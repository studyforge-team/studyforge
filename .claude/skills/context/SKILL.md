---
name: context
description: Full hand-over context for Supreeth's P1 (Engine & ChemLab) work on StudyForge. Covers the project, team, rules, workflow, tools, what is built (branches/PRs), progress numbers, open items, and the next job (stand-in model pass, then the Nebius switch). Use at the start of every new session on this repo, or whenever you need to know what was done before.
---

# StudyForge P1: complete context (last updated 10 Oct 2026)

Read this whole file first. Then read `p1/TRACKER.md` on the same branch (`p1-tracker`) for the
ticket table and the dated log. The full P1 plan is in `plan-v3.md` next to this file.
Always prefer what GitHub shows today over this file: verify before you rely on it.

## 0. Bootstrap (a fresh cloud session starts on `main`; this file lives on `p1-tracker`)

```bash
cd /home/user/studyforge            # or wherever the repo was cloned
git fetch origin                    # all branches
git checkout p1-tracker             # memory branch: tracker + this skill. Never merged.
cat p1/TRACKER.md                   # ticket table, decisions, log
python p1/progress.py               # merge-based % (only merged tickets count 100 %)
```
GitHub access is through the **GitHub MCP tools** (`mcp__github__*`, load them with ToolSearch).
There is no `gh` CLI. The repo is **public**: never commit secrets or student data.

## 1. The project

- **StudyForge**: a study agent for engineering students that **cannot make up numbers**.
  Nemotron (NVIDIA model on **Nebius Token Factory**) plans and writes Python, a **sealed browser
  Pyodide sandbox** runs it, the answer is checked; the explanation may only use numbers that the
  sandbox produced. Also: deadlines/reminders (phone notifications; Telegram dropped 10 Oct),
  quizzes, prep packs, cited web answers, ChemLab simulations (CSTR, PFR, batch, McCabe-Thiele).
- Event: **Nebius x NVIDIA Global AI Hackathon**. **Submission deadline: 28 Oct 2026, 21:00 IST**
  (Supreeth presses Submit). The demo must run on Nemotron via Token Factory.
- Repo: https://github.com/studyforge-team/studyforge (public). Master plan v1.2 (§ numbers) is the
  team's source of truth; `AGENTS.md` at repo root is the shared brief.
- Stack: `api/` Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, httpx, openai SDK
  pointed at Token Factory. `web/` React 19 + Vite + TS, Tailwind, shadcn/ui, KaTeX, mermaid,
  uPlot. `web/src/sandbox/` Pyodide 314.0.7 Web Worker. `chemlab/` plain numpy/scipy templates.
  `runner/` Node Pyodide runner for CI (docker `--network none`, empty env). Data: Supabase.
  Hosting: Vercel (web) + Render free (api).

## 2. Team (GitHub logins)

