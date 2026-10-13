# P1: what is left, what can be built now, and how it plugs into Nebius (13 Oct)

Source: plan v3 (`.claude/skills/context/plan-v3.md`), section 5 SHOULD + the MUST table in
`p1/TRACKER.md`. Plan unchanged. Every MUST code ticket is merged; the remaining MUST
hours are Nebius runs (G10, live done-when checks, README/Devpost numbers) and team
events (test days, fixes, submit). So the plan's SHOULD rule ("only if every MUST due is
merged") is met and the SHOULD tickets start now.

## Status (13 Oct)
Done and merged: #48 HX, #51 compounds, #52 flash (CH2 complete), #49 recycle, #50 pipe/pump
(CH5 complete). CH3 follow-up #53 in CI. Nothing else in P1 can be built without Nebius or
another teammate (tables below).

## Build now (no Nebius, no other teammate needed)

Each is one small PR (about 400 lines or fewer), tests first, brutal review until no
findings, then merged by me. Templates follow the frozen CH1a format (`_common.py`):
`SPEC` + `run(inputs, series)`, numpy/scipy only (the browser sandbox loads nothing else),
every number cross-checked by a second independent method in pytest.

| # | PR | What | Done when |
|---|---|---|---|
| 1 | CH2: heat exchanger template | `chemlab/templates/hx.py`: duty and outlet temperature from the balance; area by LMTD (counter, co-current, 1-2 shell-and-tube with F-correction); the same areas again by e-NTU (independent check); temperature profile; shell-and-tube geometry (tube count, bundle and shell diameter) for the V2Db drawing | HX golden cases within 1% (incl. golden proposal P1-05, 7.43518 m^2), both methods agree |
| 2 | CH2: compounds + flash | `chemlab/templates/_compounds.py`: 40 compounds (MW, Tc, Pc, omega, Antoine constants + valid range), exported once from the `chemicals` library (MIT) by a script kept in the repo, source per value; `flash.py`: bubble/dew check, then Rachford-Rice (ideal, Raoult) | flash golden cases within 1%; data file regenerates byte-identical from the script |
| 3 | CH5: recycle flowsheet | `chemlab/templates/recycle.py`: mixer -> reactor -> separator -> recycle + purge, tear stream solved with `fsolve`, closed-form solution as the cross-check | recycle balance closes within 0.5% (in practice to 1e-9) |
| 4 | CH5: pipe and pump | `chemlab/templates/pipe.py`: Reynolds, friction factor (Colebrook solved numerically, Churchill as check), Darcy-Weisbach loss, fittings K, pump head and power. Plan says "via `fluids`": `fluids` is not in the browser sandbox, so the formulas are written in numpy and `fluids` (MIT) only produced the reference values in the tests | pipe/pump golden cases within 1% |
| 5 | CH3: pick the new templates | unit conversions the new templates need (W/(m^2 K), kg/s, J/(kg K), bar, ...) + tests that every template SPEC unit is convertible, so the agent can open hx/flash/recycle/pipe once a model runs | all template specs pass the CH3 checks |

Golden values: tests use hand- and library-verified values (as for CH1b). Proposals go to
`docs/golden-proposals/` for P4 (AGENTS.md rule 5); official goldens stay P4's.

## Needs someone else (I leave these and say who/what)

| Item | Blocked by | What they must build |
|---|---|---|
| QSX dispute flow (2 h) | P2: QS (subjective-answer grading) and A4 (database) | QS grading endpoint + a `disputes` table/store; then QSX = "dispute stored and shown" |
| New templates on the ChemLab page (tabs, charts) | Page owner (ChemLab.tsx, ch4a/ch4b) | Add tabs; each template already returns `series` and `geometry` in the frozen format, so it is wiring only |
| V2Db exchanger drawing | Shreyas (V2Db) | Draw from `hx` `geometry` (PR 1): shell diameter, tube length, tube count, passes |
| Agent uses the templates in production | Whoever wires the app's `Deps` (P2, `api/app/routers/solve.py` -> `get_deps`) | Pass `templates=` the SPEC map (all templates) when building `Deps` |
| Official goldens | P4 | Review `docs/golden-proposals/` |

## Needs Nebius (switch steps in `p1/standin/SWITCH.md`)

G10 probe; A3 live smoke; C2 7/8 photos; S2/S2b 8/10 golden runs (also need the S1b Node
runner from P2); Q1 10 real quizzes; CH3 9/10 picks (also P4 labels; after PR 5 the new
templates are pickable too); F4/F8 real numbers. Rehearse each on a free stand-in first.
Nothing in PRs 1-5 calls a model, so none of them changes at the switch.

## At the Nebius switch, for the new templates
1. Whoever wires `get_deps` (P2) passes `templates=load_template_specs()` (from #53). Without it
   the agent never opens a ChemLab template (true for the old four too).
2. CH3 live check (9/10 picks) on Nebius: include questions for hx, flash, pipe, recycle; the
   picker's system prompt now lists all 8 templates (about 4,500 characters).
3. After adding or changing any template: `python chemlab/tools/export_specs.py`; the api
   test `test_specs_file_in_sync_with_templates` fails until you do.
