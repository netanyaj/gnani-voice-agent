"""Transcribe clips with STT REST (POST /stt/v3) and record round-trip time.

Each clip is sent once per format variant: 'default' (no format field), 'verbatim', 'transcribe'.
Output: results/stt_rest_<timestamp>.json and .csv
Usage: python scripts/stt_rest.py [--clips C1,N1] [--formats default,verbatim,transcribe] [--dry-run]
"""
import argparse
import csv
import json
import time

import requests
import soundfile as sf

from common import AUDIO_16K, BASE_URL, RESULTS, api_key, load_clips, pick_headers, stamp

FORMATS = ("default", "verbatim", "transcribe")


def transcribe(key, wav, lang, fmt):
    data = {"language_code": lang}
    if fmt != "default":
        data["format"] = fmt
    t0 = time.perf_counter()
    with open(wav, "rb") as f:
        r = requests.post(f"{BASE_URL}/stt/v3", headers={"X-API-Key-ID": key},
                          files={"audio_file": (wav.name, f, "audio/wav")}, data=data, timeout=90)
    rtt_ms = (time.perf_counter() - t0) * 1000
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:2000]}
    return r, round(rtt_ms), body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", help="comma-separated clip ids (default: all recorded)")
    ap.add_argument("--formats", default=",".join(FORMATS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    clips = load_clips(args.clips)
    formats = [f for f in args.formats.split(",") if f in FORMATS]
    total_s = sum(sf.info(AUDIO_16K / f"{c['clip_id']}.wav").duration for c in clips) * len(formats)
    print(f"{len(clips)} clips x {len(formats)} formats = {len(clips) * len(formats)} requests, "
          f"{total_s:.0f} s of audio")
    if args.dry_run:
        for c in clips:
            print(f"[dry-run] {c['clip_id']} {c['language_code']} formats={formats}")
        return

    key = api_key()
    rows = []
    for c in clips:
        wav = AUDIO_16K / f"{c['clip_id']}.wav"
        for fmt in formats:
            r, rtt, body = transcribe(key, wav, c["language_code"], fmt)
            row = {
                "clip_id": c["clip_id"], "type": c["type"], "language_code": c["language_code"], "format": fmt,
                "http_status": r.status_code, "rtt_ms": rtt,
                "audio_s": round(sf.info(wav).duration, 2),
                "transcript": body.get("transcript", ""),
                "literal": (body.get("output") or {}).get("literal", ""),
                "model": body.get("model", ""), "request_id": body.get("request_id", ""),
                "processing_time_s": body.get("processing_time", ""),
                "end_to_end_latency_s": body.get("end_to_end_latency", ""),
                "error": "" if r.ok else json.dumps(body, ensure_ascii=False)[:500],
            }
            rows.append({**row, "raw_body": body, "headers": pick_headers(r.headers)})
            print(f"{c['clip_id']:3} {fmt:10} HTTP {r.status_code} {rtt:5d} ms | {row['transcript'] or row['error']}")

    ts = stamp()
    jpath = RESULTS / f"stt_rest_{ts}.json"
    jpath.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    cpath = RESULTS / f"stt_rest_{ts}.csv"
    cols = [k for k in rows[0] if k not in ("raw_body", "headers")]
    with open(cpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("saved", jpath.relative_to(RESULTS.parent), "and", cpath.relative_to(RESULTS.parent))


if __name__ == "__main__":
    main()
