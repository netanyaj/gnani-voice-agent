# Creator studio map — Gnani Text to Speech playground (27 Oct 2026)

A fact-finding pass, made by Claude in a browser, 13:05–13:18 IST. It's a map for a later hand-timed run. It isn't a judgement, and there's no task time here, because automation speed isn't a creator's speed. Screenshots are in this folder, numbered by step.

## Credits

| | Remaining (Usage page) | Consumed this period | Requests |
|---|---|---|---|
| Start (13:09) | **4,929.22** | 70.78 | 303 (STT 98 / TTS 205) |
| End (13:18) | **4,926.64** | 73.36 | 309 (STT 98 / TTS 211) |
| **This pass** | **2.58 credits** | | 6 TTS generations |

- **Precision:** the sidebar widget only ever shows "4.9k / 5k Left", so exact figures come from the Usage → Usage History table (`00_usage_credits_start.jpg`, `28_usage_credits_end.jpg`).
- **How studio generations are labelled:** the API Key ID column shows "playgr... usage", with model `timbre-v3.0`.
- **Billing rate:** ₹0.76 for 279 characters, which is ₹27 per 10,000 characters as on the Pricing page.
- **Tags are billed:** the 279 characters include the `<excited>` and `<whispers>` tags.

| Time | Characters | Credits | What |
|---|---|---|---|
| 13:10:58 | 279 | 0.76 | EN reel (voice silently reset to Avinash) |
| 13:12:04 | 279 | 0.76 | EN reel, Tarika |
| 13:13:40 | 168 | 0.46 | ML reel, Tarika |
| 13:14:27 | 134 | 0.37 | EN + ML in one box, Tarika |
| 13:15:54 | 52 | 0.15 | Number-heavy line, Tarika |
| 13:16:57 | 26 | 0.08 | Reload test, Avinash |

## 1. Route: from the marketing page to a usable studio

1. **`gnani.ai/resources/timbre-v3`, page loads** (`01_timbre_v3_page.jpg`).
   - A cookie banner covers the lower right corner. I clicked **Reject**.
   - The hero section offers "Get API Key →" and "Talk to Sales →". It has no "studio" button.
2. **Scroll to the voices grid** (`02_voices_grid_link.jpg`).
   - A "Now playing: Timbre v3.0 · Showreel" bar appeared at the bottom of the page without me pressing play.
   - A hover card for Kannada covered the "Try all 13 in the studio" link.
3. **Click "Try all 13 in the studio · app.gnani.ai →"**, which redirects to **sign-in** (`03_signin_redirect.jpg`).
   - The sign-in page is `iamportal.gnani.site`, realm `inya`, client `genvoice_frontend`.
   - It offers email and password, Google, Microsoft, and "New user? Register".
   - Your existing Gnani session wasn't recognised here.
   - The page doesn't say what the account is for. "Sign in to your account" is the only heading.
   - "Start creating for free →" (lower on the same page) points to the same URL; only the tracking tag differs.
4. **You signed in with Google**, which landed on **`app.gnani.ai/voice/text-to-speech`** (`04_studio_landing.jpg`).
   - **The page:** it's titled "Text to Speech" inside a console called **"Gnani APIs"**. The left nav lists Speech to Text, Text to Speech, Voice Cloning, API Keys, Usage, Billing, Pricing and Documentation.
   - **No onboarding:** there's no tour or welcome step. The box is pre-filled with a Hindi podcast sample that already uses tags.
   - **Clicks to a usable studio:** 1 click from the marketing page, plus the sign-in.

## 2. Studio controls

