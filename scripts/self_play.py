"""Self-play: the Day 2 agent against a scripted caller, no microphone.

The agent side is agent/agent.py itself: build_session() (Silero VAD, Gnani STT, Gemini with fallback, Gnani TTS,
LiveKit's default turn detection), the same prompt, tools, greeting and jsonl logging. Only the audio I/O differs:
  caller line -> Gnani TTS REST (a different voice) -> 16 kHz mono 16-bit PCM -> the agent's audio input in 10 ms
  frames at real-time pace, with silence frames between lines (as a mic sends) -> Gnani STT stream, as live audio.
  agent speech -> a virtual speaker that "plays" in real time (so turn-taking and interruptions behave as in the
  console) and records it.
The caller waits for the agent to finish, pauses 0.8 s, then says its next line. It does not listen: lines are fixed.

Usage: python scripts/self_play.py data/self_play_T08R.json [--dry-run]
Output: results/day2_conversations/<ts>_<customer>_<label>.jsonl (same format as the console runs)
        results/day2_self_play/<ts>_<label>_call.wav (both sides mixed, 16 kHz), caller_audio/ (cached caller lines)
"""
import argparse
import asyncio
import io
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import BASE_URL, api_key  # noqa: E402

OUT = ROOT / "results" / "day2_self_play"
CALLER_AUDIO = OUT / "caller_audio"
SR = 16000
FRAME = 160  # 10 ms at 16 kHz
GAP_S = 0.8  # caller pause after the agent stops
IDLE_S = 1.5  # agent counts as finished after this long listening with nothing playing
REPLY_TIMEOUT_S = 40


# ---------------------------------------------------------------- caller audio (Gnani TTS REST, cached)
def caller_wav_path(label, i, voice):
    return CALLER_AUDIO / f"{label}_{i:02d}_{voice}.wav"


def synth_caller_line(key, text, lang, voice, model):
    body = {"text": text, "voice": voice, "model": model, "language": lang, "speed": 1.0,
            "audio_config": {"sample_rate": SR, "num_channels": 1, "sample_width": 2,
                             "encoding": "linear_pcm", "container": "wav"}}
    t0 = time.perf_counter()
    r = requests.post(f"{BASE_URL}/api/v1/tts/inference", headers={"X-API-Key-ID": key}, json=body, timeout=120)
    rtt = round((time.perf_counter() - t0) * 1000)
    if not (r.ok and r.headers.get("content-type", "").startswith("audio")):
        sys.exit(f"caller TTS failed: HTTP {r.status_code} {r.text[:300]}")
    return r.content, rtt


def read_pcm16k(wav_bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        sr, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        pcm = np.frombuffer(w.readframes(n), dtype=np.int16)
    if sw != 2:
        sys.exit(f"caller audio sample width {sw}, expected 2")
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1).astype(np.int16)
    if sr != SR:  # linear resample (only if Gnani ignores the requested rate)
        pcm = resample(pcm, sr, SR)
    return pcm, sr


def resample(pcm, sr_in, sr_out):
    if sr_in == sr_out or len(pcm) == 0:
        return pcm
    n_out = int(len(pcm) * sr_out / sr_in)
    x = np.linspace(0, len(pcm) - 1, n_out)
    return np.interp(x, np.arange(len(pcm)), pcm.astype(np.float32)).astype(np.int16)


def write_wav(path, pcm, sr=SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.astype(np.int16).tobytes())


