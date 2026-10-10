# P1 tracker (Engine & ChemLab)

Personal progress tracker for the P1 plan v3. Lives on branch `p1-tracker` only; never merged.
Run `python p1/progress.py` for the percentage.

**How % is counted** (weighted by planned hours; a ticket is only 100 % when merged, per §5.3):
0 = not started · 25 = code started · 50 = code + tests green locally · 75 = PR open (CI green when CI exists) · 100 = reviewed + merged.
Shared items use the same scale. SHOULD tickets are reported separately and never count toward the MUST %.

## Standing rule: Nebius deferred (8 Oct, from Supreeth)

Nobody on the team has a Visa/Mastercard card for Nebius yet. Until that changes:
- Build every part of the plan that does not need Nebius, against fakes and mocks.
- Do NOT change the plan's dates.
- Everything below is parked and must be done together once Nebius is available
  ("Nebius integration pass"):
  - G10 probe (`p1/g10_probe.py`) and filling model IDs/prices in `config/models.yaml`
  - A3 live smoke test (`TF_LIVE=1`)
  - C2 vision read: real calls and the 7/8 photo test
  - S2 done-when: 3 golden problems end-to-end with the real model
  - S2b done-when: smoke subset >= 8/10 with the real model
  - Q1 done-when: 10 generated quizzes; CH3 done-when: 9/10 template picks
  - Replay fixtures recorded from real calls
- Model use: Opus 5.5 orchestrates and does hard design/physics; Sonnet 5.5 subagents do
  well-specified coding. Keep token use low without lowering quality.

## Tickets

