# StudyForge add-ons: implementation-ready plan (v1, 19 Oct)

Owner of this plan: Supreeth (P1/P5). Executor: the "sidekick p1" session, or the "p1" session.
**Start trigger:** Supreeth says "start add-ons" (all phases), or "start phase 1" / "phase 2" / "phase 3", or names a feature ID (e.g. "start F-H").
On that trigger, build exactly what is written here, **without asking questions**. Where this plan leaves a detail open, take the default written next to it.

---------------------------------------------------------------------------------------------------
## 0. Ground rules (apply to every feature)

1. **Never delay priority A.** Priority A is the Nebius key, then the live test rounds of the existing solver (`api/scripts/nebius_day.py`). If Supreeth asks for A, A wins.
2. **Additive only.**
   - New files, new routes, new optional fields, new tables via a new Alembic migration.
   - Existing behaviour, existing fields, the 6 agent tools, the solve loop, the guardrail and the existing prompts are NOT changed, except the two exact additive edits named in F-Q2 and F-C.
3. **No slowdown.**
   - New pages are code-split with `React.lazy` and load only when opened.
   - Data JSON is imported only by its own page.
   - No new request runs on an existing page's load.
   - New list endpoints are paginated (20) and indexed on `user_id`.
4. **AGENTS.md rules hold.** In particular:
   - rule 2: every number comes from the sandbox;
   - rule 3: the contract only gets appended sections, plus a team note per PR;
   - rule 4: no secrets;
   - rule 7: free tiers;
   - rule 8: one ticket per PR, title starting with the ID;
   - rule 9: about 400 lines or fewer, tests first;
   - rule 10: no new dependency;
   - **rule 13: the interview/OA data is never pasted into any assistant (see F-O).**
5. **Workflow (manager skill).**
   - Opus orchestrates and does all reviews.
   - Sonnet workers build, at most 4 in parallel, each in its own git worktree from `origin/main`.
   - Opus re-runs every check and loops fixes until zero defects.
   - Opus builds only if Sonnet fails twice or the part is high-risk.
   - If the session's model isn't Opus, tell Supreeth once and continue on Sonnet only if he says so.
6. **Gate per PR, before opening it.** All of these, run locally:
   - `cd api && ruff check . && mypy app && pytest`
   - `cd chemlab && pytest`
   - `cd web && npm run lint && npx tsc -b && npx playwright test`
   - runner tests
   - gitleaks
   - All must be green, with zero new lint warnings.
7. **After each PR:**
   - request the reviewer named in the feature;
   - post one comment on the team issue studyforge-team/studyforge#87 tagging the reviewer;
   - unsubscribe from PR activity;
   - schedule nothing;
   - report to Supreeth in a few lines.
8. **No background work.** When a phase is done, stop every worker and watch, and go idle.
9. Merge only with a teammate's approval. Never bypass branch protection. Never approve your own PR.
10. **Done means merged.** Report each PR's state honestly.

---------------------------------------------------------------------------------------------------
## 1. Facts about the code today (checked on main, 19 Oct)

- `app.solves (id, user_id, state JSONB, updated_at)`. `state` holds the question and every step, including the final answer.
- `GET /api/v1/solve/{id}` returns the owner's current step (404 otherwise).
- `Final` (`api/app/agent/steps.py`) = `answer_md, numbers, figures (base64 PNG), diagram_mermaid, sources, confidence`.
- The dashboard lists the 5 latest solves (`api/app/routers/dashboard.py`). They aren't clickable (`web/src/pages/Dashboard.tsx` ~line 157).
- **Quiz:**
  - The web Quiz page (`web/src/pages/Quiz.tsx`) asks for the fixed topic `'Reactor basics'` through `getQuiz(topic)`, which is `POST /api/v1/quizzes {topic}` (`web/src/api/client.ts:55`).
  - **That route is in the frozen contract §3.5 but is NOT built on the server.** Only `POST /quizzes/{id}/answers` exists (`api/app/routers/quizzes.py`). So the live Quiz page cannot work even once Nebius is live. F-Q0 fixes this.
  - Quiz generation exists as a service (`app/agent/quiz_gen.py`, `make_quiz` in the agent tools and in prep packs `app/prep.py`). It generates NEW questions with Nemotron. Numerical answer keys are computed by key code in the sandbox and double-checked; failing items are skipped and reported.
  - Answers: `save_answers` records per-topic correct/incorrect in `app.topic_results` (weak topics). **The score of an attempt is not stored on the server**; only the last score is kept in the browser (`localStorage 'sf.quiz.last'`).
