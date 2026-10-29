"""Realtime STT latency: stream each clip as 16-bit PCM, 1024-byte frames, real-time pace.

Timing (all on this machine's monotonic clock):
  t_end          = moment the clip's last audio frame finishes "playing" (stream start + n_frames x 32 ms)
  delay_file_ms  = arrival of the final transcript message - t_end
  delay_speech_ms= arrival of the final transcript - estimated end of speech (energy-based, see speech_end_s)
The docs define no end-of-stream message, so after the clip we keep sending silence frames (PAD_S) at the same
pace so VAD can close the segment, then close the socket.

Output: results/stt_stream_<timestamp>.json and .csv
Usage: python scripts/stt_stream.py [--clips C1] [--runs 3] [--dry-run]
"""
import argparse
import asyncio
import csv
import json
import statistics as st
import time

import numpy as np
import soundfile as sf
from websockets.asyncio.client import connect

from common import AUDIO_16K, RESULTS, WS_STT_URL, api_key, load_clips, stamp

FRAME_BYTES = 1024           # 512 samples x 2 bytes
FRAME_S = 512 / 16000        # 32 ms
PAD_S = 4.0                  # silence after the clip
TAIL_WAIT_S = 1.0            # listen this long after the last pad frame before closing


def load_pcm(wav):
    data, sr = sf.read(wav, dtype="int16")
    assert sr == 16000 and data.ndim == 1, f"{wav} must be 16 kHz mono"
    raw = data.tobytes()
    raw += b"\x00" * (-len(raw) % FRAME_BYTES)
    return [raw[i:i + FRAME_BYTES] for i in range(0, len(raw), FRAME_BYTES)], data


def speech_end_s(samples):
    """Last 32 ms frame whose RMS is within 35 dB of the loudest frame and 10 dB above the noise floor."""
    n = len(samples) // 512
    frames = samples[: n * 512].astype(np.float64).reshape(n, 512)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    thr = max(db.max() - 35, np.percentile(db, 10) + 10)
    loud = np.nonzero(db > thr)[0]
    return float((loud[-1] + 1) * FRAME_S) if len(loud) else 0.0


async def run_once(key, frames, lang):
    headers = {"x-api-key-id": key, "lang_code": lang, "x-sample-rate": "16000"}
    msgs = []
    t_open = time.perf_counter()
    async with connect(WS_STT_URL, additional_headers=headers, open_timeout=15, max_size=None) as ws:
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        t_connected = time.perf_counter()
        if first.get("type") != "connected":
            return {"error": json.dumps(first, ensure_ascii=False)[:300]}

        async def receiver():
            async for m in ws:
                msgs.append((time.perf_counter(), json.loads(m) if isinstance(m, str) else {"binary": len(m)}))

        rx = asyncio.create_task(receiver())
        silence = b"\x00" * FRAME_BYTES
        n_pad = int(PAD_S / FRAME_S)
        t0 = time.perf_counter()
        for i, fr in enumerate(frames + [silence] * n_pad):
            delay = t0 + i * FRAME_S - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            await ws.send(fr)
        t_end = t0 + len(frames) * FRAME_S
        await asyncio.sleep(TAIL_WAIT_S)
        rx.cancel()
    trs = [(t, m) for t, m in msgs if m.get("type") == "transcript"]
    proc = [t for t, m in msgs if m.get("type") == "processing"]
    errs = [m for _, m in msgs if m.get("type") == "error"]
    late = [t for t, _ in trs if t > t_end + PAD_S]   # arrived after we stopped feeding audio
    return {
        "connect_ms": round((t_connected - t_open) * 1000),
        "t0": t0, "t_end": t_end,
        "segments": len(trs),
        "text": " ".join(m.get("text", "") for _, m in trs),
        "final_arrival_s_after_end": (trs[-1][0] - t_end) if trs else None,
        "first_processing_s_after_end": min((t - t_end for t in proc if t >= t_end - 5), default=None),
        "server_latency_ms": [m.get("latency") for _, m in trs],
        "segment_audio_ms": [m.get("audio_duration_ms") for _, m in trs],
        "arrived_after_padding": len(late),
        "errors": errs,
        "connected_msg": first,
    }


