# Devpost draft (ticket F8)

Status: ready to paste (27 Oct 2026). Every number below was measured on the live app or in
the team's evals on real Nemotron calls; the source is named next to it. Lines marked
**[team]** need a teammate's words or a decision before submitting.

## For judges (first lines of the description)

> Chatbots give engineering students confident wrong numbers. **StudyForge never states a
> number it did not compute:** Nemotron 3 Ultra writes the Python, the student's browser runs
> it, and a second, independent Ultra solve must agree before an answer is marked *high*.
> Held-out result: 93.8 % correct and **0 wrong answers marked high**. Try it in 10 seconds:
> https://studyforge-ten-alpha.vercel.app → **Try demo**.

Gallery (in this order, each with a one-line caption): thumbnail, an answer with its
confidence badge and "Ran Python", the "How a question is answered" diagram, ChemLab 3D,
a photo read, quiz progress.

## Project name

StudyForge

## Tagline (60 characters or fewer)

A study agent for engineers that can't make up numbers

(53 characters)

## Track

Best Apps and Agents (Track 2)

## Inspiration

Chatbots give engineering students fluent, confident answers with wrong numbers, and a wrong
number costs marks. We are chemical-engineering students, and we wanted a study partner that
never states a number it did not compute, and says "not verified" when it isn't sure.
**[team]** add a line in your own words (an exam, a tutorial sheet, a moment that started it).

## What it does

- **Solves engineering questions with computed, checked numbers.** Nemotron plans the
  solution and writes Python; the student's own browser runs it in a sealed Pyodide sandbox;
  the result must carry an answer and a check that agree to 0.5 %; every number in the written
  explanation must come from the sandbox output or the question.
- **Earns its confidence.** An answer is shown as *high* only when an independent Nemotron
  Ultra re-solve agrees. If they disagree, a third solve breaks the tie (2 of 3 = *medium*,
  all different = *low*). When it cannot verify, it says so instead of guessing.
- **Uses tested engineering tools,** not recalled formulas: a McCabe-Thiele template for
  distillation stage counts and a library of tested correlations and equations of state
  (Colebrook, Churchill-Bernstein, Ergun, Antoine, Lee/Kesler, Peng-Robinson and other cubic
  EOS, Margules/van Laar/Wilson/NRTL, bubble and dew points).
- **Reads questions from photos and PDFs** with Nemotron VL; the transcript goes to a confirm
  screen so a misread digit is fixed before solving. A tutorial sheet is split and solved one
  question at a time.
- **Explains concepts and derivations** in plain language, without invented numbers.
- **ChemLab:** eight interactive calculators (CSTR, batch, PFR, McCabe-Thiele, heat exchanger,
  flash drum, recycle loop, pipe and pump) with charts, process flow diagrams and 3D models of
  the CSTR, column and exchanger. They run in the browser and use no credits.
- **A full study loop:** quizzes with progress tracking (numerical keys computed in the
  sandbox), OA coding practice and company OA question sets, an interview bank for 15
  companies, a PYQ predictor, a time-to-finish planner, a notices inbox, voice input, and a
  history of every solve.

Try it: https://studyforge-ten-alpha.vercel.app (press **Try demo**, no account needed).

## How we built it

**Nemotron on Nebius Token Factory.** One `openai` client pointed at the Token Factory base
URL; `config/models.yaml` maps each role to a fallback chain of models:

| Role | Model | Why |
| --- | --- | --- |
| router | Nemotron 3 Nano (fallback Super) | classifies every question in about 0.6 s for $0.00003 |
| solver | Nemotron 3 Ultra (fallback Super), reasoning on | writes the Python and the explanation |
| cross_check | Nemotron 3 Ultra (fallback Super), reasoning on | re-solves independently, blind to the first answer |
| vision | Nemotron 3.5 Super-VL, reasoning on | reads question photos and PDF pages |

The client adds retries with backoff, per-role timeouts, a per-solve deadline, JSON repair,
a cut-off-reply retry, a cost row per call, spend caps (per user, per IP, daily, total) and an
automatic switch to a teammate's Token Factory key when our credits are spent. A
record/replay transport lets CI test the agent loop without a key.

**Where Token Factory helped.** The OpenAI-compatible API meant one client for all four
models; moving the solver from Super to Ultra after an eval was a one-line config change;
per-model prices let us log the cost of every call and keep a question at about one cent.

**Sandbox.** Model-written code never runs on our server. It runs in a Web Worker with
network APIs removed, a kill timer, capped output, and compatibility shims for NumPy 2.
React + Vite + TypeScript on Vercel; FastAPI + Pydantic on Render; Supabase for Postgres,
auth and storage.

