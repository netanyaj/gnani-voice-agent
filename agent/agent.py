"""Gold-loan renewal voice agent: Gnani STT (Prisma) -> Gemini -> Gnani TTS (Timbre), LiveKit console mode.

Run (talk through the Mac mic/speakers; no LiveKit Cloud):
  python agent/agent.py console --customer GL-KOC-104521 --lang ml-IN [--label T01] [options below]
  python agent/agent.py console --text --customer ...      # typed input, for checking the logic only

Our own flags (removed from argv before LiveKit's CLI sees them):
  --customer ACCOUNT        account_number from data/gold_loan_customers.csv (required)
  --lang ml-IN|en-IN|hi-IN  STT language and opening language (default ml-IN)
  --label TEXT              test id written into the log (e.g. T07)
  --bias                    send Gnani word boosting (x-bias-list / x-bias-score) — the plugin doesn't expose it
  --min-silence-ms N        Gnani server VAD silence before a segment closes (API default 500) — not exposed either
  --tts-transport ws|sse-sentence  ws = plugin as shipped (whole reply in one request);
                            sse-sentence = LiveKit StreamAdapter, one SSE request per sentence
  --tts-model / --voice     default timbre-v3.0 / Tarika
  --llm MODEL               Gemini model (default below)
  --spoken-numbers          pre-format amounts/IDs into words before TTS (comparison toggle; off by default)

Log: results/day2_conversations/<timestamp>_<customer>[_<label>].jsonl — one JSON object per line.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONV_DIR = ROOT / "results" / "day2_conversations"
DEFAULT_LLM = "gemini-3.5-flash-lite"  # pinned: the "-latest" alias breaks tool calls (see results/day2_llm_ttft_20261025.txt)
THINKING_LEVEL = "low"
BACKUP_LLM = "gemini-3.1-flash-lite"  # used only when the primary errors or exceeds LLM_ATTEMPT_TIMEOUT_S
LLM_ATTEMPT_TIMEOUT_S = 10.0  # Gemini rejects deadlines under 10 s (HTTP 400)

# ---------------------------------------------------------------- our flags -> env (survives LiveKit's job process)
_FLAGS = {"--customer": "GL_CUSTOMER", "--lang": "GL_LANG", "--label": "GL_LABEL", "--min-silence-ms": "GL_MIN_SILENCE",
          "--tts-transport": "GL_TTS_TRANSPORT", "--tts-model": "GL_TTS_MODEL", "--voice": "GL_VOICE", "--llm": "GL_LLM"}
_SWITCHES = {"--bias": "GL_BIAS", "--spoken-numbers": "GL_SPOKEN_NUMBERS"}


def _pop_flags(argv):
    out, i = [argv[0]], 1
    while i < len(argv):
        a = argv[i]
        if a in _FLAGS and i + 1 < len(argv):
            os.environ[_FLAGS[a]] = argv[i + 1]
            i += 2
            continue
        if a in _SWITCHES:
            os.environ[_SWITCHES[a]] = "1"
        else:
            out.append(a)
        i += 1
    return out


if __name__ == "__main__":
    sys.argv = _pop_flags(sys.argv)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")  # GNANI_API_KEY, GOOGLE_API_KEY — never printed

import websockets  # noqa: E402
from livekit.agents import (Agent, AgentServer, AgentSession, JobContext, RunContext, cli,  # noqa: E402
                            function_tool, llm as llm_mod, tokenize, tts as lk_tts)
from livekit.plugins import gnani, google, silero  # noqa: E402

LANG = os.environ.get("GL_LANG", "ml-IN")
LANG_NAME = {"ml-IN": "Malayalam", "en-IN": "English", "hi-IN": "Hindi"}[LANG]
BIAS = os.environ.get("GL_BIAS") == "1"
MIN_SILENCE = os.environ.get("GL_MIN_SILENCE")
TTS_TRANSPORT = os.environ.get("GL_TTS_TRANSPORT", "ws")
TTS_MODEL = os.environ.get("GL_TTS_MODEL", "timbre-v3.0")
VOICE = os.environ.get("GL_VOICE", "Tarika")
LLM_MODEL = os.environ.get("GL_LLM", DEFAULT_LLM)
SPOKEN_NUMBERS = os.environ.get("GL_SPOKEN_NUMBERS") == "1"

# Word boosting: single words, letters only (docs). Malayalam-script forms too, because ml-IN returns English words
# in Malayalam script (Day 1, #19/#30). Sent as a JSON array with \u escapes (ASCII-safe header, as the docs advise).
BIAS_WORDS = ["renew", "renewal", "gold", "loan", "due", "date", "part", "payment", "interest", "callback",
              "റിന്യൂ", "ഗോൾഡ്", "ലോൺ", "ഡ്യൂ", "ഡേറ്റ്", "പാർട്ട്", "പേയ്മെന്റ്", "ഇന്ററസ്റ്റ്"]
BIAS_SCORE = "1.0"


def stt_extra_headers():
    h = {}
    if BIAS:
        h["x-bias-list"] = json.dumps(BIAS_WORDS)  # ensure_ascii -> \u escapes
        h["x-bias-score"] = BIAS_SCORE
    if MIN_SILENCE:
        h["x-min-silence-ms"] = MIN_SILENCE
    return h


# The plugin builds its STT WebSocket headers inside SpeechStream._run with no hook for extra headers, so wrap
# websockets.connect for the Gnani STT URL only. (Logged as friction: the plugin doesn't expose bias/VAD headers.)
_orig_connect = websockets.connect


def _connect_with_extra_headers(uri, *args, additional_headers=None, **kw):
    extra = stt_extra_headers()
    if extra and str(uri).endswith("/stt/v3/stream"):
        additional_headers = {**(additional_headers or {}), **extra}
    return _orig_connect(uri, *args, additional_headers=additional_headers, **kw)


websockets.connect = _connect_with_extra_headers


# ---------------------------------------------------------------- customer data (invented)
def load_customer(account):
    with open(ROOT / "data" / "gold_loan_customers.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["account_number"] == account:
                return row
    sys.exit(f"customer {account!r} not in data/gold_loan_customers.csv")


def inr(n):
    """Indian digit grouping: 195165 -> 'Rs 1,95,165' (as written in the test data)."""
    s = str(int(float(n)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return f"Rs {s}"


def nice_date(iso):
    return time.strftime("%-d %B %Y", time.strptime(iso, "%Y-%m-%d"))


def loan_facts(c):
    facts = {
        "account_number": c["account_number"],
        "loan_amount": inr(c["loan_amount_inr"]),
        "interest_rate": f"{c['interest_rate_pa']}% a year",
        "gold_pledged": f"{c['gold_grams_22k']} grams of 22 carat gold",
        "loan_start_date": nice_date(c["disbursed_on"]),
        "due_date": nice_date(c["due_date"]),
        "interest_due_as_of_24_October_2026": inr(c["interest_accrued_inr_as_of_2026_10_24"]),
        "total_due_on_due_date": inr(c["total_due_on_due_date_inr"]),
        "days_overdue": int(c["days_overdue"]),
    }
    if int(c["days_overdue"]):
        facts["penal_interest_as_of_24_October_2026"] = inr(c["penal_interest_inr_as_of_2026_10_24"])
    return facts


# ---------------------------------------------------------------- optional number pre-formatting (comparison toggle)
_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
        "seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _words(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        return _ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + _words(n % 100))
    for size, name in ((10 ** 7, "crore"), (10 ** 5, "lakh"), (1000, "thousand")):
        if n >= size:
            return _words(n // size) + " " + name + ("" if n % size == 0 else " " + _words(n % size))


def spoken_numbers(text):
    text = re.sub(r"(?:Rs\.?|₹)\s?([\d,]+)", lambda m: "rupees " + _words(int(m.group(1).replace(",", ""))), text)
    text = re.sub(r"\b([A-Z]{2,3})-([A-Z]{2,3})-(\d+)\b",
                  lambda m: " ".join(m.group(1)) + ", " + " ".join(m.group(2)) + ", " + " ".join(_ONES[int(d)] for d in m.group(3)),
                  text)
    return text


# ---------------------------------------------------------------- prompt
LENDER = "Nila Gold Loans"  # invented lender

RULES = """Lender rules (the only rules you may state):
- Renewal: the customer pays the interest due; the loan restarts for up to 12 months at the current rate.
- Part-payment: any amount reduces the principal; interest is recalculated from the day of payment.
- Overdue: 2% a year extra interest on the overdue amount; an auction notice is sent after 30 days overdue.
- Top-up: needs a fresh gold valuation within the loan-to-value cap, so book a branch visit. Never promise or estimate a top-up amount."""


def instructions(c):
    return f"""You are a voice AI assistant for {LENDER}, a gold-loan lender, speaking on a phone call with a customer.