# ---------------------------------------------------------------- virtual mic and speaker
def make_io(rtc, lk_io):
    class ScriptedMic(lk_io.AudioInput):
        """Real-time 10 ms frames: queued caller audio when the caller is talking, digital silence otherwise."""

        def __init__(self):
            super().__init__(label="ScriptedMic")
            self._q = asyncio.Queue(maxsize=50)
            self._pending = np.zeros(0, dtype=np.int16)
            self._speech_done = asyncio.Event()
            self._speech_done.set()
            self.t0 = None
            self.attached = True

        def say(self, pcm):
            self._pending = pcm
            self._speech_done.clear()

        async def wait_said(self):
            await self._speech_done.wait()

        async def pump(self):
            self.t0 = time.monotonic()
            n = 0
            while True:
                if len(self._pending):
                    chunk, self._pending = self._pending[:FRAME], self._pending[FRAME:]
                    if len(chunk) < FRAME:
                        chunk = np.concatenate([chunk, np.zeros(FRAME - len(chunk), dtype=np.int16)])
                    if not len(self._pending):
                        self._speech_done.set()
                else:
                    chunk = np.zeros(FRAME, dtype=np.int16)
                if self.attached:
                    await self._q.put(rtc.AudioFrame(data=chunk.tobytes(), sample_rate=SR, num_channels=1,
                                                     samples_per_channel=FRAME))
                n += 1
                await asyncio.sleep(max(0.0, self.t0 + n * FRAME / SR - time.monotonic()))

        async def __anext__(self):
            return await self._q.get()

        def on_attached(self):
            self.attached = True

        def on_detached(self):
            self.attached = False

    class RecordingSpeaker(lk_io.AudioOutput):
        """Accepts TTS frames, 'plays' them in real time (start = first frame), records what was played."""

        def __init__(self):
            super().__init__(label="RecordingSpeaker", capabilities=lk_io.AudioOutputCapabilities(pause=False))
            self.segments = []  # (wall start, sample_rate, pcm int16 as played)
            self._buf, self._sr, self._start, self._dur = [], None, None, 0.0
            self._interrupted = asyncio.Event()
            self._task = None
            self.playing = False

        async def capture_frame(self, frame):
            await super().capture_frame(frame)
            if self._task and not self._task.done():
                await self._task
            if self._start is None:
                self._start = time.time()
                self.playing = True
                self.on_playback_started(created_at=self._start)
            self._sr = frame.sample_rate
            self._buf.append(np.frombuffer(bytes(frame.data), dtype=np.int16).copy())
            self._dur += frame.duration

        def flush(self):
            super().flush()
            if self._start is not None:
                self._task = asyncio.create_task(self._play_out())

        def clear_buffer(self):
            if self._start is not None:
                self._interrupted.set()

        async def _play_out(self):
            remaining = self._start + self._dur - time.time()
            try:
                await asyncio.wait_for(self._interrupted.wait(), timeout=max(0.0, remaining))
                interrupted = True
            except asyncio.TimeoutError:
                interrupted = False
            played = min(self._dur, time.time() - self._start) if interrupted else self._dur
            pcm = np.concatenate(self._buf) if self._buf else np.zeros(0, dtype=np.int16)
            self.segments.append((self._start, self._sr, pcm[: int(played * (self._sr or SR))]))
            self._buf, self._start, self._dur = [], None, 0.0
            self._interrupted.clear()
            self.playing = False
            self.on_playback_finished(playback_position=played, interrupted=interrupted)

    return ScriptedMic(), RecordingSpeaker()


