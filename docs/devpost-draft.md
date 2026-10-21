# Devpost draft (ticket F8)

Status: draft written from the code on `main`. The Nebius Token Factory model
has not been called yet, so every result, latency, cost and accuracy figure is a placeholder
marked **TBD after Nebius integration**. Do not paste invented numbers here.

## Project name

StudyForge

## Tagline (60 characters or fewer)

A study agent for engineers that can't make up numbers

(53 characters)

## Inspiration

Language models are fluent and wrong with confidence, and in engineering a wrong number
costs marks (or worse). We wanted a study helper that never states a number it did not
compute. <!-- TODO(F8): team's own story, in their words -->

## What it does

- Solves quantitative engineering questions: Nemotron plans and writes Python, the student's
  own browser computes it in a sealed Pyodide sandbox, the answer must agree with a check
  value computed in the same script, and the written explanation is rejected if it contains a number the sandbox did not produce.
- Gives plain-language answers for concept questions, with no computed numbers.
- Reads a photo or scanned page of a question with a vision model; the transcript always goes
  to a confirm screen so a person fixes any misread digit before anything is solved.
- ChemLab: eight tested templates (CSTR, PFR, batch, McCabe-Thiele distillation, heat
  exchanger, flash, recycle with purge, pipe and pump) that power the ChemLab page
  (interactive models and 3D). Chat answers always go through the general solver with a
  check and verify, so they no longer include the template's stable/unstable steady-state
  analysis; the ChemLab page shows it. The page has a tab for each template. Process flow diagrams for all eight,
  engineering drawings for the CSTR, the distillation column, the shell-and-tube exchanger
  and the PFR, and 3D views of the CSTR, column and exchanger.
- Quizzes whose numerical answer keys are computed by sandboxed code, not written by the model.
- A dashboard for deadlines and reminders, a notices inbox for pasted class messages,
  phone reminders (web push) and a check-in an hour after each deadline that asks one
  quiz question, plus weak-topic memory from quiz answers.
- Prep packs: open a deadline and get 5 questions linked to the relevant page of your notes.
- Notes and PDF handling: upload notes (full-text search on the server), and read a past
  paper or a PDF's page count in Time to Finish and the PYQ Predictor.
- Planned, not built yet: the agent's `search_my_notes` and `web_search` tools (the notes
  search route exists; the tools still answer "not available"), so cited web answers are not
  there yet. <!-- TODO(F8): update if web search lands -->

The live site is https://studyforge-ten-alpha.vercel.app. It runs in demo/mock mode until the
Render and Vercel environment variables and the model key are set: the screens work and one
built-in CSTR sample is really computed in the browser sandbox, but your own questions are
not solved yet.

## How we built it

**Stack.** React 19 + Vite + TypeScript frontend; FastAPI + Pydantic backend; Supabase for
Postgres, Auth and Storage; Vercel and Render free tiers. Libraries: react-markdown + KaTeX
for maths, Mermaid (strict) + DOMPurify for diagrams, Pyodide 314.0.7 for the sandbox.

**Nemotron on Nebius Token Factory.** Through the `openai` SDK pointed at the Token Factory
base URL. `config/models.yaml` defines four roles: `router` (classify), `solver` (write the code, explain), `cross_check` (re-solve by a different
method when the first answer fails verification) and `vision`. Reasoning is on for solving
and off for every JSON call. The client has its own retries with backoff, per-role timeouts,
a per-solve deadline, model fallback chains, JSON repair, and a cost row per attempt. A
record/replay transport lets CI test the loop without an API key.
Models and prices actually used: **TBD after Nebius integration** (only `super` has an ID in
the registry so far).

**Sandbox.** Model-written Python never runs on our server. It runs in a dedicated Web Worker
with network APIs deleted before user code starts, a 10 s kill timer, capped output and figures,
and shape-checked messages back to the page. CI and evals use a Node Pyodide runner in docker
with no network and an empty environment.

**Verification and guardrail.** The result must carry an answer and a check from a second
method, with the same unit, agreeing within 0.1 %. A disagreement triggers a re-solve by a
different method. A number guardrail then checks the explanation: each number must be within
0.5 % of a sandbox value, a number in the question, or a physical constant, or the answer is
regenerated and, if it still fails, flagged low confidence. A solve is capped at 4 tool steps
and 90 s and always ends with an honest final step.