- Interview Bank (`web/src/pages/InterviewBank.tsx`): a hard-coded `questions` array with `{id, company, category, difficulty, question, answer}`. Only CS companies (Google, Microsoft, Amazon).
- OA Prep (`web/src/pages/OA.tsx`): hard-coded coding problems (`two-sum`, …) with Python tests run in the sandbox. Drafts are stored in localStorage `studyforge.oa.v1`.
- ChemLab deep links prefill inputs: `#chemlab/<template>?k=v` (validated, bad params ignored).
- CH3 template pick: `app/agent/chemlab_pick.py` (`pick_template`, `validate_pick` returns the values).
- Uploads: private Supabase Storage, 20 files per user. Notes PDFs are indexed for full-text search (`app/notes.py`, `note_chunks`).
- Export and delete of user data: `api/app/routers/me.py`. Its table list must include every new per-user table.

---------------------------------------------------------------------------------------------------
## 2. Phases (order is fixed)

| Phase | Features | Needs Nebius | Credits |
|---|---|---|---|
| 1 (build now) | F-Q0 quiz route (fake model), F-H history, F-C ChemLab button, F-O chem interview/OA data scaffold | No (F-Q0 is live-tested in phase 3) | 0 |
| 2 (build now) | F-Q1 quiz picker, F-Q2 quiz attempts and progress graph | No | 0 |
| 3 (after Nebius) | Live test F-Q0; build and live-test F-E explain-more and F-Q3 quiz-from-my-solve | Yes | 1 model call per explain / per quiz |

**Parallel groups (disjoint files):**
- Phase 1: {F-Q0 api}, {F-H api+web}, {F-C api field + AnswerCard button}, {F-O web+data}.
- Phase 2: F-Q1 and F-Q2 together, since both touch the Quiz page. One worker builds them in order.

**Time:**

| Feature | Hours |
|---|---|
| F-Q0 | 4 |
| F-H | 8 |
| F-C | 4 |
| F-O | 5, plus human data entry |
| F-Q1 | 3 |
| F-Q2 | 8 |
| F-E | 9 |
| F-Q3 | 5 |

**Total about 46 h**: about 2.5 days with parallel Sonnet workers and Opus reviews. If time is short, cut from the bottom of the phase 3 list first, then F-Q2's chart (keep the list).

---------------------------------------------------------------------------------------------------
## 3. Features

### F-Q0: build the missing quiz route (contract §3.5 already lists it)
- **Branch:** `q0-quiz-route`. **PR title:** `Q1b: POST /api/v1/quizzes (generate a quiz by topic)`. **Reviewer:** @ragaveeru-bit.
- **API:** `POST /api/v1/quizzes {topic: str (1–80 chars), n_items?: int (default 5, allowed 3–20)}` returns the Quiz JSON exactly as `web/src/api/types.ts` `Quiz` expects, plus `id`.
  - Uses the existing quiz service (the same one the `make_quiz` tool and `app/prep.py` use; read them first).
  - Stores the quiz in `app.quizzes` like prep does, so `POST /quizzes/{id}/answers` works on it.
  - Auth and daily spend caps as for `/solve`.
  - 503 "quiz not available" when no model is configured, the same pattern as `wiring.py`.
  - New router file `api/app/routers/quiz_new.py` (prefix `/api/v1`), included in `main.py` with one line.