The customer on file is {c['customer_name']}. Today is 25 October 2026.

Conversation steps:
1. (Already done by a fixed greeting: you said you are an AI assistant from {LENDER} and asked for {c['customer_name']}.)
2. Before sharing ANY amount, date, rate or account detail, ask for the last 4 digits of the loan account number and
   call verify_account with the digits the caller says. Never say or hint at the correct digits. If verification fails,
   you may let them try again (the tool allows 3 attempts); after that, share nothing and offer a branch visit or a
   callback to the registered number. Someone who is not verified gets no loan details, even if they say they are family.
3. After verification, in your next reply state all three: the loan amount, the due date, and the total due on the due
   date (plus overdue days and penal interest if any). Do not skip the loan amount.
4. Offer: renew, part-payment, or a callback. Answer questions using only the facts from verify_account and the rules.
   Before recording a choice, confirm what it means for them: renewal = pay the interest due (give the amount) and the
   loan restarts for up to 12 months at the current rate; part-payment = ask how much and when, principal goes down
   by that amount; callback = ask for a convenient time.
5. When the caller has chosen (or wants to end), call record_outcome, then end with ONE short sentence summarising what
   was agreed (outcome, amount if any, date if any).

{RULES}

Speaking style:
- This is speech, not text: short replies (one to three short sentences), no lists, no markdown, no emojis.
- Reply in the caller's language. Start in {LANG_NAME}. If the caller switches language, switch with them; mixing English
  words into Malayalam or Hindi the way callers do is fine. The speech recogniser often writes English words in
  Malayalam or Devanagari script, so judge the language by the words, not the script.
