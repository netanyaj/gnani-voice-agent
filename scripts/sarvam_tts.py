"""Sarvam TTS reference: REST synthesis of data/tts_test_script.txt and HTTP-stream time to first audio.

Text is sent exactly as written (numbers as in the script), like Day 1.
REST (POST /text-to-speech): bulbul:v3 ishita (EN) and pooja (ML-EN), the docs' recommended en-IN / ml-IN voices;
plus bulbul:v4-flash simran_en_customer on EN only (v4 Flash has no Malayalam, friction #72).
Stream (POST /text-to-speech/stream, linear16 at 22050 Hz): EN line, bulbul:v3 ishita, N runs. First audio = first
non-empty body chunk; full = last chunk. Comparable to Day 1's Gnani SSE runs (EN line, 10 runs).
Output: results/tts_sarvam/*.wav and results/sarvam_tts_<timestamp>.json
Usage: python scripts/sarvam_tts.py [--only rest,stream] [--runs 10] [--dry-run]
"""
import argparse
import base64
import io
import json
import statistics as st
import time
import wave

import requests

from common import DATA, RESULTS, SARVAM_BASE_URL, pick_headers, sarvam_key, stamp

OUT = RESULTS / "tts_sarvam"
REST_CASES = [("bulbul:v3", "EN", "ishita", "en-IN"), ("bulbul:v3", "ML-EN", "pooja", "ml-IN"),
              ("bulbul:v4-flash", "EN", "simran_en_customer", "en-IN")]
STREAM_CASE = ("bulbul:v3", "EN", "ishita", "en-IN")
SR = 22050
PRICE = {"bulbul:v3": 3.0, "bulbul:v4-flash": 1.0}   # Rs per 1,000 characters, pay as you go (pricing page)


def read_script():
    lines = {}
    for ln in (DATA / "tts_test_script.txt").read_text(encoding="utf-8").splitlines():
        if ":" in ln:
            tag, text = ln.split(":", 1)
            lines[tag.strip()] = text.strip()
    return lines


def wav_seconds(b):
    with wave.open(io.BytesIO(b)) as w:
        return w.getnframes() / w.getframerate()


def rest(key, text, model, tag, speaker, lang, ts):
    body = {"text": text, "language_code": lang, "speaker": speaker, "model": model}
    t0 = time.perf_counter()
    r = requests.post(f"{SARVAM_BASE_URL}/text-to-speech", headers={"api-subscription-key": key}, json=body, timeout=120)
    rtt = round((time.perf_counter() - t0) * 1000)
    row = {"model": model, "tag": tag, "speaker": speaker, "language_code": lang, "chars": len(text),
           "http_status": r.status_code, "rtt_ms": rtt, "headers": pick_headers(r.headers)}
    if r.ok:
        audio = base64.b64decode(r.json()["audios"][0])
        path = OUT / f"{ts}_{model.replace(':', '-')}_{tag}_{speaker}.wav"
        path.write_bytes(audio)
        row.update(file=str(path.relative_to(RESULTS.parent)), audio_s=round(wav_seconds(audio), 2),
                   request_id=r.json().get("request_id"))
    else:
        row["error"] = r.text[:400]
    print(f"REST {model} {tag} {speaker}: {r.status_code} {rtt} ms {row.get('audio_s', row.get('error'))}")
    return row


def stream_once(key, text, model, speaker, lang):
    body = {"text": text, "language_code": lang, "speaker": speaker, "model": model,
            "output_audio_codec": "linear16", "speech_sample_rate": SR}
    t0 = time.perf_counter()
    r = requests.post(f"{SARVAM_BASE_URL}/text-to-speech/stream", headers={"api-subscription-key": key}, json=body,
                      stream=True, timeout=120)
    if not r.ok:
        return {"http_status": r.status_code, "error": r.text[:400]}
    first, chunks = None, []
    for c in r.iter_content(chunk_size=None):
        if c:
            first = first or time.perf_counter()
            chunks.append(c)
    t_done = time.perf_counter()
    pcm = b"".join(chunks)
    return {"http_status": r.status_code, "content_type": r.headers.get("content-type"),
            "first_audio_ms": round((first - t0) * 1000) if first else None, "full_ms": round((t_done - t0) * 1000),
            "bytes": len(pcm), "chunks": len(chunks), "pcm": pcm}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="rest,stream")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    parts, lines = a.only.split(","), read_script()
    cost = 0.0
    if "rest" in parts:
        cost += sum(len(lines[t]) * PRICE[m] / 1000 for m, t, _, _ in REST_CASES)
    if "stream" in parts:
        cost += len(lines[STREAM_CASE[1]]) * a.runs * PRICE[STREAM_CASE[0]] / 1000
    print(f"lines: {', '.join(f'{k} ({len(v)} chars)' for k, v in lines.items())}; estimated cost Rs {cost:.2f}")
    if a.dry_run:
        return
    key, ts = sarvam_key(), stamp()
    OUT.mkdir(exist_ok=True)
    out = {"script": lines, "rest": [], "stream": []}
    if "rest" in parts:
        for m, t, spk, lang in REST_CASES:
            out["rest"].append(rest(key, lines[t], m, t, spk, lang, ts))
    if "stream" in parts:
        m, t, spk, lang = STREAM_CASE
        for i in range(a.runs):
            res = stream_once(key, lines[t], m, spk, lang)
            pcm = res.pop("pcm", b"")
            if i == 0 and pcm:
                path = OUT / f"{ts}_stream_{m.replace(':', '-')}_{t}_{spk}.wav"
                with wave.open(str(path), "wb") as w:
                    w.setnchannels(1), w.setsampwidth(2), w.setframerate(SR), w.writeframes(pcm)
                res["file"] = str(path.relative_to(RESULTS.parent))
            res["audio_s"] = round(len(pcm) / 2 / SR, 2) if pcm else None
            out["stream"].append(res)
            print(f"stream run {i + 1}: first audio {res.get('first_audio_ms')} ms, full {res.get('full_ms')} ms, "
                  f"{res.get('audio_s')} s audio, {res.get('chunks')} chunks {res.get('error', '')}")
            time.sleep(1.1)
        fa = [x["first_audio_ms"] for x in out["stream"] if x.get("first_audio_ms")]
        if fa:
            print(f"time to first audio: median {st.median(fa):.0f} ms ({min(fa)}–{max(fa)}, n={len(fa)})")
    p = RESULTS / f"sarvam_tts_{ts}.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"saved {p.relative_to(RESULTS.parent)}")


if __name__ == "__main__":
    main()
