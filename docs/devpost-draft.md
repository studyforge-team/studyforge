# Devpost draft (ticket F8)

Status: draft written from the code on the feature branches. The Nebius Token Factory model
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
compute. <!-- TODO(F8): add the team's real story; not in the repo -->

## What it does

- Solves quantitative engineering questions: Nemotron plans and writes Python, the student's
  own browser computes it in a sealed Pyodide sandbox, two independent methods must agree,
  and the written explanation is rejected if it contains a number the sandbox did not produce.
- Gives plain-language answers for concept questions, with no computed numbers.
- Reads a photo or scanned page of a question with a vision model; the transcript always goes
  to a confirm screen so a person fixes any misread digit before anything is solved.
- ChemLab: tested reactor and distillation templates (CSTR, PFR, batch, McCabe-Thiele) the
  agent can pick instead of improvising code.
- Quizzes whose numerical answer keys are computed by sandboxed code, not written by the model.
- A dashboard for deadlines and reminders.
- Planned, not built yet: Telegram reminders, notes upload and search, cited web answers,
  3D ChemLab models and engineering drawings. <!-- TODO(F8): update as tickets merge -->

Demo mode works today without a backend for one built-in CSTR sample.

## How we built it

**Stack.** React 19 + Vite + TypeScript frontend; FastAPI + Pydantic backend; Supabase for
Postgres, Auth and Storage; Vercel and Render free tiers. Libraries: react-markdown + KaTeX
for maths, Mermaid (strict) + DOMPurify for diagrams, Pyodide 314.0.7 for the sandbox.

**Nemotron on Nebius Token Factory.** Through the `openai` SDK pointed at the Token Factory
base URL. `config/models.yaml` defines four roles: `router` (classify, pick a ChemLab
template), `solver` (write the code, explain), `cross_check` (re-solve by a different
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

**ChemLab.** Plain numpy/scipy templates with declared input ranges (SPEC). The model only
proposes a template name and quantities with units; the server converts units from an explicit
table, range-checks them, and builds the code from floats only, so no model-written string
reaches the sandbox for those solves.

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
- **Free tiers only.** Everything must fit free hosting and cold starts.
  <!-- TODO(F8): add real challenges the team hit during integration -->

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

Connect the live backend and measure the golden problem set; notes upload and search; web
search with citations; Telegram deadline reminders; prep packs; ChemLab 3D models and SVG
drawings. <!-- TODO(F8): align with the final roadmap -->

## Built with

python, fastapi, pydantic, openai-sdk, nvidia-nemotron, nebius-token-factory, supabase,
postgresql, react, typescript, vite, tailwindcss, pyodide, webassembly, numpy, scipy, sympy,
matplotlib, katex, mermaid, dompurify, playwright, vercel, render

## Track

Track 2

## Tools feedback (Nebius / NVIDIA)

See [docs/feedback-log.md](feedback-log.md). That file is currently empty apart from its
header, so there is no feedback to report yet. <!-- TODO(F8): summarise real entries from the log -->

## Links and media

Demo URL, repo URL, video, screenshots: **TBD**.