| Control | Where | What it does | Default |
|---|---|---|---|
| Model | Top left dropdown | Gnani Timbre v3.0 / Gnani Timbre v2.5 | **Timbre v3.0** |
| Audio Tags (marked "New") | Dropdown next to model | Searchable menu ("Search Emotions") of 13 tag buttons. Clicking one inserts the tag in lowercase (e.g. `<excited>`) at the cursor and keeps focus in the text box. | Closed |
| Clear | Top right of the editor | Empties the text box | — |
| Text box | Centre | Plain text with tags shown in orange. Typed tags (`<whispers>`) are highlighted like menu-inserted ones. | Hindi podcast sample with `<excited>`, `<yawns>`, `<laugh>` (327 characters) |
| Explore by scenario | Chips under the text box | Podcast Intro, Audiobook Narration, Explainer Video, Emotional Expression, Announcer Video, Product Demo, Customer Response Support, Random. These load sample scripts. | Podcast Intro highlighted |
| Character counter | Bottom left | "n/800 Characters" with a progress ring. Turns red over 800. Tags count. | 327/800 |
| Generate Speech | Bottom right | Generates and plays the audio. Disabled when the box is empty or over 800 characters. | — |
| Gender filter | Voice panel | All Genders / Male / Female | All Genders |
| **Language** | Voice panel | All Languages, Bengali, English, Gujarati, Hindi, Kannada, Malayalam, Marathi, Punjabi, Tamil, Telugu. **It sets the generation language, and replaces whatever is in the text box with that language's sample script** (see section 5). It doesn't filter the voices; all 13 show for every language. | **Hindi** |
| Persona filter | Voice panel | All Persona, Confident & Authoritative, Conversational, Expressive & Energetic, Professional, Warm & Empathetic | All Persona |
| Voice search | Voice panel | "Search Name, Tone or Language" | Empty |
| Voice list | Voice panel | 13 cards: name, gender, "Hindi +10" badge (tooltip lists all 10 languages), one-line style | **Avinash** selected |
| Result player | Bottom bar after generating | Play/pause, first ~40 characters of the text, voice name chip, download icon. **Only the latest result is kept.** | — |
| Feedback | Above the player | "Did the output meet your expectations?" with thumbs up and down, and a close button | — |
| Download | Player | Saves `generated-audio.wav` (same name every time) | — |

**Controls not in the studio:**
- Speed.
- Output format.
- Sample rate.
- Code-switch toggle.
- Expression intensity.
- History list.
- Project or save.
- Text normalisation preview.

I also checked the page code: none of these exist as hidden inputs or labels.

**Voice preview before generating:** none. I hovered over the cards and checked the page code: no play button and no `<audio>` element until you generate. **Day 1 friction #4 still holds.**

## 3. Voices and tags

### Voices (13)

All 13 say "Hindi +10" (Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati).

| Voice | Gender | Studio description |
|---|---|---|
| Avinash | Male | Professional, firm voice with deliberate pacing for collections and BFSI |
| Shivani | Female | Warm, patient, empathy-first voice for inbound customer support |
| Lakshmi | Female | Expressive, warm voice for storytelling and e-learning narration |
| Kalpana | Female | Empathetic, composed voice for customer care and insurance |
| Shubham | Male | Energetic, confident voice for outbound sales and lead qualification |
| Prakash | Male | Steady, deliberate voice for payment recovery and BFSI |
| Devansh | Male | Energetic, young conversational voice for sales and fintech |
| Yashraj | Male | Warm narrative voice for e-learning and IVR narration |
| Chetana | Female | Gentle, empathetic voice for healthcare and telecom customer service |
| Vasudha | Female | Expressive, composed voice for narration and e-learning |
| Harshad | Male | Professional, firm voice for collections and payment recovery |
| Riyaa | Female | Confident, lively voice for outbound sales and insurance |
| Tarika | Female | Warm, reassuring voice for banking and insurance customer care |

**How they're described:**
- 9 of the 13 descriptions name a contact-centre use: collections, BFSI, sales, customer support, IVR, payment recovery.
- None names a creator use such as reels, YouTube or podcasts.
- The marketing page casts several of them in creator roles: Tarika for reels, Shubham for YouTube, Riyaa for podcasts, Vasudha for audiobooks.

### Expression tags