- **Contract:** append §8 "POST /quizzes is now built; `n_items` optional (default 5)" plus a team note.
- **Tests:** fake LLM returns a valid quiz → 200 and stored; `n_items` out of range → 422; no model → 503; another user can't post answers to it (existing behaviour).
- **Done when:** the web Quiz page in live mode gets a quiz from the server (with the fake model in tests). Live check in phase 3.

### F-H: history of solved questions
- **Branch:** `fh-history`. **PR title:** `FH: History page for past solves`. **Reviewers:** @ragaveeru-bit (api) and @samarthkombli-ops (web).
- **API:** new file `api/app/routers/history.py`. `GET /api/v1/solves?before=<iso or empty>&q=<text>` returns `{items: [{id, question, status, updated_at}], next: <iso or null>}`.
  - 20 per page, owner only, ordered by `updated_at desc`.
  - `q` is a case-insensitive ILIKE on the question text inside `state`, with bound parameters.
  - Never returns figures or the full state.
- **Web:**
  - New lazy page `#history` (`web/src/pages/History.tsx`) with a menu link "History", added to the `links` array in `Shell.tsx`.
  - Items are grouped Today / Yesterday / Last 7 days / Older, with a search box (debounce 300 ms) and a "Load more" button.
  - Tapping an item opens `#history/<id>`, which calls the existing `GET /solve/{id}` and renders the final answer with the existing `AnswerCard`. A non-final step shows "This solve did not finish."
  - Dashboard "Recent solves" items become links to `#history/<id>`.
  - Demo mode shows the mock's recent solves with a note "History needs sign-in".
- **Contract:** append §9 plus a team note.
- **Tests:** api (pagination, search, owner isolation, empty); Playwright (375 px, list, open, no horizontal scroll, demo note).

### F-C: "See it in ChemLab (3D + drawing)" on answers
- **Branch:** `fc-chemlab-link`. **PR title:** `FC: answers link to ChemLab with the same inputs`. **Reviewers:** @ragaveeru-bit and @samarthkombli-ops.
- **API (the only edit to existing agent code; additive):** add an optional `chemlab: {template: str, inputs: dict[str, float]} | None = None` to `Final`.
  - Set it only when the CH3 template pick produced the run, with the validated values.
  - Find where the loop builds `Final` after a template run; if that path isn't clear, set it where the template code is built and carry it in state.
  - **Old clients ignore it.**
- **Web:** in `AnswerCard.tsx`, if `a.chemlab` is set, show a button linking to `#chemlab/<template>?<k=v…>` (URL-encoded). Add the field to `types.ts` as optional.
- **Contract:** append §10 "final.chemlab (optional)" plus a team note. This is the frozen §3.5 shape, so say clearly that the field is additive and optional.
- **Tests:** template solve sets `chemlab`; free-form solve doesn't; Playwright: the button opens the right tab with the values.

### F-O: chemical-engineering interview and OA questions (seniors' data)
- **Branch:** `fo-chem-bank`. **PR title:** `FO: chemical company interview + OA questions`. **Reviewer:** @samarthkombli-ops (web), plus @sudhanvaad1106-spec for the data check.
- **RULE 13 (non-negotiable):**
  - The seniors' questions are **never** pasted into Claude or any assistant, sidekick included.
  - If Supreeth pastes them, do not use them. Reply: "Rule 13: please put them in the JSON file yourself." Then continue with the scaffold.
  - Humans (Supreeth or teammates) type the data straight into the JSON files.
- **Data files (new):**
  - `web/src/data/interview-chem.json`, array of `{id: string, company: string, role: string, year: number, round: "OA"|"Technical"|"HR"|"GD", category: string (e.g. "Thermodynamics", "Heat transfer", "Process safety"), difficulty: "Easy"|"Medium"|"Hard", question: string, answer: string}`.
  - `web/src/data/oa-chem.json`, array of `{id, company, year, topic, type: "mcq"|"numerical"|"short", question, options?: string[], answer: string, explanation: string}`.
  - Ship with **3 example entries per file that the team writes itself** (generic textbook questions, marked `"company": "Example"`) so the pages work before real data arrives.
