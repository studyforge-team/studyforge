# Plan v2: company OA practice + interview prep (ExxonMobil, Chevron, Reliance), 20 Oct

**Replaces v1.** The OA becomes a fixed question bank per company, drawn from publicly shared candidate experiences. It is not AI-generated.
**Start trigger:** Supreeth says "start OA plan". Build without questions; the defaults are below.
**Time:** about 4 h wall-clock. **Workers:** 3 Sonnet research workers (1 per company) + 2 Sonnet build workers; Opus reviews.
**Credits used by the app:** 0. No AI calls at runtime.

## What the student sees
1. **OA Prep** has 2 tabs: "Coding" (today's page, unchanged) and **"Company OA"**.
2. **Company OA:**
   - a search box and company cards (ExxonMobil, Chevron, Reliance Industries); pick one.
   - The company screen shows its OA pattern (sections, question counts, usual duration), "Suggested time: N min (keep time yourself)", and a **Start** button.
3. **Exam mode:**
   - **15 questions drawn at random** from that company's bank (a new mix each time), one at a time;
   - Next / Previous; pick an answer per question;
   - **no answers shown until the end.** No timer.
4. **Submit:**
   - score shown in marks and %;
   - **a review of every question**: your answer, the correct answer, a short explanation.
5. **Progress:** the attempt is saved as topic **"OA: ExxonMobil"** (and so on), so it appears in **My progress** with the graph and the improving / steady / dropping label, like the quiz.
6. **Interview Bank** gets a **Field** switch, "Chemical" (default) or "Computer science" (existing, unchanged). Chemical shows one card per company:
   - **Process:** the rounds in order;
   - **Technical questions:** about 10, each with a model answer;
   - **HR / behavioural questions:** about 6, with how to answer (STAR method);
   - **How to present yourself:** what they look for (safety mindset, plant/internship examples, fundamentals), dress and conduct;
   - **Tips**;
   - a **"Practice this company's OA"** button.
7. Every company screen shows: *"Compiled and paraphrased from publicly shared candidate experiences. Not official; actual tests may differ."* The source links are kept in the data.

## R: research (3 Sonnet workers in parallel, one company each, about 45 min)
Each worker uses web search on public sources (GeeksforGeeks, Glassdoor/AmbitionBox summaries, PrepInsta/IndiaBix-style pattern pages, Reddit, blogs) and writes ONE file: `web/src/data/companies/<id>.json`:
```
{ "id": "exxonmobil" | "chevron" | "reliance",
  "company": "...", "roles": ["Process Engineer", ...],
  "note": "Compiled and paraphrased from publicly shared candidate experiences. Not official; actual tests may differ.",
  "oa": { "sections": [{"name": "...", "questions": n, "minutes": m}], "draw": 15, "marks_per_q": 1,
          "bank": [ {"id": "x1", "section": "Aptitude|Technical|...", "topic": "...", "q": "...",
                     "options": ["", "", "", ""], "answer": 0-3, "explain": "1-3 sentences"} ] },   // 25-30 items
  "interview": { "rounds": ["..."],
                 "technical": [{"q": "...", "a": "2-4 sentences"}],   // ~10
                 "hr": [{"q": "...", "how": "1-3 sentences"}],         // ~6
                 "present": ["..."], "tips": ["..."] },
  "sources": ["https://...", ...] }
```
**Rules for research workers:**
- **Paraphrase every question in your own words.** Never paste a post verbatim, never copy an entire question set, and include no names, usernames or dates of candidates.
- Prefer topics and question **types** that several sources report. If a company's OA is reported as a generic aptitude test, write generic aptitude plus chemical-technical questions in that style.
- Numerical MCQs only when the arithmetic is simple and checkable. Put the working in `explain`. **Each numerical answer is verified by running Python before writing it.**
- At least 60 % technical chemical-engineering questions (thermodynamics, fluid mechanics, heat and mass transfer, reaction engineering, process control, safety), the rest aptitude.
- Keep 3–8 real source URLs in `sources`.
- Report: question counts, how many are numerical (and verified), and anything uncertain.

## B1: build the Company OA (Sonnet, about 2.5 h). PR "FO1: company OA practice (ExxonMobil, Chevron, Reliance)"
- **Web:**
  - `web/src/pages/OA.tsx`: the tab bar. The Coding tab keeps its exact current behaviour.
  - New component `web/src/components/CompanyOA.tsx`: the company list/search, the pattern screen, exam mode, and submit + review.
  - Company JSON loaded with dynamic `import()`.
  - Random draw: shuffle the bank and take `draw` items.
  - `#oa?company=<id>` opens that company directly (the interview card links here).
- **Saving progress:** one tiny additive API route, because the existing attempt saving needs a server-stored quiz.
  - New file `api/app/routers/practice.py`: `POST /api/v1/quiz-attempts {topic: str 1-80, score: float >= 0, total: int 1-50, marks_per_q: 1|2|4}` inserts one `app.quiz_attempts` row with `quiz_id = "practice:" + topic`. Owner only, `_need_db`, returns `{"ok": true}`.
  - It reuses the merged table and `GET /quiz-attempts`. No migration.
  - One `include_router` line in `main.py`. Append a contract section.
  - The web calls it after submit when signed in. Demo mode: show the score, no save.
- **Tests:**
  - api unit/integration: insert, validation 422, owner isolation, then shown by GET.
  - Playwright (API mocked): tabs; Coding unchanged; pick a company; 15 questions; no answers shown before submit; review shows correct answers; the save request is sent; 375 px; the `#oa?company=` deep link.

## B2: build the interview cards (Sonnet, about 1.5 h). PR "FO2: chemical company interview prep"
- `web/src/pages/InterviewBank.tsx`: the Field switch. The CS view stays unchanged.
- The Chemical view renders cards from the same company JSON files (the `interview` part), with collapsible sections, the note, sources ("Sources" as small links), and the button linking to `#oa?company=<id>`.
- **Tests (Playwright):** switch; 3 cards; sections expand; the link opens the right company; 375 px.
- B2 depends only on the JSON shape above, so it runs in parallel with B1 using one sample file until R finishes.

## Validator (part of B1)
`web/scripts/check-companies.mjs`, added to the web CI job. For each company file it checks:
- required fields; unique ids;
- 4 options per question; `answer` in 0..3;
- bank ≥ 20; `draw` ≤ bank size;
- no emails, phone numbers or `@usernames`;
- `sources` non-empty.

## Opus review (the gate)
- **Data:**
  - spot-check 10 questions per company for correctness and clear wording;
  - re-run every numerical answer;
  - confirm nothing is verbatim and no personal data is included.
- **Code:** the usual diff review plus the full checks:
  - `cd api && ruff check . && mypy app && pytest`
  - `cd web && npx tsc -b && npm run lint && npx playwright test`
  - gitleaks
- Zero defects, then PR, then Samarth approves, then merge.

## Safety (does not touch what we built)
- Additive only:
  - new component, new data files, a tab on OA, a switch on Interview Bank;
  - one small new route that reuses the existing table.
- No change to Quiz.tsx, the quiz route, the solver, models.yaml or wiring.py.
- Lazy-loaded data, so no slowdown elsewhere.

## Order
- R (3 workers) and B2 (with a sample file) start together.
- B1 starts with the sample file.
- When R finishes, drop in the 3 files, then the Opus review, then the 2 PRs.