**Verification.** Answer and check must agree; impossible values fail (a conversion outside
0–1, a negative flow, a fraction of a stage); a number guardrail rejects any number in the
explanation the sandbox did not produce (standard constants and visible unit conversions
allowed); every part the question asks for must be answered. At most 10 tool steps and 300 s
per solve.

## Results

- **Accuracy:** 93.8 % on the held-out half of a new 96-question tutorial-style set across
  8 topic families (135/144 over 3 runs of 48 questions), with **0 wrong answers labelled
  high** (PR #156, live Nemotron, real prompts and checks).
- **Live app, 26 Oct:** 43 of 50 unseen hard questions from our 300-question bank correct
  (86 %); every *high* answer correct; median 33 s; about $0.013 per question.
- **Images:** 12/12 printed question images read with every number correct (was 9/12).
- **Tests:** about 1,000 API unit tests and about 390 ChemLab tests run in CI on every PR.

## Challenges we ran into

- **The model's own check repeated its mistake.** Early on, every confident wrong answer had
  a "check" that recomputed the same formula. Fix: an independent Ultra re-solve and a
  tie-break before anything is shown as *high*.
- **Recalled formulas were wrong.** Real-gas, Wilson and Peng-Robinson formulas were
  sometimes misremembered; Supercritical CO2 was treated as an ideal gas. Fix: tested tools the
  model must call, chosen by topic.
- **Keeping numbers honest without false alarms.** The guardrail parses LaTeX, scientific
  notation and unit conversions; standard constants and differences of given values had to
  be allowed so correct answers were not marked *low*.
- **The browser's NumPy 2** rejects patterns the model writes from habit (`float()` of a
  one-element array, `trapz`, `simps`); shims keep them working.
- **Images shrunk too far** turned 10⁻³ into 10⁻⁵; images now keep their resolution.
- **Credits:** Token Factory charges the card when an account's credit is used, so we count
  spend ourselves and switch keys.
- **[team]** add one challenge from your own part of the build.

## Accomplishments that we're proud of

- A wrong number shown with confidence is now rare: 0 in the held-out eval and 0 in our last
  live test of 50 hard questions.
- Model-written code never touches our server.
- A whole study app, not a demo: solver, ChemLab with 3D, quizzes, OA and interview prep.

## What we learned

Make the model propose and the program check. A model's "second method" is often the same
method twice, so real confirmation needs an independent solve. Tested tools beat recalled
formulas. Honest "not verified" answers build more trust than fluent wrong ones.

## What's next

Notes search for the agent, turning pasted notices into deadlines automatically, more tested
templates for transient heat and mass transfer, and broader subject coverage.

## Built with

nvidia-nemotron, nebius-token-factory, python, fastapi, pydantic, sqlalchemy, alembic,
openai-sdk, supabase, postgresql, react, typescript, vite, tailwindcss, pyodide,
webassembly, numpy, scipy, sympy, matplotlib, three.js, katex, mermaid, playwright, vercel,
render

## Testing instructions (Devpost field)

Open https://studyforge-ten-alpha.vercel.app and press **Try demo** (no account needed).
Ask an engineering question, for example: "A shell-and-tube heat exchanger cools 2.0 kg/s
of oil (cp = 2100 J/kg/K) from 160 C to 100 C using 2.5 kg/s of water (cp = 4180 J/kg/K)
entering at 20 C, in counterflow. U = 350 W/m^2/K. Find the water outlet temperature, the
LMTD and the heat-transfer area in m^2." (about 30 s; 44.1 C, 96.8 K, 7.44 m^2). Then press
**See it in 3D in ChemLab** under the answer: the same exchanger opens as a live simulation
with a 3D model. Hard multi-step questions can take 30–180 s because a second model re-solves
them before the answer is marked *high*. From the menu, also try Quiz, OA Prep and Interview
Bank. Free to use until judging ends.

## Tools feedback (Nebius / NVIDIA)

See [feedback-log.md](feedback-log.md); paste its points into the feedback field.

## New project?

Yes: the repository was created on 8 Oct 2026, inside the submission period.

## Links and media

- Demo: https://studyforge-ten-alpha.vercel.app
- Repo: https://github.com/studyforge-team/studyforge (MIT licence)
- Video: **[team]** YouTube link, set to Public, under 3:00
- Screenshots: answer with confidence badge, ChemLab 3D, quiz progress, photo read, Today