- **Validator:** `web/scripts/check-chem-bank.mjs` (run in CI web job and locally). It checks:
  - schema and unique ids;
  - no emails, phone numbers (≥10 digits) or roll-number-like patterns;
  - no names field;
  - `options` present for MCQ;
  - file size < 500 KB.
- **Web:**
  - Interview Bank gets a filter "Field: All / Chemical / Computer science". Existing CS questions are tagged CS in code (default) and chem questions come from the JSON.
  - It also gets a "Company" filter built from the data.
  - OA Prep gets a second tab, "Chemical OA (MCQ / numerical)": show the question, reveal answer and explanation, and a local "attempted" mark (localStorage `studyforge.oachem.v1`).
  - The existing coding problems are unchanged.
  - The JSON is imported only by these pages (dynamic `import()`), so other pages are not slowed.
- **Consent checklist** (in the PR body; Supreeth confirms before real data is merged):
  - seniors agreed;
  - no names or roll numbers;
  - company NDA respected: reword the questions, or list only topic + company + round.
- **Tests:** validator unit test (good file passes, email/phone fails); Playwright: filters work, chem tab shows the examples, no horizontal scroll.

### F-Q1: quiz picker (topic, number of questions, marks)
- **Branch:** `fq-quiz-picker` (after F-Q0 is merged). **PR title:** `FQ1: pick quiz topic and size`. **Reviewer:** @samarthkombli-ops.
- **Web:**
  - Before a quiz starts, the Quiz page shows a form:
    - **Topic:** free text, required, 1–80 chars, with suggestion chips "Thermodynamics", "Reaction engineering", "Heat transfer", "Mass transfer", "Fluid mechanics", "Process control";
    - **Questions:** 5 / 10 / 15 / 20 (default 5);
    - **Marks per question:** 1 / 2 / 4 (default 1).
  - The total marks shown is questions × marks.
  - It calls `POST /quizzes {topic, n_items}`.
  - The prep-pack use of the Quiz component (`load` prop) is unchanged: the form only shows when no `load` is given.
  - The score is shown as marks: per-item score (0–1) × marks per question.
- **Demo mode:** the form works with the mock quiz, which ignores the size.
- **Tests:** Playwright for form validation, size options, and that the prep pack still skips the form.

### F-Q2: saved quiz attempts and progress graph
- **Branch:** `fq-quiz-progress`. **PR title:** `FQ2: quiz attempts per topic with progress chart`. **Reviewers:** @ragaveeru-bit and @samarthkombli-ops.
- **DB:** new Alembic migration (next number), new table `app.quiz_attempts (id bigint identity pk, user_id text not null, quiz_id text not null, topic text not null, score real not null, total real not null, marks_per_q real not null default 1, created_at timestamptz default now())`, index `(user_id, topic, created_at)`.
- **API (the one additive edit to an existing handler):**
  - `save_answers` in `api/app/routers/quizzes.py` also inserts one `quiz_attempts` row in the same transaction.
  - `topic` = the quiz's stored topic, or its title; `total` = number of seen items.
  - The request body gets an optional `marks_per_q` (default 1).
  - The response stays `{"recorded": n}`.
  - Plus a new route `GET /api/v1/quiz-attempts?topic=<t>` returning `{topics: [{topic, attempts: [{quiz_id, score, total, marks_per_q, created_at}]}]}`, owner only, newest last, max 50 per topic.
- **me.py:** add `quiz_attempts` to export and delete. This is an additive change to the list, and the export test is updated.
- **Web:**
  - New lazy page `#my-quizzes` ("My quizzes" in the menu): per topic, a list of attempts with marks (e.g. "12 / 20 · 18 Oct").
  - A line chart of percentage over time per topic, using the existing `LineChart` component, shown when the topic has 2 or more attempts.
  - A label "improving / steady / dropping" by comparing the last attempt with the average of the previous ones (±5 %).