async def main_async(args):
    clips = load_clips(args.clips)
    plan = [(c, r) for c in clips for r in range(args.runs)]
    audio_s = sum(sf.info(AUDIO_16K / f"{c['clip_id']}.wav").duration + PAD_S for c, _ in plan)
    print(f"{len(clips)} clips x {args.runs} runs = {len(plan)} sessions, ~{audio_s:.0f} s streamed incl. padding")
    if args.dry_run:
        for c, r in plan:
            print(f"[dry-run] {c['clip_id']} run {r + 1} lang={c['language_code']}")
        return
    key = api_key()
    rows = []
    for c, r in plan:
        wav = AUDIO_16K / f"{c['clip_id']}.wav"
        frames, samples = load_pcm(wav)
        dur = len(samples) / 16000
        sp_end = speech_end_s(samples)
        try:
            res = await run_once(key, frames, c["language_code"])
        except Exception as e:  # keep going; record the failure
            res = {"error": f"{type(e).__name__}: {e}"[:300]}
        fin = res.get("final_arrival_s_after_end")
        row = {
            "clip_id": c["clip_id"], "type": c["type"], "language_code": c["language_code"], "run": r + 1,
            "audio_s": round(dur, 3), "speech_end_s_est": round(sp_end, 3), "trailing_silence_s_est": round(dur - sp_end, 3),
            "connect_ms": res.get("connect_ms"),
            "delay_file_ms": round(fin * 1000) if fin is not None else None,
            "delay_speech_ms": round((fin + dur - sp_end) * 1000) if fin is not None else None,
            "server_latency_ms_last": (res.get("server_latency_ms") or [None])[-1],
            "segments": res.get("segments"),
            "arrived_after_padding": res.get("arrived_after_padding"),
            "text": res.get("text", ""),
            "error": res.get("error") or (json.dumps(res.get("errors"), ensure_ascii=False) if res.get("errors") else ""),
        }
        rows.append({**row, "detail": {k: v for k, v in res.items() if k not in ("t0", "t_end")}})
        print(f"{c['clip_id']:3} run {r + 1}: file-end→final {row['delay_file_ms']} ms, speech-end→final "
              f"{row['delay_speech_ms']} ms, server latency {row['server_latency_ms_last']} ms, "
              f"{row['segments']} seg | {row['text'] or row['error']}")

    ts = stamp()
    (RESULTS / f"stt_stream_{ts}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    cols = [k for k in rows[0] if k != "detail"]
    with open(RESULTS / f"stt_stream_{ts}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print("\n| Clip | Runs | file-end→final median (range) ms | speech-end→final median (range) ms | server latency median ms |")
    print("|---|---|---|---|---|")
    allf, alls = [], []
    for c in clips:
        rs = [x for x in rows if x["clip_id"] == c["clip_id"] and x["delay_file_ms"] is not None]
        if not rs:
            print(f"| {c['clip_id']} | 0 | — | — | — |")
            continue
        f_ = [x["delay_file_ms"] for x in rs]
        s_ = [x["delay_speech_ms"] for x in rs]
        lat = [x["server_latency_ms_last"] for x in rs if x["server_latency_ms_last"] is not None]
        allf += f_
        alls += s_
        print(f"| {c['clip_id']} | {len(rs)} | {st.median(f_):.0f} ({min(f_)}–{max(f_)}) | {st.median(s_):.0f} "
              f"({min(s_)}–{max(s_)}) | {st.median(lat) if lat else '—'} |")
    if allf:
        print(f"| ALL | {len(allf)} | {st.median(allf):.0f} ({min(allf)}–{max(allf)}) | {st.median(alls):.0f} "
              f"({min(alls)}–{max(alls)}) | |")
    print(f"saved results/stt_stream_{ts}.json and .csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
