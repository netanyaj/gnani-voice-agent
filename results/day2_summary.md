# Day 2 summary — gold-loan renewal voice agent on Gnani + LiveKit (25 Oct 2026)

Pipeline: Gnani STT (ml-IN / en-IN / hi-IN) → Gemini `gemini-3.5-flash-lite` (thinking low, fallback `gemini-3.1-flash-lite`) → Gnani TTS `timbre-v3.0` Tarika, LiveKit Agents 1.8.9 console mode, headphones.
Every number below comes from `results/day2_conversations/*_T*.jsonl` (scored with `scripts/day2_report.py`), `results/day2_scores.csv` and `results/day2_text_checks/`.

## Build

| Measure | Result |
|---|---|
| Agent build time | **About 2 hours** wall clock (18:16 start → 20:15 first correct spoken reply with loan facts). Active build work was about 24 min (18:16:14 → 18:40:09, when the agent was handed over for the voice test). |
| Timer marks (`day2_timer.md`) | Start 18:16:14 → packages 18:19:05 → first text reply 18:31:20 → first correct spoken reply with loan facts 20:15:09 |
| Credits used (dashboard, read 25 Oct 22:08) | Cumulative 62.58 (STT 7.10 / TTS 55.48, 261 requests). **Day 2 ≈ 49.22** (cumulative minus Day 1's 13.36): STT 2.81 / TTS 46.41, 174 requests (24 STT, 150 TTS) |

**What the ~1 h 44 min from first text reply (18:31:20) to first correct spoken reply (20:15:09) went on**, from the session transcript and file times:

| Time | What |
|---|---|
| 18:31–18:37 | Text-only logic checks (5 cases). Gemini wrote Malayalam greetings with Devanagari/Bengali words, and a stricter rule gave romanised Malayalam; fixed with a fixed `session.say` greeting and a wrong-script flag (friction #45) |
| 18:37–18:40 | Logs, requirements, mic/speaker check, timing report script; agent handed over at 18:40:09 |
| 18:40–20:14 | No build activity in the folder or the session (no file changes between 18:39:49 and 20:14:27): waiting for the voice smoke test |
| 20:14:27–20:15:09 | S1 started; first spoken reply 20:14:50, first with loan facts 20:15:09 |

So most of the gap was waiting for a human voice test, not fixing the agent. Everything before 18:31 (docs, install, and the setup friction: dead default TTS model #37, Gemini model choice #43, word boosting missing from the plugin #39) took 15 min.

**Credits per conversation (derived, not measured per call):** 49.22 Day 2 credits ÷ 25 Day 2 voice sessions (S1, S2, T01–T20 and retries) ≈ **1.97 credits per conversation**. That's an upper bound, because the Day 2 total also includes 4 STT probe sessions and a TTS model probe. TTS was 94% of it: 150 TTS requests against 148 agent replies in the logs, so about 0.31 credits per spoken reply (about 2.9 per 1,000 characters). The dashboard's ₹0.24 "per request" average hides this (friction #63).

## Reply speed (end of caller's speech → agent starts speaking)

All 23 test logs (T01–T20 plus retries), 106 timed turns.

| Stage | Median | Range |
|---|---|---|
| **End of speech → agent speaks** | **5,214 ms** | 2,844–23,670 |
| Gnani final transcript (end of speech → transcript) | 874 ms | 696–9,680 |
| End-of-turn decision (LiveKit) | 926 ms | 704–9,683 |
| Gemini first token | 1,375 ms | 726–9,914 |
| Gnani TTS first audio | 779 ms | 471–3,611 |

- The smoke test (n=12) had a median of 3,325 ms; the test run was slower.
- Malayalam turns hit LiveKit's 2.5 s end-of-turn maximum in 24 of 58 turns. English hit it in 3 of 38 and Hindi in 4 of 10 (friction #54).
- The four stages add up to about 3.0 s, so about 2.1 s per turn isn't covered by any stage metric. A likely candidate is the second Gemini round trip after a tool call; not measured.

## Results (20 tests)

| Measure | Result |
|---|---|
| Completed correctly | **15/20** (+3 partial: T02, T08, T09; 2 failed: T13, T18) |
| Verification held ("someone else" tests) | **1/2** (T17 held; T18 bypassed). After the fix, the T18-R self-play re-run held (not counted in the /20) |
| Closing summary correct | **19/20** (T13's session crashed before it); repeated 2–3× in T02, T03, T12, T13 retry |
| Rupee amounts in agent replies matching the loan facts or caller's amount | 69/69 (text check) |
| Numbers misheard when listening | None noticed across all 20 (Netanya's listening); interruptions mid-sentence still got proper replies (friction #62) |
| Verification digits transcribed correctly by Gnani | 23/24 utterances (the miss, T12 in traffic noise, was rejected and the retry passed) |

## Failure causes

| Group | What happened | Tests |
|---|---|---|
| Speech recognition (Gnani) | One digit misheard in traffic noise ("എട്ട്" → "ഇട്ടേഴ്"), caught by verification; "gold" → "goal"; "Rahul" → "ഷാഹുൽ"; English speech written in Malayalam script, after which the agent kept replying in Malayalam. None of these caused a failed conversation on its own. | T12, T19, T08, T09 |
| Language model (Gemini + my prompt) | **Verification bypass:** the caller's 4512 was sent to the tool as 4521, the example digits in my prompt; loan facts were read to the "husband". Also: "dueDate" said aloud; a reply truncated to "ടോ" after an error; repeated closing summaries; outcomes recorded on half a sentence. | T18, T08, T09, T02, T03, T05, T12, T13 |
| Voice output (Gnani TTS) | No misread numbers noticed when listening, in any of the 20. "flush audio emitter due to slow audio generation" appeared in most sessions. | — |
| Platform (LiveKit / plugin / network) | T13: Gemini and the Gnani STT socket failed together, and the session closed after 3 failed STT reconnects. Malayalam end-of-turn waits of 2.5 s. False interruptions in T08, T13 and T14. | T13, all ml-IN |

## The one change

**Change:** replaced the example numbers in the prompt and in the `verify_account` description with numbers no customer has. Old examples: "Rs 1,95,165", "GL-KOC-104521", "4521". New: "Rs 1,23,456", "GL-ABC-123456", "3456". Reason: T18 (decision log, 25 Oct).

| Check | Before | After |
|---|---|---|
| Text runs: caller says 4512 in Malayalam, verified anyway | 3/5 | 0/5 |
| Text runs: caller says 4512 in English, verified anyway | 0/5 | 0/5 |
| Text run: correct 4521 still verifies | 2/2 (Day 2 earlier) | 1/1 |
| T18 (husband, 4512) | 2/2 bypassed by voice | **T18-R (self-play, synthetic caller): held.** verify_account got "4512" on both attempts (T18 sent "4521"); both failed; "what's due?" was refused for security reasons; callback recorded with verified=false. No loan amount, due amount or date spoken |
| T08-R (self-play, synthetic caller) | T08 partial: said "dueDate" aloud, English answered in Malayalam | **Completed correctly.** No JSON key, no truncation, part-payment date recorded (31 Oct). English still answered in Malayalam (3/3 turns); summary said twice |
| T09-R (self-play, synthetic caller) | T09 partial: Gemini error, reply truncated to "ടോ", 23.7 s stall | **Completed correctly.** No errors or truncation; top-up refused without an amount, branch visit booked. English still answered in Malayalam (4/4 turns); summary said twice |

**Self-play re-runs (T08-R, T09-R, T18-R), with synthetic callers.** `scripts/self_play.py` runs the agent code from `agent/agent.py` unchanged (same prompt, tools, Gemini, Gnani STT/TTS, turn detection). The caller is Gnani Timbre v3.0 speech (Chetana for Fathima, Devansh for Suresh and for Anitha's husband), streamed as 16 kHz PCM at real-time pace into the same STT stream. Clean TTS audio is much easier for speech recognition than a real voice on a phone, so these runs test the agent and prompt, not recognition of human speech. The caller follows a fixed script and doesn't react to the agent. Each ran once with no harness failures. T18-R ran on 26 Oct, 01:29; Gnani's TTS REST took about 226 s per caller line that night (friction #68), but the audio was valid and the call itself ran normally (median 4,324 ms, n=5). Mixed call audio: `results/day2_self_play/*_call.wav`.

| Check (T08 → T08-R, T09 → T09-R) | Original | Re-run |
|---|---|---|
| Spoke a JSON key | 1 (T08) | 0 |
| Reply truncated / LLM error | 1 (T09) | 0 |
| English caller turns answered in English | 0 of 3 | 0 of 7 |
| Closing summary repeated | T08 no, T09 no | once in each (partly the script: the caller's "yes" arrived after the agent had already recorded) |
| End of speech → agent speaks, median | T08 4,830 ms (n=5); T09 8,536 ms (n=5) | T08-R 5,070 ms (n=6); T09-R 4,160 ms (n=6) |

Why the re-runs passed: what fixed T08 and T09 can't be pinned on the prompt change. Their failures (a spoken JSON key, a Gemini error) weren't verification failures, and one run each can't show the fix caused it. What the re-runs do show: English-in-Malayalam is consistent (friction #65), and with clean audio the pipeline completes both flows. T18-R is the one re-run that tests the prompt change directly, and it held (friction #67). It's one synthetic run, so a voice T18 would still be the stronger check. Credits for the three runs: not separately measured (the dashboard wasn't re-read); estimate before running was about 9 for T08-R/T09-R plus about 4–5 for T18-R.

## Takeaways (from Day 2 alone)

1. Gnani's speech parts held up: 23/24 spoken digit strings were right in Malayalam words, Manglish, Hindi and English. TV noise didn't hurt, and TTS first audio had a median of 779 ms.
2. The LiveKit plugin is where the friction was:
   - The default TTS model is dead (#37).
   - Word boosting and VAD aren't exposed (#39).
   - The whole reply is buffered before TTS (#42).
   - One dropped STT socket ends the call (#53).
3. Malayalam conversations are slower for reasons outside Gnani's models: turn detection (#54) and the LLM (#55).
4. In Malayalam calls, English speech comes back in Malayalam script, and the agent then never switches to English. That was 7 of 7 English turns in the self-play re-runs, and T08/T09 by voice (#58, #65). A language tag per transcript segment would let an agent follow the caller.
