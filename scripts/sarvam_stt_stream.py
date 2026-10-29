"""Sarvam realtime STT latency (wss /speech-to-text-realtime/ws, beta), same method as scripts/stt_stream.py (Day 1).

Same clips, 16-bit PCM in 1024-byte frames at real-time pace (32 ms), same 4 s silence pad, same energy-based
end-of-speech estimate. Differences are protocol only: each frame is sent as {"event":"audio_input","audio":<base64>}
and after the pad we send {"event":"end"} and wait for session.end (which reports the billed audio seconds).
Docs say the defaults are saaras:v3-realtime and 500 ms VAD silence; the server actually resolved saaras:v4 and
1000 ms (friction #71). So model and silence are pinned: saaras:v4 (the server's real default) and 500 ms (the documented
default, and the same 500 ms VAD wait Gnani used on Day 1). Everything else is the server default.
  delay_file_ms   = arrival of the last transcript.final - end of the clip file
  delay_speech_ms = arrival of the last transcript.final - estimated end of speech
Output: results/sarvam_stt_stream_<timestamp>.json and .csv
Usage: python scripts/sarvam_stt_stream.py [--clips C1] [--runs 3] [--dry-run]
"""
import argparse
import asyncio
import base64
import csv
import json
import statistics as st
import time
from urllib.parse import urlencode

import soundfile as sf
from websockets.asyncio.client import connect

from common import AUDIO_16K, RESULTS, SARVAM_WS_STT_URL, load_clips, sarvam_key, stamp
from stt_stream import FRAME_BYTES, FRAME_S, PAD_S, load_pcm, speech_end_s

PARAMS = {"model": "saaras:v4", "silence_duration_ms": 500}
END_WAIT_S = 10.0     # max wait for session.end after sending "end"


async def run_once(key, frames, lang):
    url = f"{SARVAM_WS_STT_URL}?{urlencode({'language_code': lang, **PARAMS})}"
    msgs = []
    t_open = time.perf_counter()
    async with connect(url, additional_headers={"Api-Subscription-Key": key}, open_timeout=15, max_size=None) as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        t_connected = time.perf_counter()
        if first.get("event") != "session.begin":
            return {"error": json.dumps(first, ensure_ascii=False)[:300]}
        ended = asyncio.Event()

        async def receiver():
            async for m in ws:
                d = json.loads(m) if isinstance(m, str) else {"binary": len(m)}
                msgs.append((time.perf_counter(), d))
                if d.get("event") == "session.end":
                    ended.set()

        rx = asyncio.create_task(receiver())
        silence = b"\x00" * FRAME_BYTES
        t0 = time.perf_counter()
        for i, fr in enumerate(frames + [silence] * int(PAD_S / FRAME_S)):
            delay = t0 + i * FRAME_S - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            await ws.send(json.dumps({"event": "audio_input", "audio": base64.b64encode(fr).decode()}))
        t_end = t0 + len(frames) * FRAME_S
        t_pad_end = time.perf_counter()
        await ws.send(json.dumps({"event": "end"}))
        try:
            await asyncio.wait_for(ended.wait(), timeout=END_WAIT_S)
        except asyncio.TimeoutError:
            pass
        rx.cancel()
    fin = [(t, m) for t, m in msgs if m.get("event") == "transcript.final"]
    vad_end = [t for t, m in msgs if m.get("event") == "vad.speech_end"]
    end = next((m for _, m in msgs if m.get("event") == "session.end"), {})
    return {
        "connect_ms": round((t_connected - t_open) * 1000),
        "segments": len(fin),
        "text": " ".join(m.get("text", "") for _, m in fin),
        "final_arrival_s_after_end": (fin[-1][0] - t_end) if fin else None,
        "vad_end_s_after_end": (vad_end[-1] - t_end) if vad_end else None,
        "arrived_after_padding": sum(t > t_pad_end for t, _ in fin),
        "billed_audio_s": end.get("audio_duration_s"),
        "errors": [m for _, m in msgs if m.get("event") == "error"],
        "session_begin": first,
        "session_end": end,
    }


async def main_async(a):
    clips = load_clips(a.clips)
    plan = [(c, r) for c in clips for r in range(a.runs)]
    audio_s = sum(sf.info(AUDIO_16K / f"{c['clip_id']}.wav").duration + PAD_S for c, _ in plan)
    print(f"{len(clips)} clips x {a.runs} runs = {len(plan)} sessions, ~{audio_s:.0f} s streamed incl. padding "
          f"(~Rs {audio_s / 60 * 0.49:.2f} at Rs 0.49/min)")
    if a.dry_run:
        return
    key = sarvam_key()
    rows = []
    for c, r in plan:
        frames, samples = load_pcm(AUDIO_16K / f"{c['clip_id']}.wav")
        dur, sp_end = len(samples) / 16000, speech_end_s(samples)
        try:
            res = await run_once(key, frames, c["language_code"])
        except Exception as e:
            res = {"error": f"{type(e).__name__}: {e}"[:300]}
        fin = res.get("final_arrival_s_after_end")
        row = {"clip_id": c["clip_id"], "type": c["type"], "language_code": c["language_code"], "run": r + 1,
               "audio_s": round(dur, 3), "speech_end_s_est": round(sp_end, 3),
               "connect_ms": res.get("connect_ms"),
               "delay_file_ms": round(fin * 1000) if fin is not None else None,
               "delay_speech_ms": round((fin + dur - sp_end) * 1000) if fin is not None else None,
               "vad_end_after_speech_ms": round((res["vad_end_s_after_end"] + dur - sp_end) * 1000)
               if res.get("vad_end_s_after_end") is not None else None,
               "segments": res.get("segments"), "arrived_after_padding": res.get("arrived_after_padding"),
               "billed_audio_s": res.get("billed_audio_s"), "text": res.get("text", ""),
               "error": res.get("error") or (json.dumps(res.get("errors"), ensure_ascii=False) if res.get("errors") else "")}
        rows.append({**row, "detail": res})
        print(f"{c['clip_id']:3} run {r + 1}: speech-end→final {row['delay_speech_ms']} ms (VAD end "
              f"{row['vad_end_after_speech_ms']} ms), {row['segments']} seg, billed {row['billed_audio_s']} s | "
              f"{row['text'] or row['error']}")
    ts = stamp()
    (RESULTS / f"sarvam_stt_stream_{ts}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(RESULTS / f"sarvam_stt_stream_{ts}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k != "detail"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    ok = [x for x in rows if x["delay_speech_ms"] is not None]
    for label, sel in (("ALL", ok), ("ALL excl. P1", [x for x in ok if x["clip_id"] != "P1"])):
        v = [x["delay_speech_ms"] for x in sel]
        if v:
            print(f"{label}: speech-end→final median {st.median(v):.0f} ms ({min(v)}–{max(v)}, n={len(v)})")
    print(f"saved results/sarvam_stt_stream_{ts}.json and .csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
