"""Timing breakdown from agent conversation logs (results/day2_conversations/*.jsonl).

Per turn (LiveKit ChatMessage.metrics, all relative to the user's end of speech as seen by Silero VAD):
  stt_final  = transcription_delay  : end of user speech -> Gnani final transcript
  end_turn   = end_of_turn_delay    : end of user speech -> LiveKit decides the turn is over
  llm_ttft   = llm_node_ttft        : LLM request -> first token
  tts_ttfb   = tts_node_ttfb        : first text sent to TTS -> first audio
  e2e        = e2e_latency          : end of user speech -> agent starts speaking
Usage: python scripts/day2_report.py [files or globs ...]   (default: all logs) [--turns]
"""
import argparse
import glob
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = [("stt_final", "transcription_delay_ms"), ("end_turn", "end_of_turn_delay_ms"), ("llm_ttft", "llm_ttft_ms"),
          ("tts_ttfb", "tts_ttfb_ms"), ("e2e", "e2e_ms")]


def load(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    start = next((r for r in rows if r["kind"] == "session_start"), {})
    return start, rows


def fmt(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "—"
    return f"{st.median(vals):.0f} ({min(vals)}–{max(vals)}, n={len(vals)})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--turns", action="store_true", help="print every turn")
    a = ap.parse_args()
    files = sorted({f for p in (a.paths or [str(ROOT / "results/day2_conversations/*.jsonl")]) for f in glob.glob(p)})
    allturns = []
    for f in files:
        start, rows = load(f)
        turns = [r for r in rows if r["kind"] == "turn"]
        timed = [t for t in turns if t.get("e2e_ms") is not None]
        allturns += timed
        flags = [r for r in rows if r["kind"] in ("error", "llm_availability", "false_interruption")]
        glitches = [r for r in rows if r.get("foreign_script")]
        print(f"\n{Path(f).name}  [{start.get('label', '')}] {start.get('customer')} {start.get('stt_language')} "
              f"tts={start.get('tts_transport')} bias={start.get('bias')}  turns={len(turns)} timed={len(timed)} "
              f"errors/fallbacks={len(flags)} wrong-script replies={len(glitches)}")
        if a.turns:
            for t in turns:
                print(f"  USER : {t.get('user')}\n  AGENT: {t.get('agent')}{'  [interrupted]' if t.get('interrupted') else ''}\n"
                      f"         " + "  ".join(f"{n}={t.get(k)}" for n, k in STAGES))
        for n, k in STAGES:
            print(f"  {n:9} {fmt([t.get(k) for t in timed])} ms")
    if len(files) > 1:
        print(f"\nALL {len(files)} conversations, {len(allturns)} timed turns")
        for n, k in STAGES:
            print(f"  {n:9} {fmt([t.get(k) for t in allturns])} ms")


if __name__ == "__main__":
    main()
