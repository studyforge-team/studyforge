P1 execution plan — Engine & ChemLab simulations (v3, 8 Oct 2026)

Sources: `StudyForge_Role_P1.pdf` (4 pages) and `StudyForge_Master_Plan_v1.2.pdf` (25 pages), both read in full, plus the team repo `studyforge-team/studyforge` (all 6 branches inspected 8 Oct). § = master plan section.
v2 = v1 after an independent adversarial review (19 findings). v3 = v2 updated with what the real repo shows (section 2a) and re-reviewed. Sections 10–11 list what changed.

## 1. What P1 is

P1 builds the "brain": the Nemotron client, the agent loop that plans → writes Python → has the
browser run it → verifies → explains, the number guardrail, photo reading, the quiz engine, the
ChemLab simulation templates and template picking, plus README, Devpost text and the submission.
If an answer or a simulation number is wrong, it is P1's area.

Owned folders: `api/app/llm/`, `api/app/agent/`, `chemlab/templates/`, README, Devpost text.

Budget: 71 h own tickets + 29 h shared (G-all 3.5, K0 2, S3 3, TD1 4, TD2 4, F2 3, RTD 4, SU 5.5) = 100 h MUST. 14 h SHOULD exist on paper, but §9 expects only ~10 h of SHOULD for the whole team before the freeze.

Hard rules that bind every ticket:
1. The server never executes model-written code. It returns a `run_python` step; the browser worker runs it and posts the result.
2. Exactly 6 tools, enforced in code: `run_python, search_my_notes, web_search, make_quiz, schedule_reminder, draw_diagram`.
3. Max 4 tool steps / 90 s per solve; state saved every step.
4. Model code ends with `result = {...}` (named values + units). Explanations use only sandbox numbers, question numbers, integers ≤ 10, or allow-listed constants.
5. Reasoning off for every JSON call; reasoning text stripped before parsing. No reliance on server-side JSON decoding; validate and repair once.
6. Model IDs live only in `config/models.yaml` (the G10 probe reads them from `/v1/models`, never hardcodes).
7. Never edit `tests/golden/` (P4 owns expected answers).
8. Definition of Done (§5.3): "done when" test passes in CI · reviewed by a teammate in a different role · merged · auto-deployed · no new console errors at phone width · cost per call logged.
9. Team rules (§5.2): two failed attempts at the same test → pair with a teammate; a ticket at 2× its hours → decide that evening to cut, simplify or swap.

## 2. Where we stand today (Thu 8 Oct)

| Item | State (re-checked 8 Oct, after your "everything is set") |
|---|---|
| Team repo | Found and readable: `github.com/studyforge-team/studyforge`. Write access not yet tested. |
| G10 model test (due 6–7 Oct) | No trace in the repo (`config/` is empty, `docs/decisions.md` empty). Treated as not done. |
| A3 LLM client (due today) | Not started. `api/app/llm/` holds only `.gitkeep`. |
| Docker | Desktop is installed, but **the engine is not running and WSL is not installed**, so it cannot run containers yet. |
| Git identity | Still not set (no global user.name / user.email). |
| `gh` CLI | Still not installed. |
| Nebius key | Not set (known). |
| Python | 3.14.0 system (same Python as Pyodide 314); 3.12.15 via uv (backend pin). |
| Node / npm | 20.18.0 / 10.8.2. P3's branches use `@types/node` 24 and Vite 8, so the team is on a newer Node (see R5). |
| Working folder | `p1project/` holds only this plan and sits inside OneDrive (R11). |
| Token Factory | `GET /v1/models` reachable; 401 without a key (checked). |

### 2a. What the repo shows

- **`main` has one commit: A1 (scaffold).** Folders exist with `.gitkeep` only. There is no `api/pyproject.toml`, no FastAPI app, no CI workflow, no CODEOWNERS, no DB. So P2's A2 (due 7 Oct) and P4's A8/T1/T2 are not merged.
- **Frontend work is well ahead on unmerged, stacked branches** (8 Oct): `a5-web-skeleton` → `s1-sandbox` → `ui1-solve-screen` → `s6-diagrams`. The solve screen already runs its step loop against a mock API, with tests.
- **There is one human committer so far** (Samarth Kombli), who authored both A1 (a P2 ticket) and the P3 tickets. Who holds which role is unconfirmed, and no backend, DB or CI work is visible.
- **The branch you linked, `claude/beautiful-cori-swt2xb`**, adds only a Claude Code cloud SessionStart hook (creates a Python 3.12 venv, installs `ruff mypy pytest`, then `api[dev]`, chemlab and web deps when their manifests exist). It only runs in cloud sessions, contains no ticket work, and expects **pip with `api/pyproject.toml`**, not uv.
- **AGENTS.md rules that change this plan:**
  - Rule 8: one ticket per PR, title starts with the ticket ID. v2's "split S2 into several PRs" needs a team OK.
  - Rule 3: a contract change needs a PR that touches the contract plus a team note.
  - Rule 12: if the plan is unclear, ask a teammate, do not guess.
  - Rule 13: no real student data into any assistant (confirms R12).
  - Commands are pip-based: `cd api && pip install -e ".[dev]"`, `cd chemlab && pytest`.
- **The contract as P3 has typed it** (`web/src/api/types.ts` on `ui1-solve-screen`):
  - `run_python {code, timeout_s: 10}`, `need_confirm {extracted_text}`, `final {answer_md, numbers, figures, diagram_mermaid?, sources, confidence}`.
  - P3 marked four fields as "gap" and filled them in: `numbers: Record<string, number>` (flat, no units), `figures: string[]`, `sources: {title, url?}[]`, `confidence: 'high'|'medium'|'low'`. I adopt these as they are.
  - Result body: `{stdout, result, figures (base64 PNG strings), error, ms}`. No step number.
  - The web client does **not** retry POSTs, and there is no GET for a pending step.
