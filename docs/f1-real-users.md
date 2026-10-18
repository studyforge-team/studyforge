# F1: real users (3–5 classmates on a real deadline)

Done when: a log of what they did and what broke (this file's template, filled in, kept by P5).
Due 22 Oct. Owner: P5 (Supreeth). Feeds F2 (final fixes).

## Before inviting anyone (blockers)

1. **Live app, not the demo.** Render needs `DATABASE_URL`, `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` (Render dashboard only, never in the repo or a chat). Without them
   notices, uploads, reminders and check-ins do not save. Vercel needs `VITE_API_URL`,
   `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`; without them the site silently runs the
   demo/mock. Values only in the dashboards, never in the repo or a chat.
2. **The model (Nebius credits).** Needs `TF_API_KEY` on Render. Without it "Ask" answers nothing and quizzes cannot be made.
   If credits are late, run the session anyway on what works and log "Ask not tested".
3. **Phone reminders (optional):** the three `VAPID_*` variables on Render (D1b).
4. Try it yourself first on https://studyforge-ten-alpha.vercel.app : sign in with Google, save
   and delete a test notice, open ChemLab. Fix or note anything broken before inviting anyone.

## Who and when

- 3–5 chemical-engineering classmates with a real deadline in the next week (an assignment,
  a lab report, a quiz). Not teammates.
- One 20–30 minute session each, in person or on a call with screen sharing, on their own phone.
  Then let them use it on their own until the deadline and ask what happened.

## Consent (read it out; note "yes" in the log)

> "StudyForge is our hackathon project. I'll watch you use it and write down what works and what
> breaks. I won't write down your name, your notes or anything personal; you'll be P1–P5 in my
> log. Anything you save in the app you can delete yourself (Your data → Delete my account).
> You can stop at any time. OK?"

## What to ask them to do (in this order)

1. Open the site on their phone, sign in with Google (or "Try demo").
2. **Notices:** share a real class WhatsApp message about their deadline to StudyForge
   (Android: install the app first, browser menu → Install app; iPhone: paste it instead).
3. **Phone reminders** (only if the VAPID keys are on Render; otherwise skip and log "not live"):
   Today → Turn on phone reminders → Send a test. Did it arrive? Tap it. Tapping opens the prep
   pack page for that deadline.
4. **Ask:** one real question from their subject (photo or typed). Did the confirm screen read it
   right? Is the answer right? Did they trust the numbers?
5. **Quiz:** open the prep pack for their deadline from a reminder link (`#prep/…`); if
   reminders are not live, use the Quiz page (fixed topic: Reactor basics); answer it;
   check-in later.
6. **ChemLab:** one template relevant to them; change an input; open the drawing.
7. Their own words: "What would make you use this before your next deadline?"

Do not help unless they are stuck for over a minute; write down where they got stuck.

## Rules (AGENTS.md rule 13)

- Never paste their messages, notes, photos or answers into ChatGPT, Claude or any assistant,
  including this log's contents. Summarise in your own words.
- No names, roll numbers, phone numbers or screenshots with personal data in the log or the repo.
- Real notices they share are their data: do not copy them into tests or `tests/golden/`
  (T3 labelled data is a separate, consented collection).

## Log template (copy once per person)

| Field | Entry |
|---|---|
| Person | P1 (consent: yes / date) |
| Phone and browser | e.g. Android 14, Chrome 141 |
| Deadline (kind, days away) | e.g. lab report, 4 days |
| Signed in with | Google / demo |
| Notice shared or pasted | worked / failed: what happened |
| Phone reminder test | arrived / not / not live; tap opened the right page? |
| Ask: question type | photo / typed; subject area |
| Ask: read correctly? answer correct? | yes / no, what was wrong |
| Quiz and check-in | worked / failed |
| ChemLab | template, worked / failed |
| Stuck points (time, where) | |
| Errors seen (exact message on screen) | |
| Their words (paraphrased) | |
| Bugs to file (one line each, for F2) | |

## After the sessions

- One line per bug in the team chat with the person code (P1–P5), the step and the exact
  on-screen message; each becomes an F2 fix or a "known limit" in the README.
- Count for the Devpost text (F8): how many finished each step, without names.
