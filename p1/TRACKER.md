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
| G10 | Model test (my part of G-all) | MUST | 1.5 | 0 | needs Nebius key + network |
| G-rest | Rest of week-0 gates | MUST | 2 | 0 | |
| K0 | Kickoff | MUST | 2 | 0 | |
| A3 | LLM client | MUST | 6 | 75 | PR studyforge-team/studyforge#6 open; 41 tests green; live smoke + G10 wait for key and network; needs reviewer |
| S3 | 10 golden problems + ChemLab cases proposed | MUST | 3 | 0 | |
| C2 | Vision read | MUST | 7 | 25 | branch c2-vision: image/PDF prep + read_question with fake model (36 tests); real model + 7/8 photos wait for Nebius |
| S2 | Agent loop + browser bridge | MUST | 16 | 25 | branch s2-agent-loop (stacked on a3): DB-free core, 81 tests; routes need A2, golden runs need Nebius + runner |
| TD1 | Test day 1 | MUST | 4 | 0 | |
| S2b | Solver prompts | MUST | 6 | 0 | |
| B8 | Number guardrail | MUST | 4 | 50 | branch b8-guardrail pushed; 62 tests; PR not opened |
| Q1 | Quiz engine | MUST | 8 | 25 | branch q1-quiz: schema, key checks, mock JSON (92 tests); model generation waits for Nebius |
| CH1a | CSTR template + frozen format | MUST | 4 | 50 | branch ch1a-cstr: 30 tests + 20k random cases; Pyodide/Node-runner check waits for S1b + jsDelivr |
| CH3 | Template picking | MUST | 3 | 0 | |
| CH1b | PFR, batch, McCabe-Thiele | MUST | 9 | 50 | branch ch1b-templates (stacked on ch1a): 158 chemlab tests; official goldens are P4's |
| F4 | README | MUST | 3 | 0 | |
| TD2 | Test day 2 | MUST | 4 | 0 | |
| F2 | Final fixes | MUST | 3 | 0 | |
| RTD | Release test day | MUST | 4 | 0 | |
| SU | Standups | MUST | 5.5 | 0 | |
| F8 | Devpost text | MUST | 3 | 0 | |
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