- Script: write Malayalam in Malayalam script (for example "നമസ്കാരം"), never romanised in Latin letters and never in
  Devanagari. Write Hindi in Devanagari. English words and the lender name may stay in Latin letters.
- Write amounts, account numbers, rates and dates exactly as the tools give them (for example "Rs 1,23,456",
  "GL-ABC-123456", "12.5%", "5 March 2027"); do not spell numbers out in words.
- If you do not know something, say so and offer a callback. Do not invent fees, dates or amounts.
- If the caller goes off-topic, say briefly that you can only help with this gold loan and bring them back."""


# Examples above are deliberately not any customer's numbers: with "4521" / "GL-KOC-104521" as examples, Gemini
# "corrected" a caller's 4512 to Anitha's real 4521 (T18, 2/2 voice runs; 3/5 Malayalam text runs).
GREETINGS = {  # fixed first line: no LLM call, and no wrong-script glyphs (text checks: 2 of 5 Gemini greetings had them)
    "ml-IN": "നമസ്കാരം, ഞാൻ {lender}-ൽ നിന്നുള്ള AI അസിസ്റ്റന്റ് ആണ്. {name} ആണോ സംസാരിക്കുന്നത്?",
    "en-IN": "Hello, I'm an AI assistant from {lender}. Am I speaking with {name}?",
    "hi-IN": "नमस्ते, मैं {lender} से AI असिस्टेंट बोल रही हूँ। क्या मेरी बात {name} जी से हो रही है?",
}

SCRIPTS = {"Devanagari": (0x0900, 0x097F), "Bengali": (0x0980, 0x09FF), "Gurmukhi": (0x0A00, 0x0A7F),
           "Gujarati": (0x0A80, 0x0AFF), "Oriya": (0x0B00, 0x0B7F), "Tamil": (0x0B80, 0x0BFF), "Telugu": (0x0C00, 0x0C7F),
           "Kannada": (0x0C80, 0x0CFF), "Malayalam": (0x0D00, 0x0D7F)}
OWN_SCRIPT = {"ml-IN": "Malayalam", "hi-IN": "Devanagari", "en-IN": None}


def foreign_scripts(text):
    """Indic scripts in a reply other than the session's own script and Malayalam (callers may switch ML<->EN)."""
    allowed = {OWN_SCRIPT[LANG], "Malayalam"}
    found = {}
    for ch in text or "":
        for name, (a, b) in SCRIPTS.items():
            if a <= ord(ch) <= b and name not in allowed:
                found.setdefault(name, []).append(ch)
    return {k: "".join(v)[:20] for k, v in found.items()}


