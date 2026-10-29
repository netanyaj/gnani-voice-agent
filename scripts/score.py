"""Score STT transcripts: word error rate, numbers correct, script choice on mixed clips.

Deterministic. For every clip it prints the normalised reference/hypothesis, S/D/I counts and the numbers it found.

Two WER columns:
  strict  - the CLAUDE.md rule: lower-case, strip punctuation, then jiwer. "4521" vs "four five two one" = errors.
  lenient - additionally (a) number expressions on both sides are rewritten to their value ("four five two one"
            and "4521" both become 4521; "one lakh eighty-four thousand five hundred" and "₹1,84,500" both become
            184500 rupees), and (b) English words returned in Malayalam/Devanagari script are mapped back to the
            English word using data/script_variants.csv (hand-checked list).
CER = character error rate on the lenient tokens with spaces removed, so Malayalam word-joining
(എത്രയാണെന്നറിയണം vs എത്രയാണെന്ന് അറിയണം) costs a couple of characters, not two words.
Both sides always get the same Unicode clean-up (NFC, atomic chillu letters, native digits -> 0-9).

Usage: python scripts/score.py [results/stt_rest_XXXX.json] [--clips C1] [--field transcript|literal]
"""
import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import jiwer

from common import DATA, RESULTS

# ---------- text clean-up ----------
CHILLU = {"ണ്‍": "ൺ", "ന്‍": "ൻ", "ര്‍": "ർ", "ല്‍": "ൽ", "ള്‍": "ൾ", "ക്‍": "ൿ"}
CURRENCY_WORD = {"en": "rupees", "ml": "രൂപ", "hi": "रुपये"}
PERCENT_WORD = {"en": "percent", "ml": "ശതമാനം", "hi": "प्रतिशत"}


def base_lang(code):
    return code.split("-")[0]


def clean(text):
    """Encoding-only clean-up, applied identically to reference, hypothesis and variant list."""
    s = unicodedata.normalize("NFC", text or "")
    for k, v in CHILLU.items():
        s = s.replace(k, v)
    s = s.replace("ൻ്റ", "ന്റ")       # two Unicode spellings of the same 'nta' cluster (എൻ്റെ = എന്റെ)
    return s.replace("‍", "").replace("‌", "")


def tokens(text, lang, lenient):
    s = clean(text)
    s = "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in s)  # native digits -> 0-9
    s = s.lower()
    s = re.sub(r"(?<=\d),(?=\d)", "", s)                       # 1,84,500 -> 184500
    if lenient:
        s = re.sub(r"(?:₹|\brs\.?)\s*(\d[\d.]*)", lambda m: f"{m.group(1)} {CURRENCY_WORD[lang]}", s)
        s = re.sub(r"(\d[\d.]*)\s*%", lambda m: f"{m.group(1)} {PERCENT_WORD[lang]}", s)
    s = re.sub(r"(?<=\d)\.(?=\d)", "\x01", s)                 # protect decimal points
    s = "".join(" " if unicodedata.category(ch)[0] in "PS" else ch for ch in s)
    return s.replace("\x01", ".").split()


# ---------- number words ----------
EN_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                       "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
EN_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split(), 0)
           if w != "_"}
EN_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
          "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
          "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
          "twentieth": 20, "thirtieth": 30}
EN_SCALE = {"hundred": 100, "thousand": 1000, "lakh": 10**5, "lakhs": 10**5, "lac": 10**5, "lacs": 10**5,
            "crore": 10**7, "crores": 10**7, "million": 10**6}
# Malayalam: matched by stem (word minus final virama/anusvara) + short suffix, e.g. ലക്ഷത്തി, ആയിരത്തി, ഒൻപതര
ML_NUM = {"പൂജ്യം": 0, "ഒന്ന്": 1, "ഒരു": 1, "രണ്ട്": 2, "മൂന്ന്": 3, "നാല്": 4, "അഞ്ച്": 5, "ആറ്": 6, "ഏഴ്": 7,
          "എട്ട്": 8, "ഒൻപത്": 9, "ഒമ്പത്": 9, "പത്ത്": 10, "പതിനൊന്ന്": 11, "പന്ത്രണ്ട്": 12, "പതിമൂന്ന്": 13,
          "പതിനാല്": 14, "പതിനഞ്ച്": 15, "പതിനാറ്": 16, "പതിനേഴ്": 17, "പതിനെട്ട്": 18, "പത്തൊൻപത്": 19,
          "ഇരുപത്": 20, "മുപ്പത്": 30, "നാല്പത്": 40, "നാൽപത്": 40, "അമ്പത്": 50, "അൻപത്": 50, "അറുപത്": 60,
          "എഴുപത്": 70, "എൺപത്": 80, "തൊണ്ണൂറ്": 90, "പതിനായിരം": 10000}
