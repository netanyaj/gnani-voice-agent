"""TTS tests: REST synthesis (Timbre v2.5 and v3.0), SSE time-to-first-audio, voice clone.

Text: data/tts_test_script.txt — EN line in en-IN, ML-EN line in ml-IN. Text is sent as written (no pre-formatting),
because reading numbers/IDs correctly is the claim under test.
Outputs: results/tts/*.wav, results/tts_<timestamp>.json
Usage: python scripts/tts_test.py [--only rest,sse,vc] [--sse-runs 10] [--dry-run]
"""
import argparse
import base64
import io
import json
import statistics as st
import time

import requests
import soundfile as sf

from common import BASE_URL, DATA, RESULTS, api_key, pick_headers, stamp

TTS_DIR = RESULTS / "tts"
VOICES = {  # (model, line) -> (voice, language)
    ("timbre-v2.5", "EN"): ("Kaveri", "en-IN"),       # docs: preferred English voice
    ("timbre-v2.5", "ML-EN"): ("Reshma", "ml-IN"),    # docs: preferred Malayalam voice
    ("timbre-v3.0", "EN"): ("Tarika", "en-IN"),       # docs: "banking and insurance customer care"
    ("timbre-v3.0", "ML-EN"): ("Tarika", "ml-IN"),
}
SSE_CASE = ("timbre-v2.5", "EN")


def audio_cfg(sr=48000):
    return {"sample_rate": sr, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "wav"}


def read_script():
    lines = {}
    for ln in (DATA / "tts_test_script.txt").read_text(encoding="utf-8").splitlines():
        if ":" in ln:
            tag, text = ln.split(":", 1)
            lines[tag.strip()] = text.strip()
    return lines


def wav_seconds(b):
    try:
        d, sr = sf.read(io.BytesIO(b))
        return round(len(d) / sr, 2)
    except Exception as e:
        return f"unreadable: {e}"


def rest(key, text, model, voice, lang, tag, ts):
    body = {"text": text, "voice": voice, "model": model, "language": lang, "speed": 1.0, "audio_config": audio_cfg()}
    t0 = time.perf_counter()
    r = requests.post(f"{BASE_URL}/api/v1/tts/inference", headers={"X-API-Key-ID": key}, json=body, timeout=120)
    rtt = round((time.perf_counter() - t0) * 1000)
    rec = {"kind": "rest", "model": model, "voice": voice, "language": lang, "line": tag, "chars": len(text),
           "http_status": r.status_code, "rtt_ms": rtt, "headers": pick_headers(r.headers)}
    if r.ok and r.headers.get("content-type", "").startswith("audio"):
        path = TTS_DIR / f"{ts}_{model}_{tag}_{voice}.wav"
        path.write_bytes(r.content)
        rec.update(file=str(path.relative_to(RESULTS.parent)), audio_s=wav_seconds(r.content), bytes=len(r.content))
    else:
        rec["error"] = r.text[:1000]
    print(f"REST {model} {tag:5} {voice:7} HTTP {r.status_code} {rtt} ms  {rec.get('audio_s', rec.get('error'))}")
    return rec


def sse_once(key, text, model, voice, lang):
    body = {"text": text, "voice": voice, "model": model, "language": lang, "speed": 1.0, "audio_config": audio_cfg()}
    t0 = time.perf_counter()
    r = requests.post(f"{BASE_URL}/api/v1/tts/sse", headers={"X-API-Key-ID": key}, json=body, stream=True, timeout=120)
    t_headers = time.perf_counter()
    first_audio = None
    chunks, events, buf, event = [], [], "", None
    for piece in r.iter_content(chunk_size=None):
        buf += piece.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.rstrip("\r")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except ValueError:
                    data = {"raw": line[5:300]}
                events.append(event)
                audio = data.get("audio") if isinstance(data, dict) else None
                if audio:
                    if first_audio is None:
                        first_audio = time.perf_counter()
                    chunks.append(base64.b64decode(audio))
                if event == "error":
                    print("SSE error event:", data)
    t_done = time.perf_counter()
    return {"http_status": r.status_code, "headers_ms": round((t_headers - t0) * 1000),
            "ttfa_ms": round((first_audio - t0) * 1000) if first_audio else None,
            "total_ms": round((t_done - t0) * 1000), "chunks": len(chunks),
            "event_types": sorted(set(e for e in events if e)), "audio": b"".join(chunks),
            "first_chunk_head": chunks[0][:12].hex() if chunks else ""}


