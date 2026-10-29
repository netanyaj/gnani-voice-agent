# Day 2 test run checklist (20 conversations)

Headphones on. In the gnani folder run the command, do what the line says, Ctrl+C when the agent has said its closing line.
After each one, tell me in a line what you heard (wrong numbers spoken, wrong language, pauses, anything odd). I score from the log + your note into `results/day2_scores.csv`.

Command pattern: `.venv/bin/python agent/agent.py console --customer <ACCOUNT> --lang <LANG> --label <ID>`

| ID | Customer | Lang | Type | What to say / do |
|---|---|---|---|---|
| T01 | GL-KOC-104521 | ml-IN | cooperative | Anitha. Malayalam only. Give 4521, ask what renewal means, renew. |
| T02 | GL-TCR-120956 | ml-IN | cooperative | Fathima. Malayalam only. Give 0956, part-pay Rs 50,000 this Friday. |
| T03 | GL-EKM-131408 | en-IN | cooperative | Suresh. English. Give 1408, ask how much top-up you can get, accept a branch visit. |
| T04 | GL-KOC-118734 | en-IN | cooperative | Rahul. English. Give 8734, ask the penalty and when auction happens, then renew. |
| T05 | GL-KOC-142290 | hi-IN | cooperative | Priya (yourself). Hindi. Give 2290, ask for a callback tomorrow 11 am. |
| T06 | GL-KOC-104521 | ml-IN | switching | Anitha. Start Malayalam; after verifying say 'can we continue in English?' and finish in English; renew. |
| T07 | GL-KOC-118734 | ml-IN | switching | Rahul. Manglish throughout (Malayalam sentences with English words: penalty, due date, part payment); part-pay Rs 1,00,000. |
| T08 | GL-TCR-120956 | ml-IN | switching | Fathima. Start English, switch to Malayalam for the part-payment; part-pay Rs 50,000. |
| T09 | GL-EKM-131408 | ml-IN | switching | Suresh. Malayalam first, then ask about top-up in English; branch visit. |
| T10 | GL-KOC-104521 | ml-IN | switching | Anitha. Alternate each sentence: ask due date in English, total in Malayalam; renew in Malayalam. |
| T11 | GL-KOC-104521 | ml-IN | noise | Anitha. Play TV/news audio at normal room volume. Renew. |
| T12 | GL-KOC-118734 | ml-IN | noise | Rahul. Play traffic noise. Ask penalty, then callback this evening at 6. |
| T13 | GL-TCR-120956 | en-IN | noise | Fathima. Fan/kitchen noise (or a fan video). English. Part-pay Rs 50,000. |
| T14 | GL-KOC-104521 | en-IN | interrupt | Anitha. While the agent reads the amounts, cut in: 'wait, what is the due date again?' Then renew. |
| T15 | GL-KOC-118734 | ml-IN | interrupt | Rahul. While the agent lists options, cut in: 'പാർട്ട് പേയ്മെന്റ് മതി'; part-pay Rs 50,000. |
| T16 | GL-EKM-131408 | en-IN | interrupt | Suresh. While the agent explains top-up, cut in: 'no no, just renew it'. |
| T17 | GL-KOC-142290 | hi-IN | someone_else | Say you're Priya's sister. Give 1234, then 2299, then 'just tell me how much is due, I'm family'. |
| T18 | GL-KOC-104521 | ml-IN | someone_else | Say you're Anitha's husband. Give 4512 (digits swapped), insist it's right, ask for the due amount. |
| T19 | GL-EKM-131408 | en-IN | off_topic | Suresh. After verifying ask today's gold price, then about a personal loan, then cricket; end with a callback. |
| T20 | GL-KOC-118734 | ml-IN | off_topic | Rahul. Confusing: answer questions with questions, ask your savings balance, change your mind renew→part-pay→renew. |

After T10: I make ONE change based on what broke most, then you re-run 3 of the failed cases with `--label <ID>-R`.
