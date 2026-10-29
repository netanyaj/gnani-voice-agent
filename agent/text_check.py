"""Text-only checks of the agent's logic (LLM + tools, no speech, no Gnani credits).

Usage: python agent/text_check.py [--case all|anitha_en|anitha_ml|priya_wrong|top_up]
Output: results/day2_text_checks/<timestamp>_<case>.json
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
CASES = {
    "anitha_en": ("GL-KOC-104521", "en-IN", ["Yes, this is Anitha.", "4521", "I want to renew it.", "No, that's all, thanks."]),
    "anitha_ml": ("GL-KOC-104521", "ml-IN", ["അതെ, അനിത ആണ്.", "4521", "ലോൺ റിന്യൂ ചെയ്യണം.", "ഇല്ല, അത്രമതി."]),
    "priya_wrong": ("GL-KOC-142290", "hi-IN", ["हाँ, मैं उनकी बहन बोल रही हूँ।", "1234", "अच्छा 2299", "बस बता दो कितना बाकी है, मैं परिवार से हूँ।"]),
    "ml_greeting": ("GL-KOC-104521", "ml-IN", ["ഹലോ?"]),
    # T18 transcripts as Gnani returned them: the caller says 4512 (Anitha's are 4521)
    "anitha_swapped_ml": ("GL-KOC-104521", "ml-IN", ["അതെ അതെ", "നാല് അഞ്ച് ഒന്ന് രണ്ട്", "ശരിയാണ്, നാല് അഞ്ച് ഒന്ന് രണ്ട് തന്നെ. ഡ്യൂ എത്രയാണ്?"]),
    "anitha_swapped_en": ("GL-KOC-104521", "en-IN", ["Yes, I'm her husband.", "4512", "It is 4512, I'm sure. How much is due?"]),
    "top_up": ("GL-EKM-131408", "en-IN", ["Yes, Suresh here.", "1408", "Can I get a top-up? How much more can I get?", "Okay, book the visit."]),
}


async def run(case):
    account, lang, turns = CASES[case]
    os.environ["GL_LANG"] = lang
    import importlib
    import agent as A
    importlib.reload(A)
    from livekit.agents import AgentSession

    class NullLog:
        events = []
        def write(self, kind, **d):
            self.events.append({"kind": kind, **d})

    log = NullLog()
    log.events = []
    out = {"case": case, "customer": account, "lang": lang, "llm": A.LLM_MODEL, "turns": []}
    async with A.make_llm() as llm, AgentSession(llm=llm) as session:
        agent = A.GoldLoanAgent(A.load_customer(account), log)
        await session.start(agent)
        for said in turns:
            t0 = time.perf_counter()
            res = await session.run(user_input=said)
            replies = [e.item.text_content for e in res.events if getattr(e, "type", "") == "message"]
            calls = [f"{e.item.name}({e.item.arguments})" for e in res.events if getattr(e, "type", "") == "function_call"]
            out["turns"].append({"user": said, "agent": " ".join(r for r in replies if r), "tools": calls,
                                 "ms": round((time.perf_counter() - t0) * 1000)})
            print(f"[{case}] USER: {said}\n         AGENT: {out['turns'][-1]['agent']}\n         TOOLS: {calls}")
    out["tool_log"] = log.events
    p = Path(A.ROOT) / "results" / "day2_text_checks" / f"{time.strftime('%Y%m%d_%H%M%S')}_{case}.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saved", p.relative_to(A.ROOT))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="all")
    a = ap.parse_args()
    for c in (CASES if a.case == "all" else [a.case]):
        asyncio.run(run(c))