| Person | Login | Role |
|---|---|---|
| Supreeth (the user) | `ssupreethsg` | **P1 Engine & ChemLab**: `api/app/llm/`, `api/app/agent/`, `chemlab/templates/`, README, Devpost |
| Samarth Kombli | `samarthkombli-ops` | P3 Frontend & sandbox (also did A1 scaffold); most merged PRs on main |
| (name not recorded) | `ragaveeru-bit` | P2 Backend & data (A2 FastAPI skeleton = PR #14, open) |
| (name not recorded) | `shreyasgoudar251ch056` | V2Da CSTR drawings (PR #13); asked to review Q1, S2b, S3. Role likely P4 Quality & release: confirm |

All four are equal teammates; roles say who builds a ticket first. P4 owns golden test values.

## 3. Rules (all binding)

### AGENTS.md (team)
1. The server never executes model-written code. Python runs only in the browser Pyodide worker
   or the CI runner with an empty environment.
2. Never invent numbers. Every number in an answer comes from sandbox output.
3. API contract (§3.5) is frozen; change = PR touching the contract + team note.
4. Secrets only in host env. Never commit them. Only `.env.example` (names) is tracked.
5. Golden values (`api/tests/golden/`) change only with P4 review. Never edit to pass a test.
6. Exactly 6 agent tools (run_python, search_my_notes, web_search, make_quiz,
   schedule_reminder, draw_diagram), enforced in code. Unknown tools refused.
7. Free tiers only. No paid service or new paid dependency.
8. One ticket per PR. PR title starts with the ticket ID ("A2: FastAPI skeleton"). Body has the
   ticket's done-when and how it was tested.
9. Small PRs (~400 changed lines). Tests first.
10. No new dependency without saying why. Only MIT/Apache/MPL licences.
11. Every PR reviewed by a teammate in a **different role**; red CI blocks merge.
    → **Do not merge P1 PRs yourself** unless Supreeth explicitly says so.
12. If the plan is unclear, ask. Do not guess.
13. Never paste API keys, real student data or the interview bank into any assistant.
14. Pinned versions change only by team decision (`docs/decisions.md`).

### P1 plan hard rules (plan §1)
- Max 4 tool steps / 90 s per solve; state saved every step.
- Model code ends with `result = {...}` (named values + units, single numbers, < 16 KB, no NaN/inf).
- Explanations use only sandbox numbers, question numbers, integers ≤ 10, allow-listed constants.
- Reasoning off for every JSON call; reasoning text stripped before parsing; validate + repair once.
- Model IDs live only in `config/models.yaml` (G10 fills them from `GET /v1/models`).
- Definition of Done (§5.3): done-when test passes in CI, reviewed (other role), merged,
  auto-deployed, no console errors at phone width, cost per call logged.

### Supreeth's standing rules for the assistant
- **Nebius deferred**: nobody has a Visa/Mastercard for Nebius yet (the $25 Token Factory credit
  can't be claimed). Build everything that doesn't need Nebius; Nebius integration at the end.
- **Do not change the timeline/dates. Build exactly what the plan says.**
- **Opus orchestrates** (design, physics/numerics, loop, reviews, hard parts); **Sonnet subagents**
  (`model: "sonnet"`, isolated worktrees) do well-specified coding. Save tokens, never quality.
- **Verify everything**: run ruff, mypy, pytest yourself on every helper's work; re-check numbers
  independently; adversarially re-read diffs. No errors shipped.
- **Always push** finished work so nothing is lost; keep `p1/TRACKER.md` updated (it is the memory).
- When Supreeth says "don't change anything", only check and report.
- Report progress (hours + %) whenever asked; be honest about what is estimate vs measured.
- No-PR rule (8 Oct) was **lifted 10 Oct**; PRs are open. Still never merge without review.
- Other teammates' tickets (A2, A4, C1, S1b, T1, …) only with the team's OK.

## 4. Workflow per ticket
1. Branch from the right base (see merge order), name like the team: `s2-wiring`, `ch1a-cstr`.
2. Tests first. Opus writes the spec; Sonnet helper builds in a worktree when the spec is clear.
3. `cd api && ruff check . && mypy app && pytest` (chemlab: `cd chemlab && pytest`). All green.
4. Opus re-runs the checks, spot-checks numbers by an independent method, reads the diff.
5. Push (`git push -u origin <branch>`, retry 2/4/8/16 s on network errors).
6. PR (when allowed): title `ID: …`, body with done-when + how tested + new deps and why.
   Request a reviewer in a different role. Add the ticket to the tracker log.
7. Update `p1/TRACKER.md` on `p1-tracker` and push it.

## 5. Tools, systems, environment
- **Claude Code cloud session** (claude.ai/code): ephemeral container, repo cloned fresh, deleted
  after inactivity, so push everything. SessionStart hook (`.claude/hooks/session-start.sh`, PR #4,
  branch `claude/beautiful-cori-swt2xb`, not merged) makes a Python 3.12 venv with ruff/mypy/pytest
  and installs `api[dev]`/chemlab/web deps when manifests exist.
- **Network policy of the environment** (checked 10 Oct): blocked → `api.tokenfactory.nebius.com`,
  `integrate.api.nvidia.com`, `api.groq.com`, `openrouter.ai`, `cdn.jsdelivr.net` (Pyodide packages).
  Reachable → `generativelanguage.googleapis.com` (Gemini), GitHub, PyPI/npm, Docker Hub (was rate
  limited 429 on 8 Oct). Supreeth changes this under the environment's settings → Network access →
  Allowed domains. Keys go in the environment's settings as env vars/secrets, **never in chat**.
- Python 3.12 venv; Node 22.x (web needs ≥ 22.12); Docker (for the runner); Pyodide 314.0.7.
- Supreeth's laptop: Windows, has Docker Desktop (needed WSL), repo planned at `C:\dev\studyforge`
  (outside OneDrive). RAM is limited: Ollama models must be small (see §9).
- Scheduled check-in trigger `trig_0182qAnor2ZwSAo1zoMM2g1j` (12:01 UTC 10 Oct) belonged to the old
  session; a new session does not receive its events. Re-subscribe to PRs if asked to watch them.

## 6. What is built (all pushed; verify on GitHub)

`main` has: A1 scaffold, P3's web app (A5, S1 sandbox worker, UI1, UI1b, S6, E1, design pass,
S1 self-test), P3 golden proposals (#12), and **A3 (merged 10 Oct, #6, merge c2bc388)**.

| PR | Branch (base) | Ticket | Contents | Tests |
|---|---|---|---|---|
| #6 merged | a3-llm-client | A3 | `api/app/llm/{client,registry,cost,errors,reasoning}.py`, `config/models.yaml`: roles router (nano→super), solver (super, no fallback), cross_check (ultra→super), vision; own retries/backoff, deadlines, `CostRecorder`, `BudgetGuard`, `chat_json` validate+repair, thinking flag via `extra_body={"chat_template_kwargs":{"enable_thinking":…}}` | 41 |
| #16 | b8-guardrail (main) | B8 | `api/app/agent/guardrail.py`: `parse_numbers`, `allowed_numbers`, `check`; ±0.5 %, LaTeX/sci/%, skips subscripts/units | 62 |
| #17 | ch1a-cstr (main) | CH1a | `chemlab/pyproject.toml` (templates → import name `chemlab`), `templates/_common.py` (SPEC/validate/envelope/finish/json_safe = frozen format), `cstr.py` (all steady states, X-scan, u = 1−X precision, k0-edge bracketing, zero order) | 30 + 20k random |
| #18 | ch1b-templates (ch1a) | CH1b | `pfr.py`, `batch.py`, `mccabe.py` | 158 chemlab total |
| #19 | c2-vision (main) | C2 | `api/app/agent/read_question.py`: `prepare_image` (PDF/photo, rotate, resize), `read_question`, low-confidence fallback | 36 |
| #20 | q1-quiz (main) | Q1 | `quiz.py` schema + key checks, `quiz_gen.py` generator (keys run in the browser sandbox, never on server), `fixtures/quiz_mock.json` for P3 | 107 |
| #21 | s2-agent-loop (main) | S2 | `api/app/agent/{loop,state,steps,tools,verify}.py`, `prompts/`, `routers/solve.py`, `llm/replay.py` (replay transport for CI); DB-free core, native tool calls + fenced-code fallback, 4 steps/90 s, two-method verify, cross-check | 92 |
| #22 | contract-p1-requests (main) | S2 | `docs/api-contract.md` + team note (proposes `step_seq` for safe retries) | – |
| #23 | ch3-template-pick (ch1b) | CH3 | `api/app/agent/chemlab_pick.py`: units, validation, server-built template code, returns `(TemplateRun|None, cost)` | 70 |
| #24 | s2-wiring (s2-agent-loop; needs #16 #19 #23 first) | S2 | B8 guard on by default, template path, `upload_reader`, `Deps.templates` | 270 api |
| #25 | s2b-prompts (s2-wiring) | S2b | final prompts (Given/Method/Steps/Answer/Check; result single numbers < 16 KB), `api/app/agent/smoke.py` + `api/scripts/smoke.py` (smoke/eval harness via docker Node runner) | 292 api |
| #26 | s3-golden-proposals (ch1b) | S3 | `docs/golden-proposals/*`: 10 problems + 8 ChemLab cases, two methods each, verify script ALL OK | – |
| #27 draft | f4-readme-draft (main) | F4/F8 | `README.md`, `docs/devpost-draft.md`; results "TBD after Nebius" | – |
| #4 | claude/beautiful-cori-swt2xb | setup | cloud SessionStart hook | – |
| – | p1-tracker | – | `p1/TRACKER.md`, `p1/progress.py`, `p1/g10_probe.py`, this skill. **Never merged.** | – |

**Merge order**: a3 (done) → s2-agent-loop → s2-wiring → s2b-prompts; ch1a → ch1b → ch3
(ch3, b8, c2 before s2-wiring). A dry run merged all 12 into main cleanly (10 Oct).
Reviewers requested: ragaveeru-bit (backend), samarthkombli-ops (chemlab/contract),
shreyasgoudar251ch056 (Q1, S2b, S3). Other teammates' open PRs: #13 V2Da, #14 A2, #15 S1 chemlab mount.

Important facts about P3's sandbox (on main, `web/src/sandbox/worker.ts`): modes `solve`/`chemlab`;
16 KB result cap in solve mode; `allow_nan=False`; packages detected by scanning code, later
first-use of matplotlib/sympy forces a respawn; result body `{stdout, result, figures, error, ms}`.

## 7. Progress (10 Oct)
- Plan: **100 MUST hours** for P1 (71 own + 29 shared). SHOULD (CH2, CH5, QSX) only if MUST merged.
- Split: ~**61 h buildable without Nebius**, ~**27 h need a model** (Nebius), ~**12 h team
  activities** (kickoff, gates, standups, submit).
- **Built: ~52.5 of the 61 non-Nebius hours (86 %)** = ~52 % of the 100 h by work done.
- Tracker (merge-based, `python p1/progress.py`): **52.9 %** (A3 merged = 100 %, 11 PRs at 75 %).
- Left without Nebius (~8.5 h), all blocked: DB store for the loop (P2's A4), Pyodide runner check
  for templates (S1b runner + jsDelivr), final README/Devpost (23/27 Oct), test days on their dates.

## 8. Timeline (plan §4, do not change)
C2 13 Oct · S2 15 Oct · TD1 15 Oct · S2b 16 Oct · B8 17 Oct · Q1 18 Oct (mock to P3 16 Oct) ·
CH1a 18 Oct (must not slip) · CH3 19 Oct · CH1b 22 Oct · F4 23 Oct · SHOULD by 23 Oct ·
TD2 + F2 + RTD 24–25 Oct · F8 27 Oct · F9 submit 28 Oct 21:00 IST. Check-ins 11, 15, 18, 22 Oct.

## 9. NEXT JOB: stand-in model pass (decided 10 Oct), then the Nebius switch

Goal: do the model-dependent ~27 h now with a free OpenAI-compatible **stand-in** model, so that
when Nebius arrives only a config switch + re-run + small retune (~7–10 h) is left. A3 reads
`base_url`, `api_key_env`, model IDs and role settings from a YAML registry; env var
`STUDYFORGE_MODELS_PATH` points it to another file. **No code change is needed to swap providers**
unless the provider rejects the thinking flag (see step 2).

Honesty rules for this pass: stand-in results are **rehearsal only**. Never write them into
README/Devpost or golden files as Nemotron results. Test questions and synthetic photos only
(rule 13). Free tiers only (rule 7). Stand-in registries live in `p1/standin/` on `p1-tracker`
(never merged), so `config/models.yaml` stays the only registry on main (plan rule 6).

### Provider choice (Supreeth sets key + network in the environment settings, not in chat)
| Option | Where it runs | Setup | Notes |
|---|---|---|---|
| **A. NVIDIA API catalog** (build.nvidia.com), base `https://integrate.api.nvidia.com/v1` | cloud session | key in env `NVIDIA_API_KEY`; allow domain `integrate.api.nvidia.com` | Serves **Nemotron** models: closest to the final behaviour. Free dev credits; check sign-up needs no card |
| **B. Google Gemini** free tier, base `https://generativelanguage.googleapis.com/v1beta/openai/` | cloud session (already reachable) | AI Studio key in env `GEMINI_API_KEY` | No card. Free-tier data may be used by Google: test data only. May reject `chat_template_kwargs` |
| **C. Ollama** on the laptop, base `http://localhost:11434/v1/` | laptop only (Claude Code on Windows, or by hand) | any non-empty key env | 8 GB RAM: `qwen2.5:3b` + `qwen2.5vl:3b`; 12 GB: `qwen2.5:7b`; 16 GB+: `qwen2.5:7b` + `qwen2.5vl:7b`. Set `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_CONTEXT_LENGTH=8192` |
Also allow `cdn.jsdelivr.net` (Pyodide packages for the runner/browser). Later: `api.tokenfactory.nebius.com`.

### Steps (in order; record every result in `p1/standin/results/` and the tracker log)
1. **Check access**: `curl` the provider's `/models` with the key from env (never print it).
   If blocked/missing, tell Supreeth exactly which domain/env var to add, and stop that step.
2. **G10 rehearsal**: make `p1/g10_probe.py` take `--base-url` and `--key-env` (default Token
   Factory/TF_API_KEY), run it against the stand-in: model list, text, tool call, thinking on/off,
   JSON (json_object + prompt-only), one **synthetic** question photo (render typed text to PNG
   with Pillow). If the provider returns 400 for `chat_template_kwargs`, add a registry option
   (e.g. top-level `send_thinking_flag: true` default) on a new branch `a3-thinking-flag-option`,
   tests first, PR "A3: …" (small follow-up; needs review). Otherwise no A3 change.
3. **Stand-in registry**: write `p1/standin/models.<provider>.yaml` (same roles as
   `config/models.yaml`; omit `reasoning:` if not supported; longer timeouts for Ollama).
4. **Integration branch** `p1-integration` (pushed, never PR'd): merge #16–#26 in merge order on
   top of main (dry run was clean). This is where live runs happen.
5. **A3 live smoke**: `cd api && TF_LIVE=1 STUDYFORGE_MODELS_PATH=../p1/standin/models.X.yaml pytest tests/unit/llm/test_live_smoke.py`.
6. **C2**: run `read_question` on 8 synthetic photos (typed + rotated + low-res); target 7/8 readable.
7. **Q1**: generate 10 quizzes with the stand-in; check schema + key consistency (keys themselves
   run in the browser sandbox, not on the server).
8. **CH3**: 10 labelled ChemLab questions (use S3 cases until P4 labels arrive); target 9/10 picks.
   Running our own template code (not model-written) in CPython for checking is fine.
9. **S2 / S2b**: end-to-end smoke (`python api/scripts/smoke.py <problems.json>`) needs the
   **S1b Node runner** (`runner/node-pyodide.mjs`, not on main yet; P2/P4 ticket) + docker +
   jsDelivr. Never run model-written code in CPython on the server (rule 1). If S1b is still
   missing, ask Supreeth whether the team OKs P1 building it, or test through the browser
   (Playwright/Chromium is preinstalled) once A2 + jsDelivr are available.
10. **Replay fixtures** recorded from stand-in calls: dev only; re-record on Nebius before CI uses them.
11. Update tracker: what passed, what needs Nemotron re-run, hours.

### Final Nebius switch (when a card/credit is available)
Unset `STUDYFORGE_MODELS_PATH` → back on `config/models.yaml`; `TF_API_KEY` in env settings; allow
`api.tokenfactory.nebius.com`; run `p1/g10_probe.py --super … --nano … --vision … --photo …`; fill
model IDs + prices in `config/models.yaml` (PR "G10: …") and record in `docs/decisions.md`; re-run
steps 5–10 on Nemotron; retune prompts; record real numbers in README/Devpost (F4/F8).
Spend ceiling proposed: $5 for G10 + A3 ($10–15 for all development per §10).

## 10. Lessons already learned (don't repeat)
- CSTR numerics: absolute xtol too loose at tiny X → `xtol=1e-300`; solve near X = 1 in u = 1 − X;
  scan grid down to 1e-300; bracket the k0 edge explicitly; `np.errstate` for overflow.
- "Safe retry by identical body" loops forever on deterministic errors → removed; contract
  proposes `step_seq`.
- `MissingFixture` was swallowed by the SDK → client re-raises it. mypy needs `api/app/__init__.py`.
- Smoke runner timeouts left containers alive → containers are named and killed.
- Stable flags as 1.0/0.0 numbers leaked into answers → words now.
- A2's PR #14 `api/pyproject.toml` lacks `openai` and `pyyaml` (A3 needs them). Supreeth hasn't
  decided whether to comment on #14; ask before commenting.
- An outside AI tool's review (10 Oct) was mostly false; only the 16 KB prompt rule was real (fixed).
  Treat outside reviews as claims to verify.
- Licence flags: Pillow (MIT-CMU), pypdfium2 (BSD-3/Apache) are not strictly on the allow list:
  mention in PRs.