# ---------------------------------------------------------------- logging
class ConvLog:
    def __init__(self, customer, label):
        CONV_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.path = CONV_DIR / f"{ts}_{customer}{'_' + label if label else ''}.jsonl"
        self.f = open(self.path, "a", encoding="utf-8")
        self.last_user = None
        self.turns = []

    def write(self, kind, **data):
        self.f.write(json.dumps({"t": round(time.time(), 3), "kind": kind, **data}, ensure_ascii=False, default=str) + "\n")
        self.f.flush()

    def close(self):
        self.f.close()


def ms(v):
    return round(v * 1000) if isinstance(v, (int, float)) else None


# ---------------------------------------------------------------- agent
class GoldLoanAgent(Agent):
    def __init__(self, customer, log):
        super().__init__(instructions=instructions(customer))
        self.customer, self.log = customer, log
        self.attempts, self.verified = 0, False

    @function_tool()
    async def verify_account(self, context: RunContext, last4: str) -> str:
        """Check the last 4 digits of the loan account number that the caller said.

        Args:
            last4: the 4 digits the caller said, as digits, in the order said (e.g. "3456")
        """
        digits = re.sub(r"\D", "", last4.translate(str.maketrans("൦൧൨൩൪൫൬൭൮൯०१२३४५६७८९", "01234567890123456789")))
        if self.verified:
            return json.dumps({"verified": True, "loan": loan_facts(self.customer)})
        if self.attempts >= 3:
            self.log.write("verify", said=last4, digits=digits, result="locked")
            return json.dumps({"verified": False, "attempts_left": 0,
                               "instruction": "Share nothing. Offer a branch visit or a callback to the registered number."})
        self.attempts += 1
        ok = digits == self.customer["account_last4"]
        self.verified = ok
        self.log.write("verify", said=last4, digits=digits, attempt=self.attempts, result="ok" if ok else "fail")
        if ok:
            return json.dumps({"verified": True, "loan": loan_facts(self.customer)})
        return json.dumps({"verified": False, "attempts_left": 3 - self.attempts,
                           "instruction": "Do not reveal the correct digits or any loan detail."})

    @function_tool()
    async def record_outcome(self, context: RunContext, outcome: str, summary: str, amount_inr: int | None = None,
                             date: str | None = None) -> str:
        """Record what was agreed, just before the closing summary.

        Args:
            outcome: one of renewal, part_payment, callback, branch_visit_topup, not_verified, no_decision
            summary: the one-sentence summary you will say
            amount_inr: amount agreed, if any
            date: date agreed, if any
        """
        self.log.write("outcome", outcome=outcome, summary=summary, amount_inr=amount_inr, date=date,
                       verified=self.verified)
        return "Recorded. Now say the one-sentence summary."

    async def tts_node(self, text, model_settings):
        if SPOKEN_NUMBERS:
            async def converted():
                async for chunk in text:
                    yield spoken_numbers(chunk)
            text = converted()
        async for frame in Agent.default.tts_node(self, text, model_settings):
            yield frame


def make_llm(on_switch=None):
    """Primary Gemini with a fallback: free-tier Gemini returned 504 DEADLINE_EXCEEDED in text checks."""
    models = [google.LLM(model=m, temperature=0.3, thinking_config={"thinking_level": THINKING_LEVEL})
              for m in (LLM_MODEL, BACKUP_LLM)]
    fb = llm_mod.FallbackAdapter(models, attempt_timeout=LLM_ATTEMPT_TIMEOUT_S)
    if on_switch:
        fb.on("llm_availability_changed", lambda ev: on_switch(ev.llm.model, ev.available))
    return fb


