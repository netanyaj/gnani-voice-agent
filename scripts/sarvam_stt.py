"""Sarvam STT REST (POST /speech-to-text, saaras:v4) on the same 11 clips as Day 1, for reference.

Each clip is sent once per mode: 'verbatim' (closest to Gnani format=verbatim; headline), 'transcribe' (Sarvam's
default mode) and 'codemix' (English words in Latin script; the Gnani gap on mixed clips). Same language codes as Day 1.
Output rows use the stt_rest_*.json shape, so scripts/score.py scores them unchanged ('format' holds the mode).
Output: results/sarvam_stt_<timestamp>.json and .csv
Usage: python scripts/sarvam_stt.py [--clips C1] [--modes verbatim,transcribe,codemix] [--dry-run]
"""
import argparse
import csv
import json
import time

import requests
import soundfile as sf

from common import AUDIO_16K, RESULTS, SARVAM_BASE_URL, load_clips, pick_headers, sarvam_key, stamp

MODEL = "saaras:v4"
MODES = ("verbatim", "transcribe", "codemix")


def transcribe(key, wav, lang, mode):
    data = {"model": MODEL, "mode": mode, "language_code": lang}
    t0 = time.perf_counter()
    with open(wav, "rb") as f:
        r = requests.post(f"{SARVAM_BASE_URL}/speech-to-text", headers={"api-subscription-key": key},
                          files={"file": (wav.name, f, "audio/wav")}, data=data, timeout=90)
    rtt_ms = round((time.perf_counter() - t0) * 1000)
    try:
        body = r.json()
    except ValueError:
        body = {"raw_text": r.text[:500]}
    return r.status_code, rtt_ms, body, pick_headers(r.headers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    clips, modes = load_clips(a.clips), a.modes.split(",")
    audio_s = sum(sf.info(AUDIO_16K / f"{c['clip_id']}.wav").duration for c in clips) * len(modes)
    print(f"{len(clips)} clips x {len(modes)} modes = {len(clips) * len(modes)} requests, {audio_s:.1f} s audio "
          f"(~Rs {audio_s / 60 * 0.49:.2f} at Rs 0.49/min pay-as-you-go)")
    if a.dry_run:
        for c in clips:
            print(f"[dry-run] {c['clip_id']} lang={c['language_code']} modes={modes}")
        return
    key = sarvam_key()
    rows = []
    for c in clips:
        wav = AUDIO_16K / f"{c['clip_id']}.wav"
        for m in modes:
            status, rtt, body, headers = transcribe(key, wav, c["language_code"], m)
            err = "" if status == 200 else json.dumps(body, ensure_ascii=False)[:300]
            rows.append({"clip_id": c["clip_id"], "type": c["type"], "language_code": c["language_code"], "format": m,
                         "model": MODEL, "http_status": status, "rtt_ms": rtt,
                         "audio_s": round(sf.info(wav).duration, 2), "transcript": body.get("transcript", ""),
                         "detected_language": body.get("language_code"), "request_id": body.get("request_id"),
                         "error": err, "raw_body": body, "headers": headers})
            print(f"{c['clip_id']:3} {m:10} {status} {rtt:5} ms | {body.get('transcript', err)}")
            time.sleep(1.1)  # pay-as-you-go limit is 60 req/min
    ts = stamp()
    (RESULTS / f"sarvam_stt_{ts}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    cols = [k for k in rows[0] if k not in ("raw_body", "headers")]
    with open(RESULTS / f"sarvam_stt_{ts}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"saved results/sarvam_stt_{ts}.json and .csv")


if __name__ == "__main__":
    main()