- **The sandbox worker as P3 has built it** (`s1-sandbox`):
  - Run modes `'solve' | 'chemlab'`. The 16 KB result cap applies in `solve` mode only, so ChemLab screens can receive full series.
  - `result` is serialised with `allow_nan=False`: any NaN or inf makes the whole run fail. Templates and solver code must never emit them.
  - Code that does not set `result` fails with "code must set result = {...}".
  - No code yet writes `chemlab/` templates into the Pyodide file system (R2 is still open).
- P3's mock answer prints a percentage computed in JavaScript that is not in `result`. That is exactly the case the guardrail must reject, so the real explain step has to emit it from the sandbox.
- **More worker and client behaviour that constrains my code:**
  - Non-JSON values (sympy numbers, Decimal, complex) are silently turned into **strings**, and `result` is not required to be a dict.
  - Every open matplotlib figure is captured automatically (first 4, raw PNG ≤ 500 KB each, sent as bare base64), and only when the run succeeds. Each run gets fresh globals.
  - Packages are detected by scanning the submitted code for `numpy|scipy|sympy|matplotlib`; after the first run the worker locks down, so a later step that first needs matplotlib or sympy forces a slow respawn.
  - On failure the client posts `{stdout: '', result: null, figures: [], error, ms: 0}`; the error is the last 600 characters, or literals such as `'timeout'` and `'result too large'`.
  - The web client throws on any non-2xx response without reading the body, sends no auth header yet, posts only `{question}`, and stops at `need_confirm` with a placeholder.
  - The page CSP on those branches is `connect-src 'self'; img-src 'self' data: blob:` — narrower than §3.6, so a deployed build cannot yet call the API or show Storage images.
  - Vite 8 requires Node ≥ 20.19 or ≥ 22.12, and Mermaid's parser requires ≥ 22.12, so Node 20.18 cannot build the web app.

### Schedule reality — a decision is needed today
- Remaining P1 work is about 96 h over 20 working days (8–28 Oct, Dussehra off) = **4.8 h/day**, if kickoff and the other gates were done. The handbook assumed 4.5.
- 8–14 Oct alone holds G10 1.5 + A3 6 + S3 3 + C2 7 + S2 16 + S2b 6 = 39.5 h in 7 days = **5.6 h/day** before standups.
- §9 says cut-line step 1 is decided at G7 on 7–8 Oct. For P1 it means "B8 flags instead of regenerating" (saves 1 h). That alone does not close the gap.
- So this plan re-dates honestly (section 4): the real S2 merges 15 Oct, S2b 16 Oct. The solve screen already works against its own mock, so nobody needs an HTTP stub from me; what S5 and T4 need is the **loop interface with an in-memory store and canned steps, delivered 12 Oct**. If you can give ≥ 5.5 h/day on 8–14 Oct, the original 14 Oct holds.
- Check-in evenings 11, 15, 18, 22 Oct: more than 6 h behind → apply the next cut step.

## 3. What I need from you (grouped; nothing starts until the first group is answered)

