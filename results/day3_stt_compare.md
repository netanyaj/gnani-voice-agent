# STT: Gnani (Prisma v2.5) vs Sarvam (saaras:v4), Day 1 clips

Sources: `score_20261025_161827.csv`, `score_sarvam_stt_20261026_232914.csv`. Same 11 clips, same language codes, same scorer (`scripts/score.py`), one request per clip per mode. Pooled = errors / reference words.

### Headline: verbatim (Gnani format=verbatim vs Sarvam mode=verbatim)

| Type | Clips | WER strict Gnani | WER strict Sarvam | WER lenient Gnani | WER lenient Sarvam | Numbers Gnani | Numbers Sarvam |
|---|---|---|---|---|---|---|---|
| clean | 2 | 0.059 (2/34) | 0.029 (1/34) | 0.065 (2/31) | 0.032 (1/31) | 1/1 | 1/1 |
| noisy | 2 | 0.088 (3/34) | 0.147 (5/34) | 0.097 (3/31) | 0.161 (5/31) | 1/1 | 1/1 |
| mixed | 2 | 0.650 (13/20) | 0.550 (11/20) | 0.100 (2/20) | 0.000 (0/20) | — | — |
| numbers | 3 | 0.193 (11/57) | 0.175 (10/57) | 0.029 (1/34) | 0.000 (0/34) | 6/7 | 7/7 |
| phone | 2 | 0.447 (17/38) | 0.395 (15/38) | 0.174 (4/23) | 0.000 (0/23) | 1/2 | 2/2 |
| ALL | 11 | 0.251 (46/183) | 0.230 (42/183) | 0.086 (12/139) | 0.043 (6/139) | 9/11 | 11/11 |

### Defaults (Gnani no format field vs Sarvam mode=transcribe)

| Type | Clips | WER strict Gnani | WER strict Sarvam | WER lenient Gnani | WER lenient Sarvam | Numbers Gnani | Numbers Sarvam |
|---|---|---|---|---|---|---|---|
| clean | 2 | 0.176 (6/34) | 0.118 (4/34) | 0.065 (2/31) | 0.000 (0/31) | 1/1 | 1/1 |
| noisy | 2 | 0.206 (7/34) | 0.206 (7/34) | 0.097 (3/31) | 0.097 (3/31) | 1/1 | 1/1 |
| mixed | 2 | 0.650 (13/20) | 0.550 (11/20) | 0.100 (2/20) | 0.000 (0/20) | — | — |
| numbers | 3 | 0.544 (31/57) | 0.491 (28/57) | 0.088 (3/34) | 0.000 (0/34) | 6/7 | 7/7 |
| phone | 2 | 0.658 (25/38) | 0.579 (22/38) | 0.174 (4/23) | 0.000 (0/23) | 1/2 | 2/2 |
| ALL | 11 | 0.448 (82/183) | 0.393 (72/183) | 0.101 (14/139) | 0.022 (3/139) | 9/11 | 11/11 |

### Gnani's misses, clip by clip (verbatim)

| Clip | What was said | Gnani | Sarvam |
|---|---|---|---|
| D3 | ഒൻപതര ശതമാനം (9.5%) | lenient WER 0.143; numbers 210000:OK; 9.5:MISS; “എനിക്ക് രണ്ട് ലക്ഷത്തി പതിനായിരം രൂപ വേണം പലിശ ഒൻപതായിരം ശതമാനം” | lenient WER 0.0; numbers 210000:OK; 9.5:OK; “എനിക്ക് രണ്ട് ലക്ഷത്തി പതിനായിരം രൂപ വേണം പലിശ ഒൻപതര ശതമാനം” |
| P1 | 7 3 0 9 4 1 8 2 6 5 over a phone line | lenient WER 0.077; numbers 7309418265:MISS; 184500:OK; “my loan account number is seven three zero nine four one two two six five and the outstanding amount is one lakh eighty four thousand five hundred rupees” | lenient WER 0.0; numbers 7309418265:OK; 184500:OK; “My loan account number is seven three zero nine four one eight two six five and the outstanding amount is one lakh eighty four thousand five hundred rupees” |
| P2 | renew (phone line) | lenient WER 0.3; numbers —; “എൻ്റെ ഗോൾഡ് ലോൺ റിവ്യൂ ചെയ്യണം പക്ഷേ ഇൻട്രസ്റ്റ് റേറ്റ് എത്രയാണെന്നറിയില്ല” | lenient WER 0.0; numbers —; “എന്റെ ഗോൾഡ് ലോൺ റിന്യൂ ചെയ്യണം പക്ഷേ ഇൻട്രസ്റ്റ് റേറ്റ് എത്രയാണെന്ന് അറിയില്ല” |
| N2 | അനിത … അറിയണം (noisy) | lenient WER 0.3; numbers —; “നമസ്കാരം എൻ്റെ പേരാണിതാ എൻ്റെ സ്വർണ്ണ വായ്പയുടെ പലിശ എത്രയാണെന്ന് അറിയാം” | lenient WER 0.4; numbers —; “നമസ്കാരം എന്റെ പേര് അനത എന്റെ സ്വർണ്ണവായ്പയുടെ പലിശ എത്രയാണെന്ന്” |

### Script of English words in mixed / phone Malayalam clips (M1, M2, P2: 16 English words)

| Output | Latin script |
|---|---|
| Gnani verbatim | 0/16 |
| Gnani default | 0/16 |
| Sarvam verbatim | 0/16 |
| Sarvam transcribe | 0/16 |
| Sarvam codemix | 16/16 |
