"""Check whether Gnani realtime STT accepts a word-boost list. No audio sent.

Docs: boosting is set via x-bias-list/x-bias-score headers; only the `settings_updated` reply to an `update_settings`
frame reports `bias_word_count`. So: connect with the headers, send update_settings with the same list, read the reply.

Usage: python scripts/stt_bias_probe.py [--lang ml-IN]
Output: results/stt_bias_probe_<timestamp>.json
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from websockets.asyncio.client import connect

from common import RESULTS, WS_STT_URL, api_key, stamp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
EN = ["renew", "renewal", "gold", "loan", "due", "date", "part", "payment", "interest", "callback"]
ML = ["റിന്യൂ", "ഗോൾഡ്", "ലോൺ", "ഡ്യൂ", "ഡേറ്റ്", "പാർട്ട്", "പേയ്മെന്റ്", "ഇന്ററസ്റ്റ്"]


async def probe(key, lang, words, score="1.0", extra=None):
    h = {"x-api-key-id": key, "lang_code": lang, "x-sample-rate": "16000", "x-bias-list": json.dumps(words),
         "x-bias-score": score, **(extra or {})}
    async with connect(WS_STT_URL, additional_headers=h, open_timeout=15) as ws:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
        await ws.send(json.dumps({"type": "update_settings", "bias": {"list": words, "score": float(score)}}))
        try:
            upd = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        except asyncio.TimeoutError:
            upd = {"no_reply_within_s": 5}
    return {"connected": msg, "update_reply": upd}


async def main(lang):
    key = api_key()
    out = []
    for name, words in (("english only", EN), ("malayalam only", ML), ("both (agent list)", EN + ML)):
        m = await probe(key, lang, words)
        cfg = m["update_reply"].get("config", m["update_reply"])
        out.append({"case": name, "lang": lang, "sent": len(words), **m})
        print(f"{name:18} sent {len(words):2} words -> bias_word_count={cfg.get('bias_word_count')} "
              f"bias_score={cfg.get('bias_score')} | config keys: {sorted(cfg)}")
    m = await probe(key, lang, EN, extra={"x-min-silence-ms": "400"})
    out.append({"case": "english + min-silence 400", "connected": m})
    print("with x-min-silence-ms 400 -> connected:", json.dumps(m["connected"].get("config"), ensure_ascii=False))
    p = RESULTS / f"stt_bias_probe_{stamp()}.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saved", p.relative_to(RESULTS.parent))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ml-IN")
    asyncio.run(main(ap.parse_args().lang))