ML_SCALE = {"നൂറ്": 100, "ആയിരം": 1000, "ലക്ഷം": 10**5, "കോടി": 10**7}


def _stem(w):
    return w[:-1] if w[-1] in "്ംു" else w


ML_STEMS = sorted([(_stem(w), v, "num") for w, v in ML_NUM.items()] +
                  [(_stem(w), v, "scale") for w, v in ML_SCALE.items()], key=lambda x: -len(x[0]))


def classify(tok):
    """-> (kind, value, is_word) ; kind in num, ord, scale, point, and, None"""
    if re.fullmatch(r"\d+(\.\d+)?", tok):
        return ("num", float(tok) if "." in tok else int(tok), False)
    m = re.fullmatch(r"(\d+)(st|nd|rd|th)", tok)
    if m:
        return ("ord", int(m.group(1)), False)
    if tok in EN_UNITS:
        return ("num", EN_UNITS[tok], True)
    if tok in EN_TENS:
        return ("num", EN_TENS[tok], True)
    if tok in EN_ORD:
        return ("ord", EN_ORD[tok], True)
    if tok in EN_SCALE:
        return ("scale", EN_SCALE[tok], True)
    if tok in ("point", "പോയിന്റ്", "दशमलव"):
        return ("point", None, True)
    if tok == "and":
        return ("and", None, True)
    for stem, v, kind in ML_STEMS:
        if kind == "num" and tok.startswith(stem) and tok[len(stem):].startswith("ായിര"):
            return ("num", v * 1000, True)              # ഒൻപതായിരം = nine thousand (one compound word)
        if tok.startswith(stem) and len(tok) - len(stem) <= 4:
            rest = tok[len(stem):]
            if kind == "num" and rest == "ര":          # ഒൻപതര = nine and a half
                return ("num", v + 0.5, True)
            return (kind, v, True)
    return (None, None, False)


def fmt(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def run_value(run):
    """run = list of (kind, value, is_word). Returns (primary_value, all_candidate_values)."""
    cands = set()
    if any(k == "point" for k, _, _ in run):
        i = next(j for j, (k, _, _) in enumerate(run) if k == "point")
        ip, _ = run_value(run[:i]) if i else (0, set())
        frac = "".join(fmt(v) for k, v, _ in run[i + 1:] if k == "num")
        val = float(f"{fmt(ip)}.{frac}") if frac else ip
        return val, {val, ip}
    if any(k == "scale" for k, _, _ in run):
        total = cur = 0
        for k, v, _ in run:
            if k in ("num", "ord"):
                cur += v
            elif k == "scale" and v == 100:
                cur = (cur or 1) * 100
            elif k == "scale":
                total += (cur or 1) * v
                cur = 0
        val = total + cur
        return val, {val}
    groups = []          # digit-by-digit / year reading: "four five two one" -> 4521, "twenty twenty six" -> 2026
    for k, v, word in run:
        if k == "and":
            continue
        if groups and word and groups[-1][1] and groups[-1][0] % 10 == 0 and 20 <= groups[-1][0] <= 90 \
                and isinstance(v, int) and 0 < v < 10 and not groups[-1][2]:
            groups[-1] = (groups[-1][0] + v, True, True)
        else:
            groups.append((v, word, False))
    cands |= {g[0] for g in groups}
    if len(groups) == 1:
        return groups[0][0], cands
    if all(isinstance(g[0], int) for g in groups):
        val = int("".join(str(g[0]) for g in groups))
        cands.add(val)
        return val, cands
    return groups[0][0], cands


def numbers_in(toks):
    """-> (canonical tokens with number runs replaced by value, set of number values found, list of runs found)."""
    out, values, found = [], set(), []
    i = 0
    while i < len(toks):
        k, v, w = classify(toks[i])
        if k in ("num", "ord", "scale"):
            j, run = i, []
            while j < len(toks):
                kj = classify(toks[j])
                if kj[0] in ("num", "ord", "scale"):
                    run.append(kj)
                elif kj[0] in ("point", "and") and j + 1 < len(toks) and classify(toks[j + 1])[0] in ("num", "ord"):
                    run.append(kj)
                else:
                    break
                j += 1
            # "7 3 0 9 ... 5 one lakh ..." : split a leading digit-by-digit sequence off a scale phrase
            lead = 0
            while lead < len(run) and run[lead][0] == "num" and isinstance(run[lead][1], int) and run[lead][1] < 10:
                lead += 1
            if lead >= 2 and any(k_ == "scale" for k_, _, _ in run[lead:]):
                if run[lead][0] == "scale":   # the last digit belongs to the scale phrase ("one lakh")
                    lead -= 1
                run, j = run[:lead], i + lead
            val, cands = run_value(run)
            values |= cands | {val}
            found.append(f"{' '.join(toks[i:j])} → {fmt(val)}")
            out.append(fmt(val))
            i = j
        else:
            out.append(toks[i])
            i += 1
    return out, values, found


MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8,
          "september": 9, "october": 10, "november": 11, "december": 12, "മാർച്ച്": 3}


