"""Day 1 step 2: the Quick Start calls, exactly as documented. One STT call (C1), one TTS call.

Prints raw responses (status, headers, body / audio size). Never prints the key.
Usage: python scripts/first_contact.py [--dry-run]
"""
import argparse
import json
import time

import requests

from common import AUDIO_16K, BASE_URL, RESULTS, api_key, pick_headers, stamp

TTS_TEXT = "Your gold loan payment of Rs 4,521 is due on 28 October 2026."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    clip = AUDIO_16K / "C1.wav"
    tts_body = {
        "text": TTS_TEXT, "voice": "Kaveri", "model": "timbre-v2.5", "language": "en-IN", "speed": 1.0,
        "audio_config": {"sample_rate": 48000, "num_channels": 1, "sample_width": 2,
                         "encoding": "linear_pcm", "container": "wav"},
    }
    if args.dry_run:
        print(f"[dry-run] POST {BASE_URL}/stt/v3  audio_file={clip.name} language_code=en-IN")
        print(f"[dry-run] POST {BASE_URL}/api/v1/tts/inference  {json.dumps(tts_body, ensure_ascii=False)}")
        return

    key = api_key()
    out = {"stt": {}, "tts": {}}

    t0 = time.perf_counter()
    with open(clip, "rb") as f:
        r = requests.post(f"{BASE_URL}/stt/v3", headers={"X-API-Key-ID": key},
                          files={"audio_file": (clip.name, f, "audio/wav")},
                          data={"language_code": "en-IN"}, timeout=60)
    rtt = (time.perf_counter() - t0) * 1000
    print("=== STT /stt/v3 (C1, en-IN)")
    print("HTTP", r.status_code, f"round trip {rtt:.0f} ms")
    print("headers:", json.dumps(pick_headers(r.headers), indent=2))
    print("body:", r.text)
    out["stt"] = {"status": r.status_code, "rtt_ms": round(rtt), "headers": pick_headers(r.headers), "body": r.text}

    t0 = time.perf_counter()
    r = requests.post(f"{BASE_URL}/api/v1/tts/inference", headers={"X-API-Key-ID": key}, json=tts_body, timeout=60)
    rtt = (time.perf_counter() - t0) * 1000
    print("\n=== TTS /api/v1/tts/inference (Kaveri, timbre-v2.5, en-IN)")
    print("HTTP", r.status_code, f"round trip {rtt:.0f} ms")
    print("headers:", json.dumps(pick_headers(r.headers), indent=2))
    ctype = r.headers.get("content-type", "")
    if r.ok and not ctype.startswith(("application/json", "text/")):
        wav = RESULTS / "tts" / f"first_contact_{stamp()}.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        wav.write_bytes(r.content)
        print(f"body: {len(r.content)} bytes of {ctype}; first 12 bytes {r.content[:12]!r}; saved {wav.relative_to(RESULTS.parent)}")
        out["tts"] = {"status": r.status_code, "rtt_ms": round(rtt), "headers": pick_headers(r.headers),
                      "bytes": len(r.content), "saved": str(wav.relative_to(RESULTS.parent)), "text": TTS_TEXT}
    else:
        print("body:", r.text[:2000])
        out["tts"] = {"status": r.status_code, "rtt_ms": round(rtt), "headers": pick_headers(r.headers), "body": r.text[:2000]}

    path = RESULTS / f"first_contact_{stamp()}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nsaved", path.relative_to(RESULTS.parent))


if __name__ == "__main__":
    main()
