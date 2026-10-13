# P5 tracker: Features, drawings & release (taken over by Supreeth / ssupreethsg)

Workspace branch `p5-tracker`: never merged. A new session continues from this file alone.
Source: "StudyForge: remaining work, five members" (status 10 Oct 2026), P5 section, 45 MUST h.
Rules: AGENTS.md (14 rules) + Supreeth's takeover prompt (`.claude/skills/context/takeover-prompt.md` on `p1-tracker`).

## Audit (12 Oct 2026, main = 8769e79)

Previous P5 owner: no GitHub evidence of anyone working as P5. The fifth collaborator,
`sudhanvaad1106-spec` (admin), has 0 commits, 0 PRs, 0 branches. V2Da was built before the
split by `shreyasgoudar251ch056` (#13) and wired into ChemLab by `samarthkombli-ops` (#35).
No open PRs in the repo at all; no branch touches P5 areas, so no risk of two people on one branch.

| ID | Ticket | h | Due | Status | Evidence | What's left | Blockers |
|---|---|---|---|---|---|---|---|
| D1 | In-app intake: Web Share Target + paste box -> notice | 2 | 14 Oct | backend merged (#68); app half in review | `api/app/routers/notices.py`, migration 0004, contract §4; web: manifest share_target + Notices page (branch d1-share-inbox) | app PR; D10 export/delete must include notices (follow-up after #62) | D6 #66 also uses migration 0004 -> must renumber to 0005 |
| D1b | Web push: SW, "Turn on reminders", VAPID in env, pywebpush sender for D6 | 3 | 16 Oct | not started | no service worker / push code; `Reminder.channel: 'push'` type + mock only (P3, E1) | everything | A4 for subscriptions table; D6 (P2) calls the sender |
| D5 | Prep pack, built when opened (5 questions each linked) | 5 | 18 Oct | not started | Q1 quiz engine merged (`api/app/agent/quiz*.py`); "Open prep pack" only a mock label | everything | NR notes search (P2) not on main; `api/app/search/` empty |
| V2Da | 2D CSTR drawings: plan/front/side/section, IS SP 46 | 3 | 19 Oct | merged (done) | #13 + #35 + #63 (half section A-A added, review fixes), `web/tests/check-v2da.mjs` | hand-drawn check not recorded | none |
| OA | OA prep lite: aptitude MCQs + 3 Python problems, hidden tests | 4 | 21 Oct | not started | - | everything | MCQ half needs Q1 (merged: OK). Hidden tests must run in the browser sandbox (rule 1) |
| IB | Interview bank lite, filtered by company | 3 | 21 Oct | not started | - | everything | rule 13: the real bank must never go into an assistant -> code + synthetic sample only |
| PY | PYQ predictor lite: 3 papers -> frequency table + likely paper | 3 | 22 Oct | not started | - | everything | C1 uploads (P2) not on main; A3 merged |
| TE | Time-to-finish lite: range for a 30-page PDF | 3 | 22 Oct | not started | - | everything | C1 uploads (P2) |
| V2Db | 2D column + exchanger drawings (4 equipment types) | 5 | 22 Oct | merged: column #64, exchanger #65 | `web/src/chemlab/drawings/{sheet,column,hx}.ts`, McCabe + new Heat exchanger tab, `web/tests/{chemlab,hx}-drawing.spec.ts` | "4 equipment types": CSTR + column + exchanger exist; 4th type not named anywhere -> asked Supreeth | none |
| F1 | Real users: 3-5 classmates on a real deadline | 6 | 22 Oct | not started | - | human activity; I can prepare the plan + log template | needs a deployed working build |
| F7 | Film 26 Oct (frozen build) + edit 27 Oct | 8 | 27 Oct | not started | - | human activity; I can prepare shot list/checklist | frozen build, F6 script (P4) |
| PFD | SHOULD: process flow diagrams (12 units) | 4 | after MUST | not started | - | only after every P5 MUST is merged | - |

Checks run on main (12 Oct): web `oxlint` 0 errors (2 warnings, not P5), `tsc -b` exit 0, `check-v2da.mjs` passed.

### Progress
- Hours built: V2Da ~2.5 of 3 h (section view missing) = **2.5 / 45 h = 5.6 %**.
- Merge-based (merged ticket hours / MUST hours): V2Da merged = **3 / 45 h = 6.7 %**, but its done-when is not met.
- Buildable now without other roles: V2Da section, V2Db, OA, IB (synthetic), D1/D1b front ends on mocks, F1/F7 prep = ~22 h.
- Blocked on P2: D1/D1b back ends (A4), D5 (NR), PY + TE (C1).

## Decisions
- 12 Oct: tracker branch `p5-tracker` created from main 8769e79.

- 12 Oct: verified Supreeth's plan "build our part first, P2 builds theirs, merge at the end" against the repo:
  works for D1, D1b, D5 behind store/search interfaces with in-memory/fake versions (same pattern as P1's solve loop,
  `api/app/agent/state.py`). Final done-when checks wait for A4 (DB), NR (notes search), D6 (scheduler), a model.
  Recommendation: merge each ticket as soon as it is verified, not at the end: main.py, Shell.tsx, vercel.json change
  several times a week (Samarth is landing P2 tickets AU1/A6 fast), so long-open branches would drift.
- 12 Oct: pywebpush 2.5.0/2.4.0 need cryptography>=47 but api pins cryptography==46.0.3 -> use pywebpush 2.3.0
  (no pin change). Transitive aiohappyeyeballs is PSF-2.0 (not on the MIT/Apache/MPL list): flag in the D1b PR.
- 12 Oct: browser e2e here: `npm run build` needs cdn.jsdelivr.net (blocked); offline config (vite build, no Pyodide,
  executablePath /opt/pw-browsers/chromium) runs dashboard.spec 6/6 on main. Baseline api 418 passed/1 skipped, chemlab 165.

- 12 Oct (re-check, main = 5dc4085): P2 work on main = A2 (#14), AU1 (#36), A6 (#37, #39). Still missing: A4 DB, C1
  uploads, NR notes search, D6 scheduler, /dashboard endpoint, mounted LLM wiring. Can-do-now: D1 ~80 % (all but DB
  persistence), D1b ~80 % (all but DB + D6 calling it; a live phone test is possible once VAPID keys are in Render/Vercel),
  D5 ~60 % (needs NR for links + LLM wiring/model for real questions).
- 12 Oct: **PR #40 "feat: add OA prep practice page" (shreyasgoudar251ch056, open, 18:14 UTC)** = P5 ticket OA. Shreyas also
  built V2Da (#13). Shreyas looks like the active previous P5 owner: confirm before building any P5 ticket (risk of duplicates).

## Open questions (for Supreeth / the team)
1. Is Shreyas (`shreyasgoudar251ch056`, PR #40 OA, #13 V2Da) the previous/current P5? (`sudhanvaad1106-spec` has no activity.) Is Shreyas also doing D1/D1b/D5? Any local, unpushed work?
2. IB vs rule 13: OK to build the filter/practice code with a synthetic sample bank, real bank loaded by a human?
3. D1/D1b add new endpoints (notices, push subscriptions): needs a contract note (rule 3)?
4. D1/D1b/D5/PY/TE back ends need P2's A4/NR/C1: build now against an interface + fakes, wire when P2 lands?

## Log
- 12 Oct: audit done (this file). Nothing built yet; waiting for Supreeth's go-ahead before code.
- 12 Oct: started D1/D1b/D5 helpers, then stopped them at Supreeth's request ("verify first"). Nothing was
  committed or pushed; no worktrees left. Verification of the plan recorded under Decisions. Waiting for go-ahead.
- 13 Oct: V2Da section merged (#63). V2Db column (#64) and exchanger (#65) merged after 3 review rounds each; main = tested tree. Next: D1 (notices); D10 #62 (Samarth) still open, its export/delete must include notices.
- 13 Oct: D1 backend merged (#68, POST/GET/DELETE /api/v1/notices, 2 review rounds, real-Postgres tests incl. concurrent cap). Page renamed "Notices" (D6/D7 use "inbox" for reminders). Told Supreeth: D6 migration must become 0005.