| ID | What | Kind | h | % | Note |
|---|---|---|---|---|---|
| G10 | Model test (my part of G-all) | MUST | 1.5 | 25 | probe script ready (p1/g10_probe.py); running it needs Nebius |
| G-rest | Rest of week-0 gates | MUST | 2 | 0 | |
| K0 | Kickoff | MUST | 2 | 0 | |
| A3 | LLM client | MUST | 6 | 100 | merged 9 Oct (studyforge-team/studyforge#6); live smoke test + G10 still wait for Nebius |
| S3 | 10 golden problems + ChemLab cases proposed | MUST | 3 | 75 | branch s3-golden-proposals: 10 problems + 8 ChemLab cases, two methods each, verify script ALL OK; waits for P4 review |
| C2 | Vision read | MUST | 7 | 75 | c2-vision + upload_reader wired (s2-wiring); real model + 7/8 photos wait for Nebius |
| S2 | Agent loop + browser bridge | MUST | 16 | 75 | s2-agent-loop + s2-wiring (B8, CH3, C2 wired); Postgres store needs A4; golden runs need Nebius + S1b runner |
| TD1 | Test day 1 | MUST | 4 | 0 | |
| S2b | Solver prompts | MUST | 6 | 75 | s2b-prompts: prompts + smoke harness (292 api tests); 8/10 score needs Nebius + runner |
| B8 | Number guardrail | MUST | 4 | 75 | b8-guardrail; on by default in the loop (s2-wiring) |
| Q1 | Quiz engine | MUST | 8 | 75 | q1-quiz: schema, key checks, mock, generator, make_quiz service (107 tests); 10 real quizzes need Nebius |
| CH1a | CSTR template + frozen format | MUST | 4 | 75 | branch ch1a-cstr: 30 tests + 20k random cases; Pyodide/Node-runner check waits for S1b + jsDelivr |
| CH3 | Template picking | MUST | 3 | 75 | ch3-template-pick, wired into the loop; 9/10 picks need Nebius + P4 labels |
| CH1b | PFR, batch, McCabe-Thiele | MUST | 9 | 75 | branch ch1b-templates (stacked on ch1a): 158 chemlab tests; official goldens are P4's |
| F4 | README | MUST | 3 | 25 | f4-readme-draft: draft, TODOs for after A2/G10 |
| TD2 | Test day 2 | MUST | 4 | 0 | |
| F2 | Final fixes | MUST | 3 | 0 | |
| RTD | Release test day | MUST | 4 | 0 | |
| SU | Standups | MUST | 5.5 | 0 | |
| F8 | Devpost text | MUST | 3 | 25 | docs/devpost-draft.md on f4-readme-draft; results TBD after Nebius |
| F9 | Final checks + submit | MUST | 2 | 0 | |
| CH2 | Compounds, flash, HX | SHOULD | 6 | 0 | only if all MUST due are merged |
| CH5 | Recycle flowsheet + pipe/pump | SHOULD | 6 | 0 | |
| QSX | Dispute flow | SHOULD | 2 | 0 | |

## Setup checklist (plan §3)

- [x] Cloud environment: Python 3.12 venv, ruff/mypy/pytest, Node 22.22 (≥ 22.12), git push works
- [x] P1 libraries install on 3.12 (openai, pydantic, pyyaml, pypdfium2, Pillow, numpy, scipy)
- [ ] Cloud setup hook merged (studyforge-team/studyforge#4: needs ticket ID + reviewer)
- [ ] Network allowlist: api.tokenfactory.nebius.com, cdn.jsdelivr.net, *.supabase.co, api.tavily.com, api.telegram.org
- [ ] `TF_API_KEY` (personal dev key) set as an environment secret
- [ ] Spend ceiling agreed (proposed: $5 for G10 + A3)
- [ ] One question photo with no personal data (G10 vision call)
- [ ] Roles confirmed; A3 reviewer named
- [ ] Team note + contract request (plan §7) sent
- [ ] Hours/day for 8–14 Oct confirmed
- [ ] Dev Supabase project (from ~10 Oct)
- [ ] Docker images pull (Docker Hub returned 429; needed ~12 Oct)

## Log

- 8 Oct: tracker created. Environment checked. A3 started on branch `a3-llm-client`.
- 8 Oct: A3 code + mocked tests done on `a3-llm-client` (38 pass, 1 live test skipped; ruff, mypy --strict clean; works on openai 1.109 and 3.26). ~1,100 lines (≈560 code, ≈500 tests), over the ~400 guideline: flag to reviewer. Open for team: own JSON repair wrapper instead of instructor (stack change), dependency pins for A2.
- 8 Oct: A3 PR opened (studyforge-team/studyforge#6). Added: thinking flag optional per role (vision sends none), finish_reason, empty-choices guard. G10 probe script ready at p1/g10_probe.py. Token Factory still denied by the environment's network policy; TF_API_KEY not set.
- 8 Oct: Nebius deferred (see standing rule). Built without it: B8, Q1 (model-free), CH1a, CH1b, C2 (model-free), S2 core. Sonnet 5.5 helpers did B8, Q1, C2, PFR/batch, McCabe; Opus reviewed and re-checked each. Found and fixed: S2 "safe retry" by identical body would loop forever on a deterministic error (no step number in the contract) -> removed, contract request needed. Licence flag: Pillow (MIT-CMU) and pypdfium2 (BSD-3/Apache) not strictly on the allow list.

## Snapshot 8 Oct evening (what is built, where)

Budget-hours view (not clock time): ~61 of 100 MUST hours are buildable without Nebius;
~44 h of that is built (~72% of the buildable part). Merge-based % (progress.py) is lower
because nothing is reviewed/merged yet.

| Branch on GitHub | Ticket | Built | Left without Nebius | Left with Nebius |
|---|---|---|---|---|
| a3-llm-client (PR #6) | A3 | client, registry, retries, deadlines, cost log, JSON repair | none | G10 IDs/prices, live test |
| b8-guardrail | B8 | guardrail, 62 tests | wire into S2 | none |
| ch1a-cstr | CH1a | CSTR + shared format | Pyodide/runner check (S1b, jsDelivr) | none |
| ch1b-templates (on ch1a) | CH1b | PFR, batch, McCabe-Thiele | runner check | none |
| s2-agent-loop (on a3) | S2 | loop core, routes, replay transport | Postgres store (A4), wire B8/CH3/C2 | 3 golden runs |
| c2-vision (on a3) | C2 | image/PDF prep, read_question | none | real calls, 7/8 photos |
| q1-quiz | Q1 | schema, key checks, mock | generator with fake model | 10 real quizzes |
| ch3-template-pick (on ch1b) | CH3 | units, validation, code builder | wire into S2 | 9/10 picks |
| s3-golden-proposals (on ch1b) | S3 | 10 problems + 8 ChemLab cases | P4 review | none |
| p1-tracker | - | this tracker, progress.py, g10_probe.py | - | run G10 |

Next without Nebius: integrate B8+CH3+C2 into the loop (fake model end to end), Q1 generator,
S2b prompt polish + smoke script, F4/F8 drafts. Backend tickets of P2/P4 (A2, A4, C1, S1b, T1)
only with the team's OK.

## Workflow

Opus 5.5 orchestrates: designs hard parts (physics, loop, formats), writes specs. Sonnet 5.5
helpers build well-specified tickets in isolated worktrees, in parallel. Each ticket: own branch,
tests first, ruff + mypy + pytest green. Opus re-runs every helper's checks and spot-checks
numbers independently before pushing. Push every finished branch; PRs only with Supreeth's OK
(A3's is open). Tracker updated after each batch.

## Snapshot 8 Oct night

All buildable-now P1 work is done: ~52 of the ~61 buildable budget hours (~86%). What is
left without Nebius is blocked by others or by the calendar: Postgres store (needs A4),
Pyodide/runner checks (S1b + jsDelivr), test days TD1/TD2/RTD and F2, final README/Devpost.
New branches this round: s2-wiring (B8+CH3+C2 in the loop), s2b-prompts (prompts + smoke
harness), q1-quiz updated (generator), contract-p1-requests (docs/api-contract.md + team
note), f4-readme-draft (README + Devpost drafts).
Merge order for stacked branches: a3 -> s2-agent-loop -> s2-wiring -> s2b-prompts;
ch1a -> ch1b -> ch3 (ch3 also needs b8 and c2 before s2-wiring).

## Decision 8 Oct (Supreeth): no new pull requests for now (LIFTED 10 Oct)

All work stays on its pushed branches. Do NOT open pull requests until the reviewer has
reviewed the work; open them only after that, in the merge order above. Only A3's PR (#6)
and the setup-hook PR (#4) exist. Verified 8 Oct night: every branch matches GitHub, no
unpushed commits, no uncommitted changes.
- 10 Oct: A3 merged into main (#6, merge c2bc388). Re-verified after a session restart: all 15 branches match GitHub, 0 unpushed commits, no uncommitted changes.
- 10 Oct: checked an outside AI review claim by claim. False: parser "crashes" on <think> inside JSON (tested: worst case one repair call), guardrail "burns a tool step" (regenerate is not a counted step), s1-chemlab-mount "deadlocked" (it skips cleanly until chemlab files exist; its self-test expects our CSTR defaults and they match), "tracker false" (it reports merge-based %). Valid: solver prompt did not keep arrays out of result (16 KB cap) -> fixed on s2b-prompts (e3a8b0e). Partly valid: a late matplotlib/sympy import costs a worker respawn (seconds), but the client already retries it automatically; preloading all four packages for every solve would slow every solve, so not done. For P2: A2-fastapi-health's api/pyproject.toml lacks openai and pyyaml, which A3 on main needs (listed in PR #6). Verified: none of our branches or main were changed by that tool.
- 10 Oct: Supreeth lifted the no-PR rule. Opened PRs (not merged: AGENTS.md rule 11 needs a teammate review):
  #16 B8, #17 CH1a, #18 CH1b (base ch1a), #19 C2, #20 Q1, #21 S2 core, #22 contract note (S2),
  #23 CH3 (base ch1b), #24 S2 wiring (base s2-agent-loop; needs #16 #19 #23 first), #25 S2b (base s2-wiring),
  #26 S3 proposals (base ch1b), #27 F4/F8 drafts (draft PR). All 12 merged cleanly into main in a dry run.
  Reviewers requested: ragaveeru-bit (backend), samarthkombli-ops (chemlab/contract), shreyasgoudar251ch056 (Q1, S2b, S3).
- 10 Oct: Supreeth chose a stand-in model pass (free OpenAI-compatible model now, Nebius switch at the end). Added the hand-over skill `.claude/skills/context/` (SKILL.md = full context + next job, plan-v3.md = the P1 plan, next-session-prompt.md = text to paste into a new session). Network check from the cloud session: Token Factory, NVIDIA API, Groq, OpenRouter and jsDelivr blocked; Gemini API reachable.
