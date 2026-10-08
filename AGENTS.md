# AGENTS.md: shared brief for every AI coding assistant

Source of truth: the StudyForge master plan v1.2 (section numbers below refer to it).

## What StudyForge is
A study agent for engineering students that can't make up numbers. Nemotron (Nebius Token
Factory) plans and writes Python, a sealed browser sandbox computes, the answer is checked.
Plus deadlines/reminders, quizzes, prep packs, cited web answers, and ChemLab simulations.

## Stack per folder
- `api/`: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, httpx, openai SDK
  pointed at Token Factory, instructor, APScheduler, aiogram 3. Tests: ruff, mypy, pytest.
- `web/`: React 19 + Vite + TypeScript, Tailwind, shadcn/ui, react-markdown + KaTeX,
  mermaid (securityLevel strict) + DOMPurify, uPlot. Tests: eslint, tsc, vitest, Playwright.
- `web/src/sandbox/`: Pyodide 314.0.7 in a dedicated Web Worker (numpy, scipy, sympy, matplotlib).
- `web/src/chemlab/`: three 0.186.1 + @react-three/fiber 9.8.x + drei 10.7.x, lazy-loaded;
  2D drawings are plain SVG. No drei Text/Environment (they fetch from a CDN).
- `chemlab/`: simulation templates in plain Python (numpy/scipy), pytest-tested.
- `runner/`: Node Pyodide runner for CI/evals (docker --network none, empty env).
- Data: Supabase (Postgres via session pooler, Auth, Storage). Hosting: Vercel + Render free.

## NON-NEGOTIABLE RULES
1. The server never executes model-written code. Python runs only in the browser Pyodide
   worker or the CI runner with an empty environment.
2. Never invent numbers. Every number in an answer comes from sandbox output.
3. The API contract (section 3.5) is frozen. Changing it needs a PR that touches the contract
   plus a team note.
4. Secrets live only in host env. Never commit them. `.env` is git-ignored; only
   `.env.example` (names, no values) is tracked.
5. Golden test values (`api/tests/golden/`) change only with P4 review. Never edit them to
   make a test pass.
6. The agent has exactly 6 tools (run_python, search_my_notes, web_search, make_quiz,
   schedule_reminder, draw_diagram), enforced in code. Unknown tools are refused.
7. Free tiers only. No paid service or new paid dependency.
8. One ticket per PR. PR title starts with the ticket ID (e.g. "A2: FastAPI skeleton").
   The PR body includes the ticket's done-when and how it was tested.
9. Small PRs (about 400 changed lines or fewer). Write tests first.
10. No new dependency without saying why in the PR. Only MIT/Apache/MPL licences.
11. Every PR is reviewed by a teammate in a different role; red CI blocks merge.
12. If the plan is unclear, ask a teammate. Do not guess.
13. Never paste API keys, real student data or the interview bank into any assistant.
14. Pinned versions change only by team decision (record it in `docs/decisions.md`).

## COMMANDS
- api install: `cd api && pip install -e ".[dev]"` (after A2)
- api dev: `cd api && uvicorn app.main:app --reload` (after A2)
- api test: `cd api && pytest` (after A2)
- api lint: `cd api && ruff check . && mypy app` (after T1)
- web install: `cd web && npm install` (after A5)
- web dev: `cd web && npm run dev` (after A5)
- web test: `cd web && npm test` (vitest, after A5)
- web lint: `cd web && npm run lint && npx tsc --noEmit` (after A5/T1)
- chemlab test: `cd chemlab && pytest` (after CH1a)
- runner (CI/evals): `node runner/node-pyodide.mjs` (after S1b; in docker, no network)
- e2e: Playwright in CI (after T5)

## Where things live
- `api/app/main.py, config.py, db.py, models.py, auth.py`: backend core
- `api/app/llm/`: Token Factory client (retries, fallback, cost log)
- `api/app/agent/`: loop.py, tools.py, prompts/, guardrail.py
- `api/app/routers/`: one file per endpoint group; `api/app/search/`: notes search
- `api/tests/`: unit/, integration/, golden/ (P4 reviews golden)
- `web/src/`: sandbox/, pages/, components/, api/ (typed client + mock server), chemlab/
- `chemlab/templates/`: cstr.py, pfr.py, batch.py, mccabe.py; `chemlab/tests/`
- `config/models.yaml`: model registry; `.github/`: templates and workflows
- `docs/`: architecture.md, decisions.md, feedback-log.md
- Roles are P1 Engine & ChemLab, P2 Backend & data, P3 Frontend & sandbox, P4 Quality & release.
  All four of us are equal teammates; roles only say who builds which ticket first.