def number_ok(expected, values, toks):
    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", expected):            # date: day + month + year all present
        d, m, y = (int(x) for x in expected.split("-"))
        month_ok = any(MONTHS.get(t) == m for t in toks) or m in values
        return d in values and month_ok and y in values
    e = float(expected)
    return any(abs(float(v) - e) < 1e-9 for v in values)


# ---------- script variants for mixed clips ----------
def load_variants():
    path = DATA / "script_variants.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {clean(r["variant"]).strip(): r["english"].strip().lower()
                for r in csv.DictReader(f) if r.get("variant")}


def is_latin(tok):
    return bool(re.search(r"[a-z]", tok))


def script_notes(ref_toks, hyp_toks, variants):
    eng = [t for t in ref_toks if is_latin(t)]
    if not eng:
        return ""
    hyp_set = set(hyp_toks)
    notes = []
    for w in dict.fromkeys(eng):
        if w in hyp_set:
            notes.append(f"{w}=Latin")
        else:
            hits = [h for h in hyp_toks if w in variants.get(h, "").split()]
            notes.append(f"{w}=native script ({hits[0]})" if hits else f"{w}=missing")
    lat = sum(is_latin(t) for t in hyp_toks)
    return f"{'; '.join(notes)} | hyp tokens: {lat} Latin, {len(hyp_toks) - lat} other script"


def apply_variants(toks, variants):
    out = []
    for t in toks:
        out.extend(variants[t].split() if t in variants else [t])
    return out


# ---------- main ----------
def wer_counts(ref, hyp):
    if not hyp:
        return {"S": 0, "D": len(ref), "I": 0, "N": len(ref)}
    o = jiwer.process_words(" ".join(ref), " ".join(hyp))
    return {"S": o.substitutions, "D": o.deletions, "I": o.insertions, "N": len(ref)}