| Tag | Web page (12) | Studio menu (13) |
|---|---|---|
| `<coughs>` | yes | yes |
| `<excited>` | yes | yes |
| `<exhales>` | yes | yes |
| `<giggle>` | yes | yes |
| `<laugh>` | yes | yes |
| `<pauses>` | yes | yes |
| `<shouting>` | yes | yes |
| `<sigh>` | yes | yes |
| `<slow>` | yes | yes |
| `<sniffles>` | yes | yes |
| `<whispers>` | yes | yes |
| `<yawns>` | yes | yes |
| `<clears throat>` | **no** | **yes**, shown as "<Clears throat>" |

**How to insert a tag:**
- **Audio Tags menu:** the button shows a capitalised label ("<Excited>"); the text gets lowercase `<excited>`.
- **Typing:** typing the tag yourself also works.

**What the studio doesn't explain:**
- Where a tag takes effect.
- How many tags are allowed.
- Whether tags work on Timbre v2.5.

The web page says "Twelve tags", and its hero also shows `<whispers>`, `<laugh>`, `<sigh>`, `<excited>`, `<pauses>` and `<giggle>`.

## 4. The task: the KochiGold reel

My placeholder → tag choices: `[excited]` → `<excited>` (inserted from the menu), `[whisper]` → `<whispers>` (typed), `[laugh]` → `<laugh>` (pasted). All are Timbre v3.0.

| File | Voice | Language setting | Text | Duration |
|---|---|---|---|---|
| `01_EN_avinash_unintended_voice.wav` | Avinash (not chosen; see below) | English | EN part, `<excited>` + `<whispers>` | 18.63 s |
| `02_EN_tarika_excited_whispers.wav` | Tarika | English | EN part, `<excited>` + `<whispers>` | 19.43 s |
| `03_ML_tarika_laugh.wav` | Tarika | Malayalam | ML part, `<laugh>` | 10.44 s |
| `04_MIXED_EN-ML_same_box_tarika.wav` | Tarika | Malayalam | `<excited>` EN sentence + ML sentence + "Borrow up to Rs 2,29,500 at 10.5% a year." | 11.36 s |
| `05_NUMBERS_EN_tarika.wav` | Tarika | English | "Rs 2,29,500 at 10.5% on 28 Oct 2026, ref PLC-2291-XB" | 12.32 s |

**Download format** (checked with ffprobe): every file is WAV, PCM 16-bit, **44,100 Hz, mono**. Each was saved as `generated-audio.wav` and renamed here.

**What happened along the way:**
- **Typing into the editor dropped characters** (`11_typed_text_dropped_chars.jpg`). I typed the EN part with automated keystrokes and 5 characters were lost: "Here's"→"Her's", "grams"→"rams", "to"→"o", "always"→"aways", "interest"→"interes".
  - The same automated typing into the voice search box lost nothing.
  - So the script editor is the part that drops characters, at least at automation speed. I can't say whether it happens at human typing speed.
  - Pasting worked cleanly, so every generation above used pasted text.
  - Pasting meant writing to your clipboard.
- **The voice reset to Avinash without telling me** (`12_generating_voice_reset_avinash.jpg`).
  - I selected Tarika, and the screenshot after typing still showed Tarika ticked.
  - Then I typed in and cleared the voice search box, and pasted the script.
  - The first generation then used Avinash; the player chip said "Avinash".
  - I didn't pin down which action caused the reset.
  - Changing the language also resets the voice to Avinash (section 5).
- **Language switch overwrote the script** when I moved from English to Malayalam for the ML part (section 5).
- **Mixed EN + ML in one box:** the studio accepted it with no warning and no code-switch option, and returned one 11.36 s file. I can't hear it.
  - The web page's code-switch (beta) list is Hindi, Bengali, Tamil, Telugu, Kannada and Punjabi + English. **Malayalam isn't on it.**
- **Download timing:**
  - While a clip plays, the download icon is greyed out.
  - One click about 10 s after Generate did nothing and showed nothing; a second click a few seconds later worked.

