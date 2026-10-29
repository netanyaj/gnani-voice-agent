"""Group Gnani-trial friction rows (#1-#68, Days 1-2) by cause and count by severity. Sarvam rows (#69+) excluded.

The mapping below is hand-assigned, one group per row, with the reason in a comment where it isn't obvious.
Severity is read from logs/friction_log.md ('Major (for voice)' / 'Major (to confirm...)' count as Major).
Usage: python scripts/day3_friction_groups.py   (prints the table and the row list per group)
"""
import re
from collections import Counter, defaultdict

from common import ROOT

GROUPS = {
    "Speech recognition (Gnani STT)": [13, 19, 20, 21, 22, 23, 24, 25, 27, 29, 30, 58, 59, 65, 66],
    "Voice output (Gnani TTS, voice clone)": [15, 32, 33, 34, 35, 62, 68],
    "Docs": [6, 7, 8, 10, 11, 12, 14, 18, 28, 31, 49],
    # 9: no end-of-stream message is an API design gap first; 16/26: output-format quirks a developer must handle
    "Developer experience (keys, plugin, errors, API ergonomics)": [4, 9, 16, 26, 37, 38, 39, 40, 41, 42, 53],
    # 5: the speech key is rejected by the Agent Builder Platform API, i.e. part of the same gate
    "Access (signup, Agent Builder gate)": [1, 3, 5],
    "Billing": [2, 17, 36, 63],
    # LLM, LiveKit, my prompt or my setup; kept so every row is accounted for
    "Not Gnani (Gemini, LiveKit, my prompt or setup)": [43, 44, 45, 46, 47, 48, 50, 51, 52, 54, 55, 56, 57, 60, 61, 64, 67],
}
SEVS = ["Blocker", "Major", "Minor", "Delight"]


def severities():
    sev = {}
    for line in (ROOT / "logs/friction_log.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 8 and cells[1].isdigit():
            m = re.match(r"(Blocker|Major|Minor|Delight)", cells[7])
            sev[int(cells[1])] = m.group(1) if m else "?"
    return sev


def main():
    sev = severities()
    rows = [n for g in GROUPS.values() for n in g]
    assert sorted(rows) == list(range(1, 69)), f"unassigned/duplicate: {sorted(set(range(1, 69)) ^ set(rows))}"
    print("| Cause | Rows | " + " | ".join(SEVS) + " |")
    print("|---|---|" + "---|" * len(SEVS))
    total = Counter()
    for g, ns in GROUPS.items():
        c = Counter(sev[n] for n in ns)
        total.update(c)
        print(f"| {g} | {len(ns)} | " + " | ".join(str(c.get(s, 0)) for s in SEVS) + " |")
    print(f"| **All rows #1–#68** | {len(rows)} | " + " | ".join(str(total.get(s, 0)) for s in SEVS) + " |")
    print()
    for g, ns in GROUPS.items():
        by = defaultdict(list)
        for n in ns:
            by[sev[n]].append(f"#{n}")
        print(f"- {g}: " + "; ".join(f"{s} {', '.join(by[s])}" for s in SEVS if by[s]))


if __name__ == "__main__":
    main()