def voice_clone(key, text, ts):
    ref = RESULTS / "audio_16k" / "voice_ref_44k.wav"
    t0 = time.perf_counter()
    with open(ref, "rb") as f:
        r = requests.post(f"{BASE_URL}/api/v1/tts/voice-clone/embeddings", headers={"X-API-Key-ID": key},
                          files={"audio_file": (ref.name, f, "audio/wav")}, timeout=120)
    rec = {"kind": "voice_clone", "ref_file": str(ref.relative_to(RESULTS.parent)), "embed_status": r.status_code,
           "embed_ms": round((time.perf_counter() - t0) * 1000), "embed_headers": pick_headers(r.headers)}
    try:
        body = r.json()
    except ValueError:
        rec["embed_error"] = r.text[:1000]
        return rec
    # docs disagree on the shape: top-level {embedding, shape, dtype} vs nested under voice_clone_embedding
    # live API (25 Oct 2026) returns {success, message, data: {voice_clone_embedding: {...}}}
    emb = (body.get("data") or {}).get("voice_clone_embedding") or body.get("voice_clone_embedding") or body
    rec["embed_response_keys"] = sorted(body.keys())
    rec["embedding_shape"], rec["embedding_dtype"] = emb.get("shape"), emb.get("dtype")
    if not r.ok or "embedding" not in emb:
        rec["embed_error"] = f"unexpected shape, keys {sorted(body.keys())}"   # never store the body: it may hold the embedding
        return rec
    (RESULTS / f"voice_clone_embedding_{ts}.json").write_text(json.dumps(emb), encoding="utf-8")  # git-ignored
    print(f"VC embeddings HTTP {r.status_code} {rec['embed_ms']} ms keys={rec['embed_response_keys']} "
          f"shape={rec['embedding_shape']} dtype={rec['embedding_dtype']}")

    speaker = {"embedding": emb["embedding"], "shape": emb["shape"], "dtype": emb["dtype"]}
    body = {"text": text, "model": "vachana-vc-v1", "audio_config": audio_cfg(44100), "speaker_embedding": speaker}
    t0 = time.perf_counter()
    r = requests.post(f"{BASE_URL}/api/v1/tts/inference", headers={"X-API-Key-ID": key}, json=body, timeout=120)
    rec.update(tts_status=r.status_code, tts_ms=round((time.perf_counter() - t0) * 1000), chars=len(text),
               tts_headers=pick_headers(r.headers))
    if r.ok and r.headers.get("content-type", "").startswith("audio"):
        path = TTS_DIR / f"{ts}_vachana-vc-v1_EN_myvoice.wav"
        path.write_bytes(r.content)
        rec.update(file=str(path.relative_to(RESULTS.parent)), audio_s=wav_seconds(r.content))
    else:
        rec["tts_error"] = r.text[:1000]
    print(f"VC TTS HTTP {r.status_code} {rec['tts_ms']} ms {rec.get('audio_s', rec.get('tts_error'))}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="rest,sse,vc")
    ap.add_argument("--sse-runs", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    parts = args.only.split(",")
    lines = read_script()
    chars = (sum(len(lines[t]) for _, t in VOICES) if "rest" in parts else 0) \
        + (len(lines[SSE_CASE[1]]) * args.sse_runs if "sse" in parts else 0) + (len(lines["EN"]) if "vc" in parts else 0)
    print(f"lines: {', '.join(f'{k} ({len(v)} chars)' for k, v in lines.items())}; total characters to synthesise: {chars}")
    if args.dry_run:
        for (m, t), (v, l) in VOICES.items():
            print(f"[dry-run] REST {m} {t} voice={v} language={l}")
        print(f"[dry-run] SSE x{args.sse_runs}: {SSE_CASE} voice={VOICES[SSE_CASE][0]}")
        print("[dry-run] VC: embeddings from results/audio_16k/voice_ref_44k.wav, then vachana-vc-v1 on EN line")
        return

    key, ts = api_key(), stamp()
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    out = {"script": lines, "rest": [], "sse": [], "vc": None}
    if "rest" in parts:
        for (model, tag), (voice, lang) in VOICES.items():
            out["rest"].append(rest(key, lines[tag], model, voice, lang, tag, ts))
    if "sse" in parts:
        model, tag = SSE_CASE
        voice, lang = VOICES[SSE_CASE]
        for i in range(args.sse_runs):
            res = sse_once(key, lines[tag], model, voice, lang)
            audio = res.pop("audio")
            if i == 0 and audio:
                p = TTS_DIR / f"{ts}_sse_{model}_{tag}_{voice}.wav"
                p.write_bytes(audio)
                res["file"] = str(p.relative_to(RESULTS.parent))
                res["audio_s"] = wav_seconds(audio)
            res["run"] = i + 1
            out["sse"].append(res)
            print(f"SSE run {i + 1}: HTTP {res['http_status']} first audio {res['ttfa_ms']} ms, total {res['total_ms']} ms, "
                  f"{res['chunks']} chunks, events {res['event_types']}")
        tt = [x["ttfa_ms"] for x in out["sse"] if x["ttfa_ms"] is not None]
        tot = [x["total_ms"] for x in out["sse"]]
        if tt:
            out["sse_summary"] = {"runs": len(tt), "ttfa_median_ms": st.median(tt), "ttfa_min_ms": min(tt),
                                  "ttfa_max_ms": max(tt), "total_median_ms": st.median(tot)}
            print("SSE summary:", out["sse_summary"])
    if "vc" in parts:
        out["vc"] = voice_clone(key, lines["EN"], ts)
    path = RESULTS / f"tts_{ts}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saved", path.relative_to(RESULTS.parent))


if __name__ == "__main__":
    main()