**Six tools, enforced.** `run_python`, `search_my_notes`, `web_search`, `make_quiz`,
`schedule_reminder`, `draw_diagram`; unknown tools are refused in code.

**ChemLab.** Plain numpy/scipy templates with declared input ranges (SPEC). They power the
ChemLab page, which makes no API call. The solve path does not use them: a template is a
single unverified method, and two of its six real picks were wrong but shown as high
confidence, so templates stay out until they sit behind a verify step.

Measured results (accuracy on the problem set, latency, cost per solve):
**TBD after Nebius integration**.

## Challenges we ran into

- **Keeping model numbers honest.** Checking "no invented numbers" means parsing LaTeX,
  scientific notation, list markers, subscripts and step labels without false alarms. The
  guardrail is a purpose-built parser with tolerances and an allow-list of constants.
- **Locking down the sandbox.** Python can call back into JavaScript, so the worker removes
  network APIs from `self` and its prototype chain and the page treats every worker message as
  untrusted.
- **CSTR multiple steady states.** An exothermic CSTR can have several steady states, and
  naive root finding picks one arbitrarily. The template scans conversion, solves for the
  temperature on the mole-balance curve, finds every root of heat generated minus heat removed
  and reports stability, so the student sees all states.
- **Model output quirks.** Reasoning text leaks into replies, JSON arrives fenced, tool calling
  may not be used; the client strips reasoning, extracts JSON, and the loop accepts a fenced
  Python block as a fallback. How often this happens with the real model:
  **TBD after Nebius integration**.
- **Model access arrived late.** Nebius access was delayed, so the whole loop was built and
  tested against fakes and a record/replay transport instead of the live API. The model's
  real behaviour is still to be measured: **TBD after Nebius integration**.
- **pdfium is not thread-safe.** Reading notes, question photos and PDFs all use pypdfium2,
  and pdfium must not run in two threads at once, even on different documents. One shared
  lock now guards every PDF reader.
- **A frozen API contract.** The solve contract could not change, so every new feature
  (notices, phone reminders, prep packs, PDF reading) was added as a new optional endpoint,
  each written up in `docs/api-contract.md`.
- **Free tiers only.** Everything must fit free hosting and cold starts; a keep-alive ping
  (a GitHub Actions schedule plus an external pinger) keeps the free Render backend awake,
  and also drives reminder delivery.
  <!-- TODO(F8): add the team's own integration challenges, in their words -->

## Accomplishments that we're proud of

- A pipeline where an unsupported number is a failed check, not a style issue.
- A browser sandbox that keeps model-written code off our server entirely.
- ChemLab templates that cover multiple steady states, not just the textbook case.
- Record/replay tests, so model-dependent code is tested in CI with no key.
- Demo mode that runs real Python in the browser with no backend.
- Results: **TBD after Nebius integration**.

## What we learned

Mostly engineering lessons visible in the code: make the model propose and the program
dispose (template picking, tool argument validation); treat every string from a model, a
note or a worker as data; give the agent a hard budget and a graceful failure instead of an
error. Lessons about the models themselves: **TBD after Nebius integration**.

## What's next

Connect the live backend and measure the golden problem set; connect notes search to the
agent; web search with citations. (Telegram reminders were dropped; phone reminders use web push.)
<!-- TODO(F8): align with the final roadmap -->

## Built with

python, fastapi, pydantic, sqlalchemy, alembic, openai-sdk, nvidia-nemotron,
nebius-token-factory, supabase, postgresql, react, typescript, vite, tailwindcss, pyodide, webassembly, numpy, scipy, sympy,
matplotlib, katex, mermaid, dompurify, playwright, vercel, render

## Track

Track 2

## Tools feedback (Nebius / NVIDIA)

See [docs/feedback-log.md](feedback-log.md). That file is currently empty apart from its
header, so there is no feedback to report yet. <!-- TODO(F8): summarise real entries from the log -->

## Links and media

Repo: https://github.com/studyforge-team/studyforge. Demo URL (demo/mock mode until the env
vars and model key are set): https://studyforge-ten-alpha.vercel.app. Video, screenshots: **TBD**.
