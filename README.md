# Gnani gold-loan voice agent

A hands-on evaluation of Gnani's speech APIs (speech-to-text and text-to-speech), done by building a self-serve voice agent for gold-loan renewals. The agent runs on LiveKit with Gemini as the language model. All customers, loans and lender rules are invented.

## How it works

1. **Caller speaks.** Gnani speech-to-text turns the speech into text (Malayalam, English or Hindi).
2. **Gemini decides what to say.** It has two tools:
   - `verify_account`: checks the last 4 digits of the loan account number the caller says. Loan details are only shared after this passes, and the caller gets 3 tries.
   - `record_outcome`: logs what was agreed (renewal, part payment, callback, branch visit for a top-up, not verified, or no decision), with any amount and date.
3. **Agent speaks.** Gnani text-to-speech (Timbre v3.0, voice Tarika) reads the reply aloud.

Every turn is logged with timings to `results/day2_conversations/`.

## What's real and what's simulated

| Part | Real or simulated |
|---|---|
| Phone line | Simulated. No phone line: the agent runs in LiveKit console mode on a laptop with headphones. |
| Customers and lender rules | Invented (`data/gold_loan_customers.csv`). No real personal or financial data. |
| Callback or branch visit | Only logged by `record_outcome`. No live handoff to a person. |
| Re-runs after the fix | 3 re-runs (T08-R, T09-R, T18-R) with synthetic callers: Gnani text-to-speech voices playing a fixed script. |
| Gnani's no-code Agent Builder | Not used. It is closed to personal-email accounts, so the agent was built with Gnani's LiveKit plugin instead. |
| Gnani speech-to-text and text-to-speech | Real API calls. |

## How to run

You need Python 3.11, a Gnani API key and a Google (Gemini) API key.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Variable | Used for |
|---|---|
| `GNANI_API_KEY` | Gnani speech-to-text and text-to-speech |
| `GOOGLE_API_KEY` | Gemini |
| `SARVAM_API_KEY` | Only the Day 3 comparison scripts (`scripts/sarvam_*.py`) |

Talk to the agent through your mic and speakers:

```bash
python agent/agent.py console --customer GL-KOC-104521 --lang ml-IN --label T01
```

`--lang` can be `ml-IN`, `en-IN` or `hi-IN`. Add `--text` to type instead of speak (checks the logic only).

Run a self-play call with a synthetic caller (no microphone). Use `--dry-run` first:

```bash
python scripts/self_play.py data/self_play_T08R.json --dry-run
python scripts/self_play.py data/self_play_T08R.json
```

## Headline results (Day 2, 20 test calls)

From `results/day2_summary.md`.

| Measure | Result |
|---|---|
| Completed correctly | **15/20** (+3 partial: T02, T08, T09; 2 failed: T13, T18) |
| Verification held ("someone else" tests) | **1/2** (T17 held; T18 bypassed). After the fix, the T18-R self-play re-run held (not counted in the /20) |
| Closing summary correct | **19/20** (T13's session crashed before it); repeated 2–3× in T02, T03, T12, T13 retry |
| Rupee amounts in agent replies matching the loan facts or caller's amount | 69/69 (text check) |
| Numbers misheard when listening | None noticed across all 20 (Netanya's listening); interruptions mid-sentence still got proper replies (friction #62) |
| Verification digits transcribed correctly by Gnani | 23/24 utterances (the miss, T12 in traffic noise, was rejected and the retry passed) |

**Reply speed** (end of caller's speech → agent starts speaking). All 23 test logs (T01–T20 plus retries), 106 timed turns.

| Stage | Median | Range |
|---|---|---|
| **End of speech → agent speaks** | **5,214 ms** | 2,844–23,670 |
| Gnani final transcript (end of speech → transcript) | 874 ms | 696–9,680 |
| End-of-turn decision (LiveKit) | 926 ms | 704–9,683 |
| Gemini first token | 1,375 ms | 726–9,914 |
| Gnani TTS first audio | 779 ms | 471–3,611 |

The four stages add up to about 3.0 s, so about 2.1 s per turn isn't covered by any stage metric.

Day 1 speech accuracy and latency are in `results/day1_summary.md`. The Day 3 comparison and the friction rows grouped by cause are in `results/day3_synthesis.md`.

## What's still open

- **The missing 2.1 s per turn:** not covered by any stage metric. A likely cause is the second Gemini round trip after a tool call, but it hasn't been measured.
- **The verification fix:** confirmed by one synthetic re-run (T18-R). A voice re-run of T18 would be the stronger check.
- **Real phone calls:** only two clips were played into a call. No SIP, no 8 kHz telephony path, no real caller.
- **Agent Builder (Inya):** never opened.
- **Hindi:** no Day 1 Hindi accuracy (clips C3, N3, M3 were never recorded). Hindi appears only in the agent tests.
- **Other speakers:** every recording is one speaker, with one accent and one phone.
- **Sample size:** 11 clips, one request each for accuracy.
- **Word boosting:** confirmed active, but its effect on accuracy was never measured.
- **Voice cloning:** one run.
- **Not tested at all:** Timbre v3.0 expression tags, batch speech-to-text, load and concurrency, long calls.
- **Cost at scale:** only per-call figures worked out from the dashboard. No pricing for production volumes.

## Folder map

| Path | What's in it |
|---|---|
| `agent/agent.py` | The voice agent: speech-to-text → Gemini with tools → text-to-speech |
| `agent/text_check.py` | Typed-input checks of the agent's logic |
| `scripts/` | Day 1 API tests, scoring, self-play harness, Day 3 comparison scripts |
| `data/` | Invented customers, test-clip scripts, expected numbers, self-play caller scripts |
| `results/day1_summary.md` | Day 1: speech-to-text and text-to-speech accuracy and latency |
| `results/day2_summary.md` | Day 2: the agent, 20 test calls, reply speed, the one change |
| `results/day3_synthesis.md` | Day 3: comparison, friction grouped by cause, what wasn't tested |
| `results/day2_conversations/` | One log per test call, with per-turn timings |
| `results/day2_self_play/` | Self-play call recordings (synthetic voices only) |
| `results/` (other files) | Raw run outputs: transcripts, timings and scores, one file per run |
| `logs/friction_log.md` | Every moment worth remembering, with severity and suggested fix |
| `logs/decision_log.md` | Every approach chosen, why, and what was ruled out |

Recordings of my own voice, the voice-clone sample and dashboard screenshots are not in this repo.