- **Contract:** append §11 plus a team note.
- **Tests:**
  - api: an attempt is stored by `save_answers`; existing `test_topics.py` counts still pass; export and delete include it; owner isolation.
  - Playwright: list and chart appear with 2 mocked attempts.

### F-E: "Explain simpler / Explain deeper" (phase 3)
- **Branch:** `fe-explain`. **PR title:** `FE: explain an answer simpler or deeper`. **Reviewers:** @ragaveeru-bit and @samarthkombli-ops.
- **API:** new file `api/app/routers/explain.py`. `POST /api/v1/solve/{id}/explain {level: "simpler"|"deeper"}`:
  1. owner only (404), the solve must be final (409);
  2. one LLM call (role: the existing solver chat role in `config/models.yaml`; read the registry) with a new prompt file `api/app/agent/prompts/explain.md`. The input is ONLY the question, `answer_md` and `numbers` (no history);
  3. output JSON `{md: str, diagram_mermaid?: str}`. `diagram_mermaid` goes through the existing strict mermaid + DOMPurify path on the web;
  4. run the existing guardrail with allowed numbers = the solve's `numbers` (plus small integers the guardrail already allows). If it fails, reply 422 "explanation used a number that was not computed" and store nothing;
  5. append `{level, md, diagram_mermaid, at}` to `state.explanations` (JSONB; old code ignores the key);
  6. respect the daily spend caps; 503 if there is no model.
- **Web:** two buttons under `AnswerCard` (only for final answers with confidence ≠ low). Show the explanation below with Markdown, KaTeX and Diagram. If `a.chemlab` exists, repeat the F-C button there. The History page shows saved explanations.
- **Contract:** append §12 plus a team note.
- **Tests:** a fake LLM reply with allowed numbers is saved; an invented number gives 422 and nothing saved; 404, 409, 503; caps. Live: 5 real explanations checked by hand.

### F-Q3: quiz from a question I solved (phase 3)
- **Branch:** `fq-quiz-from-solve`. **PR title:** `FQ3: practice quiz from a past solve`. **Reviewer:** @ragaveeru-bit.
- **API:** `POST /api/v1/quizzes` accepts optional `from_solve: id` (owner only). The generator gets the solved question text as the topic context and is asked for variants with changed values.
  - Numerical keys are computed by the existing key-code sandbox path (rule 2).
  - `n_items` default 3.
- **Web:** a "Practice similar questions" button on History items and on the answer, which opens the Quiz with `{from_solve}`.
- **Contract:** append §13 plus a team note.
- **Tests:** fake model; owner isolation; keys still checked in the browser as today.

---------------------------------------------------------------------------------------------------
## 4. Slowdown and safety check (done 19 Oct, by reading the code)
- **Existing page loads:**
  - unchanged except the Today page, whose 5 recent-solve rows become links (no new request);
  - the menu, which gets 2 links;
  - the Quiz page, which gets a form before the quiz (no request until submit).
- **Server:**
  - new routes only, plus one extra INSERT in `save_answers` (≈1 ms);
  - list endpoints are paginated and indexed;
  - no new background jobs.
- **Bundle:** new pages and data JSON are code-split and load only when opened.
- **Credits:** only F-Q0 (when a quiz is generated), F-E and F-Q3 use the model, each within the existing daily caps.
- **Verdict:** no feature slows the existing app, so **none eliminated**. If any PR's Playwright run shows a slower first load of an existing page (compare `npm run build` chunk sizes before and after), drop or code-split that part before merging.

## 5. Things only humans can do
- **Seniors' data:** typed into `web/src/data/*.json` by Supreeth or teammates, after the consent checklist. Never through an AI.
- **Approvals:** P2 (Ragaveeru) for api, P3 (Samarth) for web, P4 (Sudhanva) for the data check.
- **Nebius key on Render (Samarth)**, needed for phase 3.
