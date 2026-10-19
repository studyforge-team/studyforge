# StudyForge: one-day plan (v2, written 19 Oct, to execute 20 Oct)

**This replaces PLAN-addons.md for tomorrow.** The other add-ons (F-C ChemLab link, F-E explain, F-O chem interview data, F-Q3) are postponed; PLAN-addons.md stays as the backlog.
**Start trigger:** Supreeth says "start tomorrow plan" (or "start T1" … "start T5"). Then build without asking questions; every open detail has a default below.

## Goal for tomorrow (two things only)
1. **Quiz that works end to end:**
   - make a quiz from a topic or from uploaded material (textbook PDF, scanned/handwritten pages, or a photo);
   - the student chooses the type (MCQ / fill-in-the-blank / mixed), the number of questions and the marks;
   - the app shows a suggested time (display only, no timer);
   - the student takes the quiz in the app and gets marks and a percentage;
   - every attempt is saved per topic, with a progress graph.
2. **History of solved questions** (like Claude's chat list): every past solve is listed by day, searchable, and reopens with its full answer.

## Why the Quiz page shows nothing today
- The page asks the server for a quiz with `POST /api/v1/quizzes`.
- **That route is in the contract (§3.5) but was never built**, so the request fails. The page then shows "That question or session no longer exists" instead of a quiz.
- The quiz generator itself exists (`app/agent/quiz_gen.py: generate_quiz(llm, topic, n_items, notes=…)`), so T1 only has to expose it.

## Rules (short)
- Additive only:
  - new routes, new files and new optional fields;
  - one new table through a new Alembic migration;
  - the only edit to an existing handler is one extra INSERT in `save_answers`.
  - The solve loop, the 6 tools, the guardrail and the existing prompts are not touched.
- **Don't collide with the Nebius integration.** A teammate is wiring Nebius now. Do not edit `config/models.yaml` or `api/app/wiring.py`; only *read* them. In `main.py` add one `include_router` line per new router. If his PR merges first, merge main and keep both sides.
- Full test gate before each PR:
  - `cd api && ruff check . && mypy app && pytest`
  - `cd chemlab && pytest`
  - `cd web && npm run lint && npx tsc -b && npx playwright test`
  - runner tests
  - gitleaks
- One ticket per PR, title with its ID. Contract: appended sections only, plus a team note on studyforge-team/studyforge#87.
- Manager workflow: Sonnet workers build in parallel worktrees; Opus reviews every diff and re-runs the checks, looping until zero defects.
- Merge only with a teammate's approval. No background work after the day's work.

## Tasks (in parallel where marked; times are working hours)

### T1: quiz route (api) — 3 h — PR "Q1b: POST /api/v1/quizzes (topic or material)"
New router `api/app/routers/quiz_new.py`. `POST /api/v1/quizzes`, request:
```
{ topic: str 1–80 (required),
  n_items?: int 3–20 (default 5),
  kinds?: "mcq" | "blank" | "mixed" (default "mcq"),
  marks_per_q?: 1 | 2 | 4 (default 1),
  upload_id?: str }
```
- **Material (only if `upload_id`):**
  - The upload must be the user's own (same check as `GET /uploads/{id}`).
  - PDF with a text layer: `notes.pdf_pages(data)`, first 10 pages, at most 12,000 chars in total.
  - A PDF page or image without text (handwritten or scanned): transcribe with the existing vision reader `read_question(client, data, mime, page)`, at most **3 pages**, to keep credits low.
  - The text is passed as `notes=[…]` to `generate_quiz`.
- `kinds`:
  - `"mcq"`: ask for MCQ items only;
  - `"blank"`: fill-in-the-blank only (T2);
  - `"mixed"`: about half each.
  - Implement this through the instruction text `generate_quiz` already builds. Add an optional `kinds` argument with default `"mcq"`, so the existing callers (prep packs, the `make_quiz` tool) behave exactly as before.
- Store the quiz in `app.quizzes` the same way `app/prep.py` does, with `topic` and `marks_per_q` in the stored JSON.
- Response:
```
{ id, title, items: [...],
  topic, marks_per_q,
  total_marks: n * marks_per_q,
  suggested_minutes: n * (2 if mcq, 3 if blank or mixed) }
```
- Errors: 503 "quiz not available" when there is no model (same pattern as `wiring.py`); 404 for an upload that isn't the user's; 422 for bad input; the daily spend caps apply as on `/solve`.
- **Tests (fake LLM, fake vision):** topic only; text-layer PDF; image path calls vision ≤ 3 times; kinds passed through; defaults; 503 / 404 / 422; the stored quiz can be answered by `POST /quizzes/{id}/answers`.

### T2: fill-in-the-blank item type — 2 h — part of the T1 PR or a separate small PR "Q1c"
- `api/app/agent/quiz.py`: new `BlankItem(_Item)`:
  - `type: Literal["blank"]`;
  - `stem` must contain `"____"`;
  - `answers: list[str]`, 1–5 accepted answers, each ≤ 60 chars;
  - `explanation: str`.
- Add it to the `QuizItem` union (additive).
- Numerical blanks stay `NumericalItem`, so their keys are still computed in the sandbox (rule 2).
- Generator instruction: blanks are words or short phrases; numerical answers use the numerical type.
- **Web:** `Quiz.tsx` `Question` renders a text box for `blank` and grades case- and whitespace-insensitive against `answers`. A reveal shows the explanation.
- **Tests:** schema accepts and rejects; grading (case, spaces); Playwright for a mocked blank item.

### T3: quiz setup screen (web) — 3 h — PR "FQ1: quiz setup (topic, material, type, size, marks)"
`web/src/pages/Quiz.tsx`. Only when no `load` prop is given; the prep pack is unchanged.
- **Setup form:**
  - **Topic** (required). Chips: Thermodynamics, Reaction engineering, Heat transfer, Mass transfer, Momentum transfer, Process control, Particle technology.
  - **"Add material (optional)":** PDF or photo, using the existing `uploadFile(f, 'notes')`; the file name is shown.
  - **Type:** MCQ / Fill in the blanks / Mixed.
  - **Questions:** 5 / 10 / 15 / 20.
  - **Marks per question:** 1 / 2 / 4.
  - Shows "Total: N marks · Suggested time: M minutes (keep time yourself)".
- Button "Make quiz" calls `POST /quizzes`, then the existing quiz flow runs.
- **Result screen:** "Score: x / total marks (p %)". The score sent to `saveAnswers` stays per item (0–1), and marks = score × marks_per_q.
- `client.ts`: `getQuiz` accepts the new optional fields. `types.ts`: optional `topic`, `marks_per_q`, `total_marks`, `suggested_minutes`.
- **Demo mode:** the form works and the mock quiz ignores the options.
- **Tests (Playwright):** form validation, options sent, suggested time shown, prep pack still skips the form, 375 px with no horizontal scroll.

### T4: attempts per topic and progress graph — 3 h — PR "FQ2: quiz progress per topic"
- **Migration** (next number): `app.quiz_attempts (id bigint identity pk, user_id text not null, quiz_id text not null, topic text not null, score real not null, total real not null, marks_per_q real not null default 1, created_at timestamptz not null default now())`, index `(user_id, topic, created_at)`.
- **`save_answers`** (the one existing-handler edit): in the same transaction, insert one row.
  - `topic` = the stored quiz topic, else its title;
  - `score` = the request's score;
  - `total` = the number of non-null entries in `correct`;
  - `marks_per_q` = the stored quiz value, else 1.
  - The response is unchanged.
- **New route** `GET /api/v1/quiz-attempts` returns `{topics: [{topic, attempts: [{quiz_id, score, total, marks_per_q, created_at}]}]}`, owner only, oldest first, max 50 per topic.
- **`me.py`:** add `quiz_attempts` to export and delete.
- **Web:** a "My progress" section on the Quiz page (above the setup form, signed in only):
  - one card per topic with each attempt as "12/20 marks (60 %) · 18 Oct";
  - a line chart of % per attempt with the existing `LineChart`, when there are ≥ 2 attempts;
  - a label: improving / steady / dropping (last attempt vs. the average of the earlier ones, ±5 %).
- **Tests:** api (insert on save, existing `test_topics.py` still passes, export/delete, owner isolation); Playwright with 2 mocked attempts.

### T5: History of solved questions — 4 h — PR "FH: history of past solves"
- **API:** new `api/app/routers/history.py`. `GET /api/v1/solves?before=<iso>&q=<text>` returns `{items: [{id, question, status, updated_at}], next}`.
  - 20 per page, owner only, newest first.
  - `q` is ILIKE on the question in `state`, with bound parameters.
  - Never returns full state or figures.
- **Web:**
  - New page `#history` (lazy-loaded) with a "History" link in the menu (`Shell.tsx` links).
  - Groups: Today / Yesterday / Last 7 days / Older. A search box and "Load more".
  - Tap an item to open `#history/<id>`: the existing `GET /solve/{id}`, rendered with the existing `AnswerCard`. A non-final solve shows "This solve did not finish".
  - The Today page "Recent solves" rows become links to it.
- **Tests:** api (pagination, search, isolation, empty); Playwright (list, open, 375 px).

## Schedule for 20 Oct
| Time | Work |
|---|---|
| Start | Workers in parallel: W1 = T1+T2 (api + schema), W2 = T5 (history), W3 = T4 api (migration + route). Opus reviews as each finishes. |
| +3 h | W1 continues with T2 web. W4 = T3 (setup screen), starting once T1's request shape is fixed (it is, above). |
| +5 h | T4 web (progress section). |
| +6–7 h | Final full gate; PRs opened; reviewers tagged (P2 @ragaveeru-bit for api, P3 @samarthkombli-ops for web); merge on approval; live check with Nebius (make a quiz from a real PDF). |

Total work is about 15 h, about 7 h wall-clock with 3–4 parallel workers.

**If time runs short, cut in this order:**
1. history search;
2. the progress chart (keep the list);
3. the "mixed" type;
4. handwritten pages (keep text PDFs).

## Credits (from the $25)
- One quiz = one generation call, plus up to 3 vision calls if the material is handwritten.
- History and progress use no credits.
- The existing daily caps apply.

## Not tomorrow (backlog in PLAN-addons.md)
F-C ChemLab link from answers, F-E explain simpler/deeper, F-O chemical interview/OA data (rule 13: humans type the data), F-Q3 quiz from a past solve, subjective questions, an in-app timer.