# ---------------------------------------------------------------- conversation
async def converse(spec, lines_pcm, A, rtc, lk_io):
    customer = A.load_customer(spec["customer"])
    log = A.ConvLog(spec["customer"], spec["label"])
    log.write("session_start", **A.session_config(spec["customer"], spec["label"]), harness="self_play",
              caller_voice=spec["caller_voice"], caller_model=spec["caller_model"], script=spec["_path"])
    session = A.build_session(log)
    mic, speaker = make_io(rtc, lk_io)
    session.input.audio = mic
    session.output.audio = speaker

    state = {"agent": "initializing", "since": time.monotonic()}

    @session.on("agent_state_changed")
    def _state(ev):
        state["agent"], state["since"] = ev.new_state, time.monotonic()

    async def agent_idle(timeout):
        """True once the agent has been listening, with nothing playing, for IDLE_S."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if state["agent"] == "listening" and not speaker.playing and time.monotonic() - state["since"] >= IDLE_S:
                return True
            await asyncio.sleep(0.05)
        return False

    pump = asyncio.create_task(mic.pump())
    caller_track = []  # (wall start, pcm)
    try:
        await session.start(agent=A.GoldLoanAgent(customer, log))
        await session.say(A.greeting(customer))
        for i, (line, pcm) in enumerate(zip(spec["lines"], lines_pcm), 1):
            if not await agent_idle(REPLY_TIMEOUT_S):
                log.write("harness", event="agent_not_idle_before_line", line=i, agent_state=state["agent"])
            await asyncio.sleep(GAP_S)
            t_start = time.time()
            mic.say(pcm)
            await mic.wait_said()
            caller_track.append((t_start, pcm))
            log.write("caller_line", line=i, lang=line["lang"], text=line["text"], audio_ms=round(len(pcm) / SR * 1000),
                      started=round(t_start, 3))
            print(f"[caller {i}] {line['text']}")
            # wait for the agent to react (end-of-turn can take up to 2.5 s), then to finish
            t_wait = time.monotonic()
            while state["agent"] == "listening" and time.monotonic() - t_wait < 8:
                await asyncio.sleep(0.05)
            if state["agent"] == "listening":
                log.write("harness", event="no_agent_reaction_8s", line=i)
        if not await agent_idle(REPLY_TIMEOUT_S):
            log.write("harness", event="agent_not_idle_at_end", agent_state=state["agent"])
        await asyncio.sleep(1.0)
    finally:
        await session.aclose()
        pump.cancel()
        A.finish_log(log)
    return log.path, caller_track, speaker.segments


def mix_call(caller_track, agent_segments, path):
    events = [(t, pcm) for t, pcm in caller_track] + [(t, resample(pcm, sr or SR, SR)) for t, sr, pcm in agent_segments]
    if not events:
        return
    t0 = min(t for t, _ in events)
    total = max(int((t - t0) * SR) + len(p) for t, p in events) + SR
    mix = np.zeros(total, dtype=np.int32)
    for t, p in events:
        s = int((t - t0) * SR)
        mix[s:s + len(p)] += p
    write_wav(path, np.clip(mix, -32768, 32767))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--dry-run", action="store_true", help="show the plan; no API calls")
    a = ap.parse_args()
    spec = json.load(open(ROOT / a.script, encoding="utf-8"))
    spec["_path"] = a.script
    label, voice = spec["label"], spec["caller_voice"]

    print(f"{label}: customer {spec['customer']}, agent {spec['agent_lang']}, caller voice {voice} ({spec['caller_model']})")
    cached = [caller_wav_path(label, i, voice).exists() for i in range(1, len(spec["lines"]) + 1)]
    for i, (line, c) in enumerate(zip(spec["lines"], cached), 1):
        print(f"  {i}. [{line['lang']}] {line['text']}{'  (cached audio)' if c else ''}")
    print(f"  caller TTS requests needed: {cached.count(False)}, characters: "
          f"{sum(len(l['text']) for l, c in zip(spec['lines'], cached) if not c)}")
    if a.dry_run:
        print("dry run: nothing sent")
        return

    # agent/agent.py reads these at import time
    os.environ.update(GL_LANG=spec["agent_lang"], GL_LABEL=label, GL_CUSTOMER=spec["customer"])
    sys.path.insert(0, str(ROOT / "agent"))
    import agent as A  # noqa: E402  (loads .env; patches websockets.connect for bias/VAD headers, both off)
    from livekit import rtc  # noqa: E402
    from livekit.agents.voice import io as lk_io  # noqa: E402

    CALLER_AUDIO.mkdir(parents=True, exist_ok=True)
    key = None
    lines_pcm, synth_log = [], []
    for i, line in enumerate(spec["lines"], 1):
        p = caller_wav_path(label, i, voice)
        if not p.exists():
            key = key or api_key()
            wav_bytes, rtt = synth_caller_line(key, line["text"], line["lang"], voice, spec["caller_model"])
            p.write_bytes(wav_bytes)
            synth_log.append({"line": i, "rtt_ms": rtt, "chars": len(line["text"])})
        pcm, native_sr = read_pcm16k(p.read_bytes())
        lines_pcm.append(pcm)
        print(f"  line {i}: {len(pcm) / SR:.1f} s audio (file {native_sr} Hz)")

    log_path, caller_track, agent_segments = asyncio.run(converse(spec, lines_pcm, A, rtc, lk_io))
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": round(time.time(), 3), "kind": "caller_tts", "requests": synth_log,
                            "cached_lines": cached.count(True)}) + "\n")
    call = OUT / f"{log_path.stem}_call.wav"
    mix_call(caller_track, agent_segments, call)
    print(f"call audio: {call.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
