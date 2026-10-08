# P1 tracker (Engine & ChemLab)

Personal progress tracker for the P1 plan v3. Lives on branch `p1-tracker` only; never merged.
Run `python p1/progress.py` for the percentage.

**How % is counted** (weighted by planned hours; a ticket is only 100 % when merged, per §5.3):
0 = not started · 25 = code started · 50 = code + tests green locally · 75 = PR open (CI green when CI exists) · 100 = reviewed + merged.
Shared items use the same scale. SHOULD tickets are reported separately and never count toward the MUST %.

## Tickets

| ID | What | Kind | h | % | Note |
|---|---|---|---|---|---|
| G10 | Model test (my part of G-all) | MUST | 1.5 | 0 | needs Nebius key + network |
| G-rest | Rest of week-0 gates | MUST | 2 | 0 | |
| K0 | Kickoff | MUST | 2 | 0 | |
| A3 | LLM client | MUST | 6 | 75 | PR studyforge-team/studyforge#6 open; 41 tests green; live smoke + G10 wait for key and network; needs reviewer |
| S3 | 10 golden problems + ChemLab cases proposed | MUST | 3 | 0 | |
| C2 | Vision read | MUST | 7 | 0 | |
| S2 | Agent loop + browser bridge | MUST | 16 | 0 | |
| TD1 | Test day 1 | MUST | 4 | 0 | |
| S2b | Solver prompts | MUST | 6 | 0 | |
| B8 | Number guardrail | MUST | 4 | 0 | |
| Q1 | Quiz engine | MUST | 8 | 0 | |
| CH1a | CSTR template + frozen format | MUST | 4 | 0 | |
| CH3 | Template picking | MUST | 3 | 0 | |
| CH1b | PFR, batch, McCabe-Thiele | MUST | 9 | 0 | |
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
