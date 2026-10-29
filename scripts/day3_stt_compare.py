"""Gnani vs Sarvam STT side by side, from the two score CSVs (same clips, same scorer, one run per clip per mode).

Usage: python scripts/day3_stt_compare.py [--gnani results/score_20261025_161827.csv]
                                          [--sarvam results/score_sarvam_stt_20261026_232914.csv]
Writes results/day3_stt_compare.md
"""
import argparse
import csv
from collections import defaultdict

from common import RESULTS

TYPES = ["clean", "noisy", "mixed", "numbers", "phone"]
KEYS = ("es", "ns", "el", "nl", "nc", "nt")


def load(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def agg(rows):
    a = defaultdict(lambda: dict.fromkeys(KEYS, 0))
    for r in rows:
        for t in (r["type"], "ALL"):
            x = a[t]
            x["es"] += int(r["strict_S"]) + int(r["strict_D"]) + int(r["strict_I"])
            x["ns"] += int(r["ref_words"])
            x["el"] += int(r["lenient_S"]) + int(r["lenient_D"]) + int(r["lenient_I"])
            x["nl"] += int(r["lenient_words"])
            x["nc"] += int(r["numbers_correct"])
            x["nt"] += int(r["numbers_total"])
    return a


def rate(d, e, n):
    return f"{d[e] / d[n]:.3f} ({d[e]}/{d[n]})"


def nums(d):
    return f"{d['nc']}/{d['nt']}" if d["nt"] else "—"


def table(title, g_rows, s_rows):
    g, s = agg(g_rows), agg(s_rows)
    out = [f"### {title}", "", "| Type | Clips | WER strict Gnani | WER strict Sarvam | WER lenient Gnani | WER lenient Sarvam "
           "| Numbers Gnani | Numbers Sarvam |", "|---|---|---|---|---|---|---|---|"]
    for t in TYPES + ["ALL"]:
        n = len({r["clip_id"] for r in g_rows if t in (r["type"], "ALL")})
        out.append(f"| {t} | {n} | {rate(g[t], 'es', 'ns')} | {rate(s[t], 'es', 'ns')} | {rate(g[t], 'el', 'nl')} "
                   f"| {rate(s[t], 'el', 'nl')} | {nums(g[t])} | {nums(s[t])} |")
    return out + [""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gnani", default=str(RESULTS / "score_20261025_161827.csv"))
    ap.add_argument("--sarvam", default=str(RESULTS / "score_sarvam_stt_20261026_232914.csv"))
    a = ap.parse_args()
    G, S = load(a.gnani), load(a.sarvam)
    pick = lambda rows, f: [r for r in rows if r["format"] == f]
    lines = ["# STT: Gnani (Prisma v2.5) vs Sarvam (saaras:v4), Day 1 clips", "",
             f"Sources: `{a.gnani.split('/')[-1]}`, `{a.sarvam.split('/')[-1]}`. Same 11 clips, same language codes, "
             "same scorer (`scripts/score.py`), one request per clip per mode. Pooled = errors / reference words.", ""]
    lines += table("Headline: verbatim (Gnani format=verbatim vs Sarvam mode=verbatim)", pick(G, "verbatim"), pick(S, "verbatim"))
    lines += table("Defaults (Gnani no format field vs Sarvam mode=transcribe)", pick(G, "default"), pick(S, "transcribe"))
    lines += ["### Gnani's misses, clip by clip (verbatim)", "", "| Clip | What was said | Gnani | Sarvam |", "|---|---|---|---|"]
    said = {"D3": "ഒൻപതര ശതമാനം (9.5%)", "P1": "7 3 0 9 4 1 8 2 6 5 over a phone line", "P2": "renew (phone line)",
            "N2": "അനിത … അറിയണം (noisy)"}
    for cid, what in said.items():
        g = next(r for r in pick(G, "verbatim") if r["clip_id"] == cid)
        s = next(r for r in pick(S, "verbatim") if r["clip_id"] == cid)
        cell = lambda r: f"lenient WER {r['wer_lenient']}; numbers {r['numbers_detail'] or '—'}; “{r['hypothesis']}”"
        lines.append(f"| {cid} | {what} | {cell(g)} | {cell(s)} |")
    lines += ["", "### Script of English words in mixed / phone Malayalam clips (M1, M2, P2: 16 English words)", "",
              "| Output | Latin script |", "|---|---|"]
    for name, rows, fmt in (("Gnani verbatim", G, "verbatim"), ("Gnani default", G, "default"),
                            ("Sarvam verbatim", S, "verbatim"), ("Sarvam transcribe", S, "transcribe"),
                            ("Sarvam codemix", S, "codemix")):
        notes = [n for r in pick(rows, fmt) if r["clip_id"] in ("M1", "M2", "P2") for n in r["script_notes"].split("; ")
                 if "=" in n and not n.startswith("Latin tokens")]
        lat = sum(n.split("=", 1)[1].startswith("Latin") for n in notes)
        lines.append(f"| {name} | {lat}/{len(notes)} |")
    md = "\n".join(lines) + "\n"
    (RESULTS / "day3_stt_compare.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