**Must have to start (6 items)**
1. Your git name + email. The repo is public, so I suggest your GitHub `…@users.noreply.github.com` address (the other committer uses one). I set them.
2. GitHub write access: the first `git push` opens a browser login through Git Credential Manager, which you complete. No `gh` install is needed for that; `gh` is optional (it lets me open PRs and read the ticket board from here).
3. Go-ahead to create `C:\dev\studyforge` (outside OneDrive) and clone there, and to work on a new branch `a3-llm-client` cut from `main` (the team's naming: `a5-web-skeleton`, `s1-sandbox`). The `claude/…` branch you linked is a cloud-session setup branch, so I would not build on it unless you say so.
4. **Who holds which role?** Every commit so far is by one person. Tell me who is doing A2/A4 (backend skeleton, DB), T1 (CI) and who reviews A3 (it must be someone in a different role, AGENTS.md rule 11).
5. Send the team note in section 7 today (I draft it). It gates the work from 12 Oct.
6. Real hours/day for 8–14 Oct, and whether kickoff/G7/G8 happened.

**Needs the Nebius key (can come a little later)**
7. Your **personal dev** key (G3: $25 code redeemed, expiry noted), set by you as user env var `TF_API_KEY`, never pasted in chat. Not the team prod key.
8. A spend ceiling for live calls (§10 budgets $10–15 for all development; I propose a $5 hard stop for G10 + A3, spend reported after each ticket).
9. One question photo with no personal data, for the G10 vision call.
- Without the key I can still write A3's code and mocked tests and open the PR. G10 and the one live smoke test wait.

**Needed this week**
10. Docker: open a terminal as Administrator, run `wsl --install`, reboot, start Docker Desktop and wait for "Engine running". Needed from about 12 Oct, when the loop first executes model-written code.
11. Node: OK to install Node 24 LTS (R5: the web app needs ≥ 22.12; this machine has 20.18).
12. A dev database: your own free Supabase project (session-pooler connection string + Storage), for loop/resume tests. Needed from about 10 Oct.

**From teammates (I draft the messages, you send)**
13. All: OK to split S2 (16 h) and CH1b (9 h) into 2–3 PRs each, since rule 8 says one ticket per PR and rule 9 says about 400 lines.
14. Sandbox/frontend owner: section 7 items; how `chemlab/templates/*.py` is loaded as `chemlab.*` in the worker (R2); the Node pin.
15. Golden-data owner: the 10 labelled chem questions for CH3; the judging rule for C2 "readable enough to solve"; the `result["answer"]` shape for T4; who authors the 8 ChemLab golden cases; **synthetic or consented** photos for C2 testing (rule 13 forbids real student data in any assistant, with no exceptions).
16. Backend/CI owners: where a CI model key lives, when CI (T1) lands, who owns the demo/cached path, and whether `config/models.yaml` at the repo root is readable by a Render service rooted at `api/`.
17. All (heads-up): AGENTS.md names `npm test` (vitest) and eslint for web, but the web package has no `test` script and uses oxlint. If T1 is written from AGENTS.md, web CI will be red and block every merge.

**Later**: Devpost and Nebius Discord are yours to post/submit on; I draft. No browser access is needed before F8.

## 4. Order of work (re-dated)

| # | Ticket | h | Plan due | Target | Notes |
|---|---|---|---|---|---|
| 0 | Setup + G10 (my part of G-all) | 1.5 | 7 Oct | 8 Oct | needs key |
| 1 | A3 LLM client | 6 | 8 Oct | **9 Oct** | one PR |
| 2 | S3 share: 10 golden problems + ChemLab cases proposed | 3 | 10 Oct | 10 Oct | constant-α, CMO textbook cases only |
| 3 | Team note (section 7) + **loop interface** (`step`/`on_result`, in-memory store, canned steps) | part of S2 | — | **12 Oct** | what S5 and T4 build on |
| 4 | C2 vision read | 7 | 13 Oct | 13 Oct | |
| 5 | Draft template I/O format (`SPEC` + sample JSON) published | part of CH1a | — | **14 Oct** | P2/P3 get 5 days instead of 1 |
| 6 | S2 agent loop + bridge | 16 | 14 Oct | **15 Oct** | |
| — | TD1 | 4 | 15 Oct | 15 Oct | my smoke script is the eval (T4 lands 16 Oct) |
| 7 | S2b solver prompts | 6 | 14 Oct | **16 Oct** | |
| 8 | B8 guardrail | 4 | 16 Oct | 17 Oct | |
| 9 | Q1 quiz engine (schema + mock to P3 **16 Oct**) | 8 | 17 Oct | 18 Oct | |
| 10 | CH1a CSTR + format frozen | 4 | 18 Oct | 18 Oct | **not allowed to slip** (video scene, real users 19 Oct) |
| 11 | CH3 template picking | 3 | 19 Oct | 19 Oct | |
| 12 | CH1b PFR, batch, McCabe-Thiele | 9 | 22 Oct | 22 Oct | |
| 13 | F4 README | 3 | 23 Oct | 23 Oct | |
| 14 | SHOULD: CH2 (needs CH1a) → CH5 (needs CH1b, CH2) → QSX (needs P2's QS) | 14 | 23 Oct | only if every MUST due is merged | |
| 15 | TD2 + F2, RTD | 11 | 24–25 Oct | | |
| 16 | F8 Devpost text | 3 | 27 Oct | 27 Oct | |
| 17 | F9 final checks + submit | 2 | 28 Oct 21:00 IST | 28 Oct | you press Submit |

Not in the table: K0 2 h, rest of G-all 2 h, standups 5.5 h. After A3: report real cost per call so the team can re-budget (§10 expects this by 9 Oct).

## 5. Ticket designs

### Step 0 — setup and G10
- Clone to `C:\dev\studyforge`; Python 3.12 venv; pip installs as in AGENTS.md (`pip install -e ".[dev]"`), matching the cloud hook. Add the first entries to the existing `docs/feedback-log.md` today.
- Record G10 results in `docs/decisions.md`. If I end up replacing instructor (part of the listed stack) with my own repair wrapper, that is a stack change and goes to the team first.
- `scripts/g10_probe.py`: `GET /v1/models`, then one call each — Super text; Super native tool call; Super reasoning on vs off (`extra_body={"chat_template_kwargs":{"enable_thinking":…}}`); `low_effort`; Nano JSON in **two modes** (`response_format=json_object` and prompt-only JSON); one photo through the vision model.
- Record per call: model ID, tokens, price, **latency per call type**, and how reasoning text arrives (`reasoning_content` field vs inline think tags, incl. unbalanced tags).
- From the latencies, project a full solve (≈ 5 calls). If the projection is over 60 s, the single-script two-method design below becomes mandatory and `low_effort` is used off the hard path.
- Output: `config/models.yaml` and §3.2 filled. Super missing → Discord post the same day (you post).

### A3 — LLM client (6 h) · `api/app/llm/`
- `registry.py`: roles `router` (Nano → fallback Super, reasoning off), `solver` (Super, **no fallback model**: failure raises a typed `ModelUnavailable` that E3's "model timeout" state can show), `cross_check` (Ultra if listed, else second Super sample), `vision` (per G10).
- `client.py` (openai async SDK, Token Factory base URL): `chat`, `chat_tools`, `chat_json`, `vision`.
  - SDK `max_retries=0`; own 3 retries with backoff + jitter on 429 (honouring `Retry-After`), 5xx, timeouts. Never retry 400/401/404.
  - **Deadline-aware**: every call takes `deadline`; timeout = min(role timeout, time left); no retry once the budget is gone.
  - `chat_json`: own validate-and-repair wrapper so the order is fixed — get text → `strip_reasoning` (handles `reasoning_content`, `<think>…</think>`, a lone closing tag, truncated block) → extract JSON → Pydantic validate → one repair retry. instructor is used only if G10 shows its prompt-only mode gives the same control; otherwise the wrapper replaces it (say so in `docs/decisions.md`).
  - Cost log: one `llm_calls` row per attempt, including failures and repairs, through a `CostRecorder` protocol (DB-backed when A4 lands; in-memory in tests). Calls return their cost so the loop can add up `solves.cost_usd`.
  - `BudgetGuard` hook called before each request, so P2's spend guard (T7) plugs in without touching the client.
  - Registry path comes from an env var with the repo-root `config/models.yaml` as default (item 16).
- **Kept out of this ticket** to stay inside 6 h and about 400 lines: the record/replay transport (fixtures keyed by hash of model + messages + params, so normal CI needs no key) moves to the first S2 PR, where it is first needed. The recording workflow belongs with whoever owns `.github/workflows/`.
- **No manifest needed, and A2 is not touched.** The PR contains only `api/app/llm/**`, `api/tests/unit/llm/**` and `config/models.yaml`. I develop in a local, uncommitted Python 3.12 venv and run `cd api && python -m pytest tests/unit`. The PR body lists the runtime and dev dependencies for A2's `pyproject.toml` (rule 10 requires naming them anyway). If A2 is still missing when S2 needs it, a separate "A2: …" PR is the clean route, with team OK.
- CI does not exist yet (T1 not merged), so "passes in CI" cannot be met today. Until T1 lands, the PR shows local `ruff` + `mypy` + `pytest` output and is marked done only after CI goes green on it.
- Order inside the ticket: (1) registry + client + retries + cost log with mocked tests — no key needed; (2) G10 results into `config/models.yaml`; (3) live smoke test.
- Done when: mocked tests (retry counts, Retry-After, no retry on 4xx, fallback order, deadline cut-off, cost row per attempt, reasoning stripped in all four shapes, repair retry, replay) + 1 live smoke test behind `TF_LIVE=1`.

### C2 — vision read (7 h)
- `read_question(bytes, mime, page=1) -> {text, latex, figure_description, confidence}`; page chosen by the caller, default first. pypdfium2 render (~170 DPI) in a threadpool; EXIF rotation; longest side ~1600 px; JPEG data URL.
- Vision model extracts only; Nemotron reasons. Fallback: NVIDIA vision → Qwen2-VL if a real call works → typed input. Output always goes to the confirm screen.
- I supply the function; P2 wires `POST /uploads/{id}/read` (or reviews my wiring). `figure_description` is not in the frozen response → in the contract request.
- Tested on my own photos first; P4's 8 labelled photos decide the ticket, by P4's rule. CI uses replay.
- Done when: ≥ 7/8 labelled photos readable enough to solve.

### S2 — agent loop + browser tool bridge (16 h) · `api/app/agent/`
- **Core is DB-free**: `loop.step(state, deps)` and `loop.on_result(state, result, deps)` are pure over a `SolveState` model; `deps` injects the LLM client, state store, tool implementations and clock. The route layer uses a Postgres store; T4 and my tests use an in-memory store and the Node runner. This is what lets T4 "drive agent/loop.py in-process".
- Flow per §3.6: first call → if `upload_id` and text unconfirmed → `need_confirm`; else Nano `classify` + `search_my_notes`; non-calc → answer without code; calc → `next_action`.
- The confirm round-trip is undefined in §3.5 and in the client. Proposal (section 7): the client re-posts `/solve {question: <edited text>, upload_id, confirmed: true}`; no new endpoint.
- Auth is an injectable dependency that can be switched off locally, because neither the auth backend nor the client's bearer header exists yet.
- **Failures are returned as a `final` step with `confidence: 'low'`** (model unavailable, budget exhausted, refused tool), never as an HTTP error, because the client discards error bodies. No new step type is ever emitted without the frontend owner: an unknown type renders nothing.
- LLM calls on the calc path (target 4–5): classify (Nano) → `next_action` writes plan + code in one Super call, reasoning on → browser runs → verify is **deterministic** (result parses, required keys present, units present, finite, range checks, two methods agree) → explain (JSON, reasoning off) → B8.
- **Two methods in one script**: the code computes the answer by two independent methods and reports both, so verification costs no extra step or Super call. A separate second run is used only for repair.
- Canonical result (to agree with P4): `result = {"answer": {"value", "unit"}, "check": {"value", "unit", "method"}, "values": {name: {"value", "unit"}}}`.
- Tool calling: native if G10 confirms; fallback = free text with one fenced code block parsed deterministically (keeps reasoning on for coding, avoids code inside JSON strings).
- `tools.py`: registry of exactly 6; unknown → refuse. Every `next_action` counts toward the 4 steps, including searches and diagrams — so notes search runs once up front (not a counted step), and the prompt says so. Stubs behind interfaces: `search_my_notes` (NR, 17 Oct), `web_search` (S4, 19 Oct), `schedule_reminder` (D6, 18 Oct), `make_quiz` (Q1). `draw_diagram` is mine: returns Mermaid text for `final.diagram_mermaid`, validated for length and type only (P3 sanitises and renders).
- Bridge:
  - State saved before every return; the last issued step is stored.
  - The step sequence is **derived server-side** (the client does not echo anything back today). A repeat of the last processed result **returns the stored next step** (safe retry).
  - Row lock per solve for concurrent posts. Every request checked against the solve's `user_id`.
  - Caps sized to what the worker really sends: request body limit about 3 MB (4 PNGs of 500 KB become about 2.7 MB as base64); the 500 KB check is on decoded PNG bytes with the PNG signature verified; stdout over 64 KB plus the worker's truncation note is truncated, not rejected; the 16 KB result check allows a little slack for re-serialisation.
  - Figures go to Storage through the backend's helper (C1, 12 Oct; in-memory fake before that). Until the page CSP allows the Storage origin, `final.figures` returns `data:image/png;base64,…` URLs, which the UI already renders.
  - `GET /solve/{id}` to re-fetch the pending step after a restart (contract request).
- Limits: 4 steps; 90 s **of server wall-clock from issuing the first `next_action`**, with confirm waiting excluded. Wall-clock between issuing a step and receiving its result is used rather than the client's `ms`, because a sandbox timeout reports `ms: 0`. The remaining budget is passed into every model call; out of budget → honest partial answer.
- Hard path: when verification fails twice or methods disagree, one cross-check call (Ultra if listed, else second Super sample with a different method); answers must agree, else the answer is flagged low-confidence.
- `final`, in P3's typed shape: `numbers` = flat `{name: number}` built from `values` + answer (units go in the key name or the text, since the type has no unit field); `figures` = URLs after Storage upload (P3 accepts URLs or data URLs); `sources` = `{title, url?}` from notes hits/web results; `confidence` = high (methods agree, B8 clean) / medium / low (flagged).
- Deterministic verify also rejects any string-typed value where a number is expected (the worker stringifies sympy and Decimal values).
- The web client never retries a POST, so the duplicate-result case is rare; the safe-retry design stays because it costs little and a restart can still interrupt a response.
- Notes and upload text enter prompts as quoted data (§14 prompt-injection row).
- Demo/cached path and the spend-cap path call into the loop through one `deps` switch; owner to be agreed (item 16).
- First S2 PR also carries the record/replay transport moved out of A3.
- Done when: 3 golden problems solved end-to-end through the Node runner, median ≤ 60 s. CI: replay; live: manual workflow or local Docker.

### S2b — solver prompts (6 h) · `api/app/agent/prompts/`
- Prompts for classify, plan+code, repair, explain. Explanations must print values with ≥ 4 significant figures and only values present in `result`.
- Code rules taken from how the worker behaves:
  - `result` is a dict with string keys; every numeric value is cast with `float()`; no NaN/inf (the run is rejected).
  - The script is self-contained: no variables survive between steps.
  - Import matplotlib in the first script if a plot may be needed (a later first use forces a slow worker restart). Leave figures open; never call `plt.close()`, `savefig` or `show`.
  - Keep printed output short; on failure only the last 600 characters of the error reach the repair prompt, and no prints.
- Own smoke script over 10 problems (also serves TD1). Longer-term target is §11's ≥ 85% on the 40-problem set.
- Done when: smoke subset ≥ 8/10 correct.

### B8 — number guardrail (4 h) · `api/app/agent/guardrail.py`
- Pure function `check(answer_md, allowed) -> report` (reused by P2's CHX).
- **Allowed set (tight)**: scalar named values in `result` only — no arrays, no `series`, no bulk stdout; numbers in the question text; integers ≤ 10; constants allowlist (R, g, N_A, k_B, F, σ, c, h, 273.15, 101325 …).
- **No scale shifts.** v1's ×100 / ×1000 relaxations are dropped: together they would pass any decimal-point or unit slip. Instead the code must emit every displayed value, in its display unit, inside `result` (e.g. both `X` and `X_percent`, both `T_K` and `T_C`).
- Tolerance ±0.5% relative as specified; exact zero and |x| < 1e-12 compared absolutely. Rounding is handled by the ≥ 4 sig-fig prompt rule, not by loosening the check.
- Parser: plain, thousands separators, `1.2e-3`, `1.2×10^-3`, LaTeX `\times 10^{…}`, bare `10^{-3}`, Unicode minus, `\frac` parts. Skipped tokens: digits inside identifiers and units (`C_{A0}`, `T_2`, H2O, m^2, s^{-1}), ordinals ("2nd-order", "Step 3").
- Open for team decision (not built unless agreed): unit-conversion factors 60, 100, 1000, 3600 as allowed constants.
- Fail → regenerate once → flag. If cut-line step 1 is applied: flag only. The flag needs a field in `final` (contract request).
- Done when: a planted wrong number is caught; tests also cover a decimal slip, a kPa/Pa slip, and that correct 4-sig-fig rounding passes.

### Q1 — quiz engine (8 h)
- Schema (one `items` list, item `type` tagged): MCQ (stem, 4 options, correct index, misconception per wrong option, explanation), Numerical (stem, `key_code` computing the key by two methods in one script, unit, tolerance, worked solution **with value placeholders**), and a Subjective slot (stem + rubric) whose generation is P2's QS. Common fields: `topic`, `source` (upload/slide, for D5), `tags` (company/round, for IB).
- Numerical keys are computed in the browser when the quiz opens. If the script errors or its two methods disagree, the client drops that item and reports it (needs one contract line); the worked solution is filled from the computed values and checked by B8.
- Schema + mock JSON to P3 by 16 Oct.
- Done when: 10 generated quizzes pass schema validation + key re-check through the Node runner (replay in CI).

### CH1a — CSTR template + frozen format (4 h) · `chemlab/templates/cstr.py`
- Interface: `run(inputs: dict, series: bool = True) -> dict`, JSON-safe (no numpy types; NaN/inf replaced by null + a warning, because the worker serialises with `allow_nan=False`), pure numpy/scipy, no I/O, < 1 s. The agent path runs in the worker's `solve` mode (16 KB cap) and calls `series=False`; ChemLab screens run in `chemlab` mode (no cap) with `series=True`, arrays still capped at a few hundred points for the 250 ms slider target.
  ```
  {template, version, ok, errors[{code, message, field}], warnings[],
   inputs{name:{value, unit}}, outputs{name:{value, unit}},
   steady_states[{T, X, CA, Da, stable}], n_steady_states,
   series{name:{x, y, x_unit, y_unit}}, geometry{...}}
  ```
  plus module `SPEC` (name, unit, default, min, max, required) — the single source for sliders, validation and CH3. Each template declares its own canonical units (reactors: mol/m³, m³/s, K, J; distillation: kmol/h, mole fractions).
- Physics (n ≥ 0 enforced; isothermal mode uses T = T0, stated in `SPEC`):
  - Scan conversion X, not temperature. Mole balance gives k = X / (τ·CA0^(n−1)·(1−X)^n), so T_MB(X) = Ea / (R·ln(k0/k)) explicitly for any n — no inner root-solve.
  - Steady states are roots of the heat residual `G − R` (generation minus removal, UA(T−Ta) + flow term) evaluated on a dense vectorised grid and refined with `brentq`; no division by ΔHr, so ΔHr = 0 is safe. T bounded by min(T0, Ta) and max(T0, Ta) + ΔT_adiabatic.
  - Every steady state returned with a stability flag (up to three branches; the middle one unstable) and its own Damköhler number.
  - X-vs-τ curve from the same parametrisation, sweeping **V** (v0 also appears in the energy balance); Levenspiel series.
- Templates import **only numpy and scipy** (prefer `scipy.optimize` and `scipy.integrate`, which the worker pre-imports). The worker decides what to load by scanning the submitted code, so a template that imported matplotlib or sympy internally would fail when called from the one-line CH3 script.
- I create `chemlab/pyproject.toml` mapping the package name `chemlab` to `templates/`, so `from chemlab.cstr import run` works under `cd chemlab && pytest` and matches what the cloud hook installs.
- Template files must be written into the Pyodide file system during worker start-up, before lockdown. I give the sandbox owner the exact file list and import name with the draft format.
- Draft format published 14 Oct; frozen at merge on 18 Oct.
- Done when: 2 golden cases (isothermal + adiabatic with multiple steady states) within 1% in pytest and the Node runner.

### CH3 — template picking (3 h)
- Nano (JSON, reasoning off) → `{template | none, inputs: {name: {value, unit}}}`.
- Conversion to the template's canonical units from a small explicit table only (°C→K for absolute temperatures, never for per-degree quantities; min/h→s; mol/L→mol/m³; kJ/cal→J; %→fraction). Unknown unit → general solver. Sign of ΔHr and k0 units vs n are validated against `SPEC` ranges.
- Code is built server-side as `from chemlab.cstr import run; result = run(<repr of validated Python values>)` — `repr`, not `json.dumps`, and no model-written string is ever interpolated.
- A template run is one step and needs no second-method verify (the template is golden-tested).
- Inverse questions ("find V for X = 0.9") do not fit a forward template: the general solver handles them and may `import chemlab`. Scoring rule to agree with P4: "none" is the correct pick for those.
- Answer reported in canonical units with the unit stated, plus the question's unit when it differs.
- Done when: ≥ 9/10 labelled chem questions pick the right template (labels: item 15).

### CH1b — PFR, batch, McCabe-Thiele (9 h)
- PFR and batch: closed-form solutions for isothermal nth-order kinetics as the primary result; `solve_ivp` (rtol 1e-8) as the cross-check and for profiles; concentration clamped at zero for n < 1. Rate constant input: `k` directly, or `k0, Ea, T` (in `SPEC`). PFR: V + tube diameter → length.
- McCabe-Thiele: constant α, CMO, total condenser, reboiler = a stage; D, B from F, zF, xD, xB; q-line with tolerance around q = 1 (vertical) and q = 0 (horizontal); Rmin from the q-line/equilibrium intersection; R or R/Rmin (default 1.3).
  - Validation → structured errors: xB < zF < xD, α > 1, R > Rmin, stage count capped (200) so a near-pinch case cannot hit the 10 s kill.
  - Real trays = ceil((N − 1)/Eo), Eo = 0.7.
  - Souders-Brown (illustrative): K = 0.07 m/s at 0.6 m spacing; ρV ideal gas from MW, P, T inputs (defaults documented: top conditions, distillate MW); molar → mass flow on a per-second basis; sized on the larger of V = (R+1)D and V′ = V − (1−q)F; no flooding fraction unless the golden case uses one. All choices written in the docstring and shown on screen.
  - Stage-count convention (whole stages, feed-stage switch rule) in the docstring and matched to the golden cases.
- Done when: 6 golden cases within 1% (incl. q = 1 and q = 0) in pytest and the Node runner. If cut-line step 3 drops batch: 4 cases, golden set X/38.

### F4, F8, F9
- F4 README: what/why, setup ≤ 5 commands, demo mode, architecture diagram, Nemotron usage, licences. Must survive F5's fresh-clone test.
- F8: Devpost text, Track 2, tools feedback from the log. I draft; you paste.
- F9: §15 checklist, two people tick each line. You press Submit; I verify the page shows Submitted.

### SHOULD (only if every MUST due that day is merged; latest 23 Oct)
- CH2 (6 h): 40-compound JSON exported once from `chemicals` with source per value; flash (bubble/dew check, then Rachford-Rice); HX (LMTD co/counter; 1-2 shell-and-tube F-correction and ε-NTU). Done when: flash + HX golden cases within 1%.
- CH5 (6 h): recycle flowsheet (`fsolve`) + pipe/pump via `fluids`. Done when: recycle balance closes within 0.5%.
- QSX (2 h): dispute flow. Done when: dispute stored and shown.

## 6. Cross-team dependencies and how I avoid waiting

| I need | From | Due | If late |
|---|---|---|---|
| FastAPI skeleton + `api/pyproject.toml` | A2 (owner unconfirmed) | 7 Oct, not merged | A3 needs neither; S2's routes do — raise at the 11 Oct check-in |
| `llm_calls`, `solves` tables | P2 A4 | 9 Oct | Recorder/store protocols + in-memory versions; own dev Supabase |
| Photos | P4 T3 | 9 Oct | My own photos first |
| Upload storage + Storage helper | P2 C1 | 12 Oct | C2 takes bytes; S2 figures use a fake store |
| Sandbox / Node runner | P3 S1 / P2 S1b | 12 / 13 Oct | Fake runner with canned results for loop tests; Node runner outside Docker only for my own template code and only if the team agrees (§3.6 says Docker-only) |
| Golden set | all S3 | 10 Oct | My 10 first |
| Notes search, web search, scheduler | P2 | 17–19 Oct | Stubs behind interfaces |
| Eval runner | P4 T4 | 16 Oct | Own smoke script |
| 10 labelled chem questions | P4 | before 19 Oct | I draft, P4 approves |

What others get from me, and when: A3 9 Oct (plan 8) · stub loop 12 Oct, real S2 15 Oct (plan 14) · Q1 mock 16 Oct, engine 18 Oct (plan 17) · template format draft 14 Oct, frozen 18 Oct · CH1b 22 Oct.

## 7. One contract-change request to send today

The contract is not written down in the repo; the only concrete version is P3's `web/src/api/types.ts`. Per AGENTS.md rule 3 this goes out as a PR that touches the contract plus a team note. All additions are **optional fields**, so P3's current code and mock keep working unchanged.
1. `GET /api/v1/solve/{id}` returning the pending step (resume after a restart or a reloaded tab). Step sequencing is derived server-side, so nothing changes in the result body.
2. Optional `progress` label on each step (the plan says "progress streamed" but defines no streaming endpoint; proposal: no SSE, the label is shown per step).
3. `final`: optional `flags[]` (B8) and `chemlab {template, inputs}` (for "Open in ChemLab keeps the inputs").
4. `/uploads/{id}/read`: add `figure_description`.
5. Quiz: a way for the client to report an item whose key failed.
6. Canonical `result["answer"]` shape (with P4, for T4).
7. Confirm the four "gap" choices already in `types.ts` (`numbers`, `figures`, `sources`, `confidence`) and the envelopes `{solve_id, step}` / `{step}` as the agreed contract, and put the whole thing in `docs/` so there is one written copy.
8. Confirm round-trip: client re-posts `/solve {question, upload_id, confirmed: true}` after the student approves the extracted text.
9. Failures arrive as a `final` step with `confidence: 'low'`, not as HTTP errors (the client does not read error bodies).
10. Frontend asks: add the API and Supabase origins to `connect-src` and `img-src` in `vercel.json` as §3.6 specifies; send the bearer token on API calls; say when both land.

## 8. Risks

- **R1 — schedule.** See section 2. A3 is the only thing worked on until merged.
- **R2 — package path.** Files are `chemlab/templates/cstr.py`; the import is `from chemlab.cstr import run`. Must be settled with P3 before CH1a, and pytest must use the same mapping.
- **R3 — streaming.** Covered by contract request 2.
- **R4 — Docker.** §3.6: the Node runner runs only inside `docker --network none`. Without Docker locally, model-written code can be executed only in CI.
- **R5 — Node version.** No pin is written anywhere. The web lockfile requires Node ≥ 22.12 (Vite 8, Mermaid's parser), so this machine's 20.18 is too old. Fix: install Node 24 LTS and ask the team to record the pin in `docs/decisions.md`. Whether `node --permission` is stable on the pinned version is still to be checked.
- **R13 — no backend, DB or CI work is merged, and role ownership is unconfirmed.** Every P1 ticket after A3 leans on the backend (A4, C1, S1b). If A2/A4 are not in by 10 Oct, raise it at the 11 Oct check-in; my in-memory stores keep me moving but "merged and deployed" cannot be met without them.
- **R14 — the frontend branches are unmerged.** The contract types and the worker live only on feature branches and can still change. I build against them but pin nothing until they merge.
- **R15 — CSP and auth gaps block real integration.** Until the page CSP allows the API origin and the client sends a token, a deployed frontend cannot reach my endpoints at all (`npm run dev` hides this; `vite preview` and Vercel show it).
- **R16 — the CI runner does not exist yet (S1b).** Whether it will serialise results and apply caps the same way as the browser worker is unknown; golden runs must use the same rules.
- **R6 — Python versions.** Pyodide is 3.14; which Python runs chemlab pytest in CI is not specified. Only long-stable scipy APIs used.
- **R7 — golden values.** ChemLab goldens are due 10 Oct, before the templates exist, and nobody is assigned to author them. Cases must state constant α and CMO, or they will not match within 1%.
- **R8 — G10 surprises** (tool calling, reasoning toggle, JSON mode, latency). Fallbacks are built in from the start.
- **R9 — router ownership.** `routers/solve.py` and `routers/uploads.py` are in P2's area. Default: I write `solve.py`, P2 reviews.
- **R10 — TD1 has no eval runner.** §10 schedules a full eval on 15 Oct but T4 lands 16 Oct; my smoke script covers it.
- **R11 — OneDrive.** Sync locks on `.git`, `.venv`, `node_modules` cause failures; work in a non-synced folder.
- **R12 — data rule.** §5.2 forbids putting real student data into an AI assistant; P4's labelled photos need an explicit OK or synthetic stand-ins.

## 9. How I will work

- Branch per ticket named like the team's (`a3-llm-client`), cut from `main`. PR title starts with the ticket ID and uses the repo's PR template (done-when, how tested, contract touched y/n).
- One ticket per PR and about 400 changed lines (AGENTS.md rules 8–9). S2 and CH1b cannot satisfy both, so they are split only if the team agrees (item 13); otherwise they go as one larger PR each.
- Tests first; `ruff` + `mypy` + `pytest` green before each PR. New dependencies are named with a reason in the PR (rule 10). Nothing is pushed, merged, posted or spent without your go-ahead.
- After each ticket: feedback log, tracker, spend so far.
- Keys only in env vars.

### Tracker
| Item | Status |
|---|---|
| Python 3.12 installed | done 8 Oct |
| Plan v1 → reviewed → v2 → repo inspected → v3 | done 8 Oct |
| Repo located and read | done 8 Oct |
| Git identity, `gh` login, clone location, A2 timing, hours | waiting on you (section 3, items 1–5) |
| Nebius key, WSL + Docker engine, Node 24, dev database | waiting on you (items 6–11) |
| G10, A3, S3 share, stub loop, C2, S2, S2b, B8, Q1, CH1a, CH3, CH1b, F4, F8, F9 | not started |

## 10. What the review changed (v1 → v2)

| Finding | Change |
|---|---|
| Schedule did not fit (39.5 h in 7 days) | Honest re-dating; stub loop 12 Oct; decision asked for today |
| No way to meet model-dependent "done when" in CI | Record/replay transport in A3; CI key question raised; Docker recommended |
| B8 relaxations let unit and decimal slips through | Scale shifts dropped; allowed set narrowed to scalar `result` values; display-unit values emitted by code |
| Step idempotency could strand a solve; contract additions unrequested | Repeat returns the stored next step; row lock; one contract-change request |
| 90 s not enforceable; clock undefined | Deadline passed into every model call; clock defined |
| 4-step budget only worked for pure `run_python` | Two methods in one script; deterministic verify; notes search not a counted step |
| Quiz keys could not be validated; worked solutions would contain invented numbers | Client drops/reports failing items; placeholder solutions + B8; schema fields for QS, D5, IB |
| Template format vs 16 KB cap; no errors or steady-state list | `series` switch, `ok/errors`, `steady_states[]`, JSON-safe values |
| CSTR method: division by ΔHr, slow inner solve for order n | Scan on X with explicit T_MB; heat-residual roots; stability flags; sweep V |
| CH1b: loose ODE tolerance, no iteration cap, vague sizing | Closed forms + tight ODE; validation and cap; sizing choices stated |
| CH3: `json.dumps` is not Python; "SI" converter too broad; inverse questions | `repr` of validated values; per-template canonical units and a small table; "none" rule |
| A3: strip-before-parse impossible inside instructor; no budget hook; solver fallback undefined | Own validate-and-repair order; `BudgetGuard`; typed error |
| S2 scope gaps | `need_confirm`, `draw_diagram`, DB-free core for T4, auth check, hard path, `final` fields |
| Format reached P2/P3 one day before their deadlines | Draft format 14 Oct |
| Missing prerequisites | Section 3 rewritten |

## 11. What the repo changed (v2 → v3)

| Repo fact | Change |
|---|---|
| `main` has only the A1 scaffold; no `api/pyproject.toml`, no CI | A3 depends on A2's manifest; "passes in CI" waits for T1; R13 added |
| Tooling is pip + `pyproject.toml` (AGENTS.md, cloud hook) | Dropped `uv sync`; pip in a 3.12 venv |
| AGENTS.md rule 8: one ticket per PR | PR splitting needs team OK |
| AGENTS.md rule 3: contract change = PR + team note | Section 7 goes out that way; all additions optional |
| P3 already typed the contract and filled four gaps | `final` fields follow P3's types (`numbers` flat, etc.) |
| Worker has `solve` and `chemlab` modes; 16 KB cap only in `solve` | Series allowed in ChemLab mode; `series=False` on the agent path |
| Worker serialises with `allow_nan=False` | Templates and solver code must never emit NaN/inf |
| Web client never retries POSTs; no GET for a pending step | Safe-retry kept as low-cost; `GET /solve/{id}` requested for resume |
| No template loading in the worker yet | R2 still open with P3 |
| `@types/node` 24, Vite 8 on P3's branches | Node 24 requested |
| Linked branch is a cloud-session hook only | Work goes on `a3-llm-client` from `main` |
| Docker installed but engine down, WSL missing; git identity and `gh` still missing | Section 2 and 3 corrected |

### Second review (17 findings on v3, all applied)

| Finding | Change |
|---|---|
| Page CSP blocks the API and Storage images | Figures returned as data URLs for now; CSP ask added; R15 |
| Client sends no auth, no `upload_id`; confirm has no return path | Confirm round-trip proposed; auth switchable locally |
| One committer for all work; roles unconfirmed | "Who holds which role" is now a start question |
| A3 contradicted itself on the missing manifest | One PR, no manifest, A2 untouched; record/replay moved to S2 |
| Client drops HTTP error bodies; failures post `ms: 0`, 600-char error | Failures as `final` steps; wall-clock budget; repair prompt sized to it |
| Worker stringifies non-JSON values | `float()` rule in prompts; verify rejects strings |
| Template loading constraints; no chemlab manifest owner | numpy/scipy-only rule explained; I create `chemlab/pyproject.toml` |
| Solve screen already built on its own mock | HTTP stub dropped; loop interface delivered instead |
| Server caps would reject legitimate worker output | Caps resized (3 MB body, decoded-byte check, truncate stdout) |
| Figure and globals behaviour | Added to solver prompt rules |
| Node floor is provable (≥ 22.12) | R5 made firm |
| Rule 13 has no exceptions | Ask changed to synthetic or consented photos |
| `gh` not needed to push | Made optional |
| AGENTS.md web commands do not match the web package | Heads-up added (item 17) | C:\Users\Supreeth\OneDrive\Desktop\p1project\P1_PLAN.md this is the plan we should start working on it from today ok so first see if we have all the things set up and all the environment set up