def session_config(account, label):
    return {"customer": account, "label": label, "stt_language": LANG, "llm": LLM_MODEL, "backup_llm": BACKUP_LLM,
            "thinking": THINKING_LEVEL, "tts_model": TTS_MODEL, "voice": VOICE, "tts_transport": TTS_TRANSPORT,
            "bias": BIAS, "bias_words": BIAS_WORDS if BIAS else [], "min_silence_ms": MIN_SILENCE,
            "spoken_numbers": SPOKEN_NUMBERS}


def build_session(log):
    """The voice pipeline and its per-turn logging. Shared by the console entrypoint and scripts/self_play.py."""
    tts = gnani.TTS(model=TTS_MODEL, voice=VOICE, language=LANG, sample_rate=22050,
                    synthesize_method="sse" if TTS_TRANSPORT == "sse-sentence" else "websocket")
    if TTS_TRANSPORT == "sse-sentence":
        tts = lk_tts.StreamAdapter(tts=tts, sentence_tokenizer=tokenize.blingfire.SentenceTokenizer())

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=gnani.STT(language=LANG),
        llm=make_llm(lambda model, ok: log.write("llm_availability", model=model, available=ok)),
        tts=tts,
    )
    pending = {}  # metrics of the last user turn, waiting for the agent reply

    @session.on("conversation_item_added")
    def _item(ev):
        item = ev.item
        if getattr(item, "type", "message") != "message":
            return
        m = dict(item.metrics or {})
        rec = {"role": item.role, "text": item.text_content, "interrupted": item.interrupted,
               "metrics_ms": {k: ms(v) for k, v in m.items() if k not in ("started_speaking_at", "stopped_speaking_at")}}
        if item.role == "assistant" and (bad := foreign_scripts(item.text_content)):
            rec["foreign_script"] = bad
        log.write("message", **rec)
        if item.role == "user":
            pending.clear()
            pending.update(user=item.text_content, transcription_delay_ms=ms(m.get("transcription_delay")),
                           end_of_turn_delay_ms=ms(m.get("end_of_turn_delay")))
        elif item.role == "assistant":
            turn = {**pending, "agent": item.text_content, "interrupted": item.interrupted,
                    "llm_ttft_ms": ms(m.get("llm_node_ttft")), "tts_ttfb_ms": ms(m.get("tts_node_ttfb")),
                    "e2e_ms": ms(m.get("e2e_latency"))}
            log.write("turn", **turn)
            log.turns.append(turn)
            pending.clear()

    @session.on("user_input_transcribed")
    def _transcribed(ev):
        if ev.is_final:
            log.write("stt_final", text=ev.transcript, language=str(ev.language) if ev.language else None)

    @session.on("agent_false_interruption")
    def _false_int(ev):
        log.write("false_interruption")

    @session.on("error")
    def _error(ev):
        log.write("error", source=type(ev.source).__name__, error=str(ev.error)[:500])

    return session


def greeting(customer):
    return GREETINGS[LANG].format(lender=LENDER, name=customer["customer_name"])


def finish_log(log):
    rows = [t for t in log.turns if t.get("e2e_ms") is not None]
    log.write("session_end", turns=len(log.turns))
    log.close()
    print(f"\n--- timing per turn (ms) — log: {log.path.relative_to(ROOT)}")
    print(f"{'#':>2} {'STT final':>9} {'end-of-turn':>11} {'LLM TTFT':>8} {'TTS TTFB':>8} {'speech->agent':>13}")
    for i, t in enumerate(rows, 1):
        print(f"{i:>2} {t.get('transcription_delay_ms')!s:>9} {t.get('end_of_turn_delay_ms')!s:>11} "
              f"{t.get('llm_ttft_ms')!s:>8} {t.get('tts_ttfb_ms')!s:>8} {t.get('e2e_ms')!s:>13}")


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    account = os.environ.get("GL_CUSTOMER") or sys.exit("pass --customer ACCOUNT")
    customer = load_customer(account)
    label = os.environ.get("GL_LABEL", "")
    log = ConvLog(account, label)
    log.write("session_start", **session_config(account, label))
    session = build_session(log)

    async def _on_close():
        finish_log(log)

    ctx.add_shutdown_callback(_on_close)
    await session.start(agent=GoldLoanAgent(customer, log), room=ctx.room)
    await session.say(greeting(customer))


if __name__ == "__main__":
    cli.run_app(server)
