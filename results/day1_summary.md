# Day 1 summary — Gnani developer path (25 Oct 2026)

Every number below comes from a run in this folder; source files are named next to each table.
All inputs filled in on 25 Oct (signup time, listening notes, dashboard credits).

## What was measured

| Area | What | Runs | Source |
|---|---|---|---|
| STT REST | 11 clips (C3, N3, M3 not recorded) × 3 formats (no `format`, `verbatim`, `transcribe`) | 33 requests, 250 s audio | `stt_rest_20261025_161827.json`, `score_20261025_161827.md` |
| STT realtime | 11 clips × 3 runs, 16 kHz PCM, 1024-byte frames, 32 ms pace, 4 s silence pad | 33 sessions, ~382 s streamed | `stt_stream_20261025_162936.json` |
| TTS REST | EN + ML-EN lines × Timbre v2.5 and v3.0 | 4 requests | `tts_20261025_163012.json`, `tts/` |
| TTS SSE | EN line, v2.5 Kaveri | 10 runs | `tts_20261025_163012.json` |
| Voice clone | Embedding from my 9.2 s sample, then EN line with `vachana-vc-v1` | 1 run | `tts_20261025_163120.json` |

**Volume sent today** (counted from the scripts): about 670 s of audio to STT (REST + stream, including tests and silence padding) and 3,547 characters to TTS.
**Credits used:** not visible through the API (no usage headers or fields). 13.36 credits (₹13.36) of 5,000 per the usage dashboard: STT 4.29, TTS 9.07; 87 requests (71 STT, 16 TTS), ₹0.15 per request

## STT accuracy by type (REST, `format=verbatim`)

Pooled = total errors / total reference words. "Lenient" compares numbers by value and counts English words written in Malayalam script as correct (list: `data/script_variants.csv`).

| Type | Clips | Word error rate, strict | Word error rate, lenient | Character error rate | Numbers correct |
|---|---|---|---|---|---|
| Clean | C1, C2 | 0.059 (2/34) | 0.065 (2/31) | 0.015 | 1/1 |
| Noisy | N1, N2 | 0.088 (3/34) | 0.097 (3/31) | 0.036 | 1/1 |
| Mixed | M1, M2 | 0.650 (13/20) | 0.100 (2/20) | 0.018 | — |
| Numbers | D1, D2, D3 | 0.193 (11/57) | 0.029 (1/34) | 0.020 | 6/7 |
| Phone | P1, P2 | 0.447 (17/38) | 0.174 (4/23) | 0.069 | 1/2 |

- **English** clips (C1, N1, D1, D2) had **0 recognition errors**, even with noise.
- **Numbers missed (2 of 11 expected values across all clips):** D3 "ഒൻപതര ശതമാനം" (9.5%) → "ഒൻപതായിരം" / "9,000%"; P1 account number 7309418265 → 730941**2**265.
- **Mixed clips:** every English word was recognised, but 0 of 11 were written in Latin script; all came back in Malayalam script. The remaining errors are Malayalam word-joining (എത്രയാണെന്നറിയില്ല).
- **Meaning-changing errors:** N2 "അറിയണം" (want to know) → "അറിയാം" (I know); P2 "renew" → "review" (REST only; the realtime stream got it right 3/3).
- The numbers result was identical in all three formats. With no `format` field, output is the same as `transcribe` (digits), not verbatim as documented.

## Latency

| Measure | Median | Range | Runs |
|---|---|---|---|
| STT REST round trip (7–17 s clips) | 721 ms | 527–1,994 ms | 33 |
| STT REST server-reported `end_to_end_latency` | 244 ms | 105–337 ms | 33 |
| STT realtime: end of speech → final transcript | 1,023 ms | 848–1,610 ms | 30 (P1 excluded) |
| STT realtime: server-reported `latency` | 234 ms | 54–298 ms | 33 |
| STT realtime: connect → `connected` | 524 ms | 433–2,689 ms | 33 |
| TTS SSE time to first audio (234 chars) | 419 ms | 353–481 ms | 10 |
| TTS SSE full audio delivered (21.9 s audio) | 2,309 ms | — | 10 |
| TTS REST v2.5 / v3.0, EN line | 4,936 / 4,290 ms | — | 1 each |
| Voice-clone TTS, EN line | 20,640 ms | — | 1 |

The realtime "end of speech" delay includes the default 500 ms VAD silence wait. End of speech is estimated from audio energy. P1 is excluded because its phone-line hiss defeats that estimate (friction #29).

## TTS files to listen to (`results/tts/`)

1. `20261025_163012_timbre-v2.5_EN_Kaveri.wav` — EN, v2.5
2. `20261025_163012_timbre-v3.0_EN_Tarika.wav` — EN, v3.0 (9 s longer than v2.5 for the same text)
3. `20261025_163012_timbre-v2.5_ML-EN_Reshma.wav` — Malayalam–English, v2.5
4. `20261025_163012_timbre-v3.0_ML-EN_Tarika.wav` — Malayalam–English, v3.0
5. `20261025_163012_vachana-vc-v1_EN_myvoice.wav` — my cloned voice, EN

Check: GL-KOC-104521, Rs 1,85,000, 28 October 2026, Rs 1,95,165, Rs 10,165, 10.5%, 18.0 grams, PLC-2291-XB, and whether "gold loan" / "due date" switch language cleanly in the ML-EN line.

## Measurement rows

| Measurement | Result |
|---|---|
| Signup to first transcript | About 10 min (first API transcript returned 907 ms after the request) |
| Word errors — clean | Strict 0.059 (2/34 words); lenient 0.065; English clean 0/24 |
| Word errors — noisy | Strict 0.088 (3/34); lenient 0.097; English noisy 0/24; Malayalam noisy 3/10 |
| Word errors — mixed | Strict 0.650 (13/20, script); lenient 0.100 (2/20); 11/11 English words right, 0/11 in Latin script |
| Numbers misheard | 2 of 11 expected values (D3 9.5% → 9,000%; P1 one digit of the account number) |
| Streaming transcript delay | Median 1,023 ms from end of speech (848–1,610, n=30); server-side 234 ms |
| TTS time to first audio | Median 419 ms (353–481, n=10, SSE) |
| TTS numbers misread | Standard voices (v2.5 and v3.0, EN and ML-EN): 0 misreads heard; language switches seamless. Cloned voice: several mismatches, sounds wrong in multiple places |

## Top 5 friction log entries

1. **#20 Major:** Malayalam "nine and a half percent" transcribed as "9,000%" in all 3 formats. An implausible interest rate passes through without a flag.
2. **#21 Major:** over a phone line, 1 of 10 account-number digits was wrong; the same words recorded directly were perfect.
3. **#18 Major:** the default STT `format` is ITN (digits), not verbatim as documented. Same on the realtime stream (#28).
4. **#9 Major:** realtime STT has no end-of-stream / flush message; the client must pad silence to get the last transcript.
5. **#31 Major:** the voice-clone embedding response shape matches neither documented example, so code written to the docs fails.

Worked well: first STT and TTS calls succeeded on the first try (#13, #15); English accuracy, including under noise, a 10-digit ID and "one lakh eighty-four thousand five hundred" (#19); SSE first audio in about 0.4 s (#34); 89 API calls today, none failed (HTTP 200 / clean WebSocket sessions).
