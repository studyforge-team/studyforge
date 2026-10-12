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
| D1 | In-app intake: Web Share Target + paste box -> notice | 2 | 14 Oct | not started | no manifest, no share_target, no notices table/route on main | everything | DB (A4, P2) not on main; front end can go on mocks |
| D1b | Web push: SW, "Turn on reminders", VAPID in env, pywebpush sender for D6 | 3 | 16 Oct | not started | no service worker / push code; `Reminder.channel: 'push'` type + mock only (P3, E1) | everything | A4 for subscriptions table; D6 (P2) calls the sender |
| D5 | Prep pack, built when opened (5 questions each linked) | 5 | 18 Oct | not started | Q1 quiz engine merged (`api/app/agent/quiz*.py`); "Open prep pack" only a mock label | everything | NR notes search (P2) not on main; `api/app/search/` empty |
| V2Da | 2D CSTR drawings: plan/front/side/section, IS SP 46 | 3 | 19 Oct | merged, done-when NOT met | #13 + #35, `web/src/chemlab/drawings/cstr.ts`, `web/tests/check-v2da.mjs` passes (re-run 12 Oct) | **section view missing** (sheet has front, LH side, plan); hand-drawn check not recorded | none |
| OA | OA prep lite: aptitude MCQs + 3 Python problems, hidden tests | 4 | 21 Oct | not started | - | everything | MCQ half needs Q1 (merged: OK). Hidden tests must run in the browser sandbox (rule 1) |
| IB | Interview bank lite, filtered by company | 3 | 21 Oct | not started | - | everything | rule 13: the real bank must never go into an assistant -> code + synthetic sample only |
| PY | PYQ predictor lite: 3 papers -> frequency table + likely paper | 3 | 22 Oct | not started | - | everything | C1 uploads (P2) not on main; A3 merged |
| TE | Time-to-finish lite: range for a 30-page PDF | 3 | 22 Oct | not started | - | everything | C1 uploads (P2) |
| V2Db | 2D column + exchanger drawings (4 equipment types) | 5 | 22 Oct | not started | `drawings/McCabe.tsx` is the McCabe chart, not a drawing | everything | none |
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

## Open questions (for Supreeth / the team)
1. Is `sudhanvaad1106-spec` the previous P5? Any local, unpushed work?
2. IB vs rule 13: OK to build the filter/practice code with a synthetic sample bank, real bank loaded by a human?
3. D1/D1b add new endpoints (notices, push subscriptions): needs a contract note (rule 3)?
4. D1/D1b/D5/PY/TE back ends need P2's A4/NR/C1: build now against an interface + fakes, wire when P2 lands?

## Log
- 12 Oct: audit done (this file). Nothing built yet; waiting for Supreeth's go-ahead before code.