**Listen for:**
- **`02`:** does `<excited>` lift the opening and does `<whispers>` actually whisper "Pro tip…"? Are "Rs 2,29,500" (two lakh twenty-nine thousand five hundred), "10.5%" and "22-carat" read right?
- **`03`:** where does `<laugh>` land, and is the Malayalam natural?
- **`04`:** does the English sentence keep an English accent inside a Malayalam request, or get read with Malayalam phonetics? Is there a seam?
- **`05`:** check "28 Oct 2026" and "PLC-2291-XB". The web page claims "PLC-2291-XB" is read correctly on live calls.
- **`01` vs `02`:** same text, different voice. Useful if you want to compare voices.

## 5. Edge cases (one try each)

| Case | What happened | Screenshot |
|---|---|---|
| Empty text box | Clear empties it; counter "0/800 Characters"; **Generate Speech greyed out**. No message. | `10_empty_box_generate_disabled.jpg` |
| Long paste (2,000 characters of the EN script repeated) | Paste accepted in full; counter turns red: **"2000/800 Characters"**; Generate disabled. No message saying what to do, no cut-off marker, no "split into parts". I didn't generate. | `20_long_paste_2000_of_800.jpg` |
| Number-heavy line "Rs 2,29,500 at 10.5% on 28 Oct 2026, ref PLC-2291-XB" | Generated without issue: 52 characters, 0.15 credits, 12.32 s audio → `05_NUMBERS_EN_tarika.wav`. No normalisation preview, so you only find out by listening. | `21_numbers_generated.jpg` |
| Switching voice after generating | An orange warning appears: **"Voice changed. Generate again to hear Tarika"**, and Generate re-enables. The old clip stays in the player with its voice chip. | `14_voice_changed_warning.jpg` |
| Switching **language** with your own script in the box | **Your script is replaced by that language's sample script**, with no warning or confirmation. The voice also resets to Avinash ("Voice changed. Generate again to hear Avinash"). Cmd+Z then restored an *older* state (the hand-typed text with dropped characters), not the text I had just pasted. Happened 3 times (Hindi→English, English→Malayalam with my EN reel, Malayalam→English with the 2,000-character paste). | `08_…`, `16_language_switch_overwrites_script.jpg` |
| Browser back button mid-task | Back went to the previous page in the app (Usage). Forward returned to Text to Speech **with everything reset**: Hindi sample, Hindi, Avinash, no player. No "leave page?" warning. | `22_…`, `23_forward_work_lost.jpg` |
| Navigating via the sidebar (Usage → Text to Speech) | Same as back/forward: language back to Hindi, sample text restored. | — |
| Reload with a generated, undownloaded clip | **The text, settings and generated clip were all gone** after reload; the clip was paid for (0.08 credits) and is gone. No warning before unload. No history anywhere in the studio to recover it. | `24_…`, `25_after_reload_work_lost.jpg` |

## 6. Account-type limits and gating

- **Nothing in the TTS studio was greyed out, paywalled or marked business-only** for this personal Google account. Both models, all 13 tags, all 13 voices and all 10 languages worked or were selectable.
- **Voice Cloning** is marked **"Beta"**. It has its own text box (language dropdown, default Hindi), but **no model or Audio Tags dropdown**, plus "My Voices" with "+ Voice Clone". Not used.
- **Pricing page:**
  - "Pay only for what you use. No subscriptions. Credits never expire."
  - Credits are one-time purchases ("1 Credit = ₹1"); there's a "Contact Sales for Larger Credits" button.
  - TTS is "₹27.00 Per 10,000 Chars, 60 requests/minute".
  - The ₹1,000 example says "~3,70,370 Chars of TTS" and "60 Request of API".
- **Three different free-allowance statements:**
  - Timbre v3.0 web page: "Start with 2,500 free TTS minutes. No card needed."
  - Pricing FAQ: "You'll receive 60 free credits when you first sign up."
  - This account: 5,000 credits (sidebar "5k").
- **Workspace switcher:** the top-left switcher says "Gnani APIs". I didn't open it; Agent Builder is out of scope.

## GIF

`creator_studio_pass.gif`, 1440×727, 9.5 MB. **The recorder caps at 50 frames, so the GIF covers the start of the pass:** landing, sign-in redirect, studio controls and the first generations. It doesn't cover the whole route. The numbered screenshots cover every step.