def cer_counts(ref, hyp):
    """Character edits with spaces removed, so Malayalam word-joining (sandhi) isn't double-counted."""
    r, h = "".join(ref), "".join(hyp)
    if not h:
        return len(r), len(r)
    o = jiwer.process_characters(r, h)
    return o.substitutions + o.deletions + o.insertions, len(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", help="stt_rest_*.json (default: newest)")
    ap.add_argument("--clips")
    ap.add_argument("--field", default="transcript", help="response field to score (transcript or literal)")
    args = ap.parse_args()

    src = Path(args.input) if args.input else max(RESULTS.glob("stt_rest_*.json"), key=lambda p: p.stat().st_mtime)
    rows = json.loads(src.read_text(encoding="utf-8"))
    if args.clips:
        rows = [r for r in rows if r["clip_id"] in args.clips.split(",")]
    with open(DATA / "clip_scripts.csv", newline="", encoding="utf-8") as f:
        refs = {r["clip_id"]: r for r in csv.DictReader(f)}
    with open(DATA / "expected_numbers.csv", newline="", encoding="utf-8") as f:
        expected = {r["clip_id"]: r["expected_values"].split(";") for r in csv.DictReader(f)}
    variants = load_variants()

    out_rows, lines = [], [f"# STT scoring — {src.name} (field: `{args.field}`)\n"]
    for r in rows:
        cid, lang = r["clip_id"], base_lang(r["language_code"])
        ref_text, hyp_text = refs[cid]["reference_transcript"], r.get(args.field) or ""
        ref_s, hyp_s = tokens(ref_text, lang, False), tokens(hyp_text, lang, False)
        ref_l, _, _ = numbers_in(tokens(ref_text, lang, True))
        hyp_lt = apply_variants(tokens(hyp_text, lang, True), variants)
        hyp_l, values, found = numbers_in(hyp_lt)
        strict, lenient = wer_counts(ref_s, hyp_s), wer_counts(ref_l, hyp_l)
        c_err, c_n = cer_counts(ref_l, hyp_l)   # on lenient tokens: digits-vs-words and script don't count
        exp = expected.get(cid, [])
        num_res = [(e, number_ok(e, values, hyp_l)) for e in exp]
        row = {
            "clip_id": cid, "type": r["type"], "format": r["format"], "language_code": r["language_code"],
            "ref_words": strict["N"],
            "strict_S": strict["S"], "strict_D": strict["D"], "strict_I": strict["I"],
            "wer_strict": round((strict["S"] + strict["D"] + strict["I"]) / strict["N"], 3),
            "cer_errors": c_err, "ref_chars": c_n, "cer": round(c_err / c_n, 3),
            "lenient_words": lenient["N"],
            "lenient_S": lenient["S"], "lenient_D": lenient["D"], "lenient_I": lenient["I"],
            "wer_lenient": round((lenient["S"] + lenient["D"] + lenient["I"]) / lenient["N"], 3),
            "numbers_correct": sum(ok for _, ok in num_res), "numbers_total": len(num_res),
            "numbers_detail": "; ".join(f"{e}:{'OK' if ok else 'MISS'}" for e, ok in num_res),
            "numbers_found_in_hyp": " | ".join(found),
            "script_notes": script_notes(ref_s, hyp_s, variants) if lang != "en" and r["type"] in ("mixed", "phone") else "",
            "hypothesis": hyp_text,
        }
        out_rows.append(row)
        lines += [f"## {cid} ({r['type']}, {r['language_code']}, format={r['format']})",
                  f"- ref (strict):  {' '.join(ref_s)}", f"- hyp (strict):  {' '.join(hyp_s)}",
                  f"- ref (lenient): {' '.join(ref_l)}", f"- hyp (lenient): {' '.join(hyp_l)}",
                  f"- strict S/D/I/N = {strict['S']}/{strict['D']}/{strict['I']}/{strict['N']} → WER {row['wer_strict']:.3f}; "
                  f"lenient {lenient['S']}/{lenient['D']}/{lenient['I']}/{lenient['N']} → WER {row['wer_lenient']:.3f}; "
                  f"CER {c_err}/{c_n} = {row['cer']:.3f}",
                  f"- numbers found: {row['numbers_found_in_hyp'] or '—'}",
                  f"- expected numbers: {row['numbers_detail'] or '—'}"]
        if row["script_notes"]:
            lines.append(f"- script: {row['script_notes']}")
        lines.append("")

    # per-clip table
    table = ["| Clip | Type | Format | WER strict | WER lenient | CER | Numbers | Script notes |",
             "|---|---|---|---|---|---|---|---|"]
    for o in out_rows:
        nums = f"{o['numbers_correct']}/{o['numbers_total']}" if o["numbers_total"] else "—"
        table.append(f"| {o['clip_id']} | {o['type']} | {o['format']} | {o['wer_strict']:.3f} | {o['wer_lenient']:.3f} "
                     f"| {o['cer']:.3f} | {nums} | {o['script_notes'].split(' | ')[0] if o['script_notes'] else ''} |")
    # summary by format x type: pooled WER = total errors / total reference words
    agg = defaultdict(lambda: defaultdict(int))
    for o in out_rows:
        a = agg[(o["format"], o["type"])]
        a["clips"] += 1
        a["err_s"] += o["strict_S"] + o["strict_D"] + o["strict_I"]
        a["n_s"] += o["ref_words"]
        a["err_l"] += o["lenient_S"] + o["lenient_D"] + o["lenient_I"]
        a["n_l"] += o["lenient_words"]
        a["ce"] += o["cer_errors"]
        a["cn"] += o["ref_chars"]
        a["nc"] += o["numbers_correct"]
        a["nt"] += o["numbers_total"]
    summary = ["| Format | Type | Clips | WER strict (errors/words) | WER lenient (errors/words) | CER (errors/chars) "
               "| Numbers correct |", "|---|---|---|---|---|---|---|"]
    order = ["clean", "noisy", "mixed", "numbers", "phone"]
    for (f_, t), a in sorted(agg.items(), key=lambda x: (x[0][0], order.index(x[0][1]) if x[0][1] in order else 9)):
        summary.append(f"| {f_} | {t} | {a['clips']} | {a['err_s'] / a['n_s']:.3f} ({a['err_s']}/{a['n_s']}) "
                       f"| {a['err_l'] / a['n_l']:.3f} ({a['err_l']}/{a['n_l']}) "
                       f"| {a['ce'] / a['cn']:.3f} ({a['ce']}/{a['cn']}) "
                       f"| {a['nc']}/{a['nt'] if a['nt'] else '—'} |")

    report = "\n".join(["\n".join(lines[:1]), "## Per-clip", *table, "", "## Summary by type (pooled)", *summary,
                        "", "## Working", *lines[1:]])
    stem = src.stem.replace("stt_rest_", "")
    suffix = f"_{args.field}" if args.field != "transcript" else ""
    md = RESULTS / f"score_{stem}{suffix}.md"
    md.write_text(report, encoding="utf-8")
    with open(RESULTS / f"score_{stem}{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    print(report)
    print(f"\nsaved {md.relative_to(RESULTS.parent)} and .csv")


if __name__ == "__main__":
    main()
