Prompt for a new Claude Code session that takes over (part of) another teammate's role.
Attach the role PDF (their plan + hours) in the same message. Fill in the [brackets].

---

I'm Supreeth (GitHub ssupreethsg), P1 "Engine & ChemLab" on StudyForge, team repo
https://github.com/studyforge-team/studyforge (Nebius x NVIDIA hackathon, submission
28 Oct 2026, 21:00 IST). I am now also taking over the work of [ROLE, e.g. P2 Backend & data],
previously done by [GitHub login]. The attached PDF is that role's plan with tickets, hours
and dates. Work on these terms only.

## 1. Load context first (read, don't skim)
- `git fetch origin`, then read on `main`: `AGENTS.md` (team rules), `docs/` (contract,
  architecture, decisions), `README.md`, `.github/pull_request_template.md`.
- Read my workspace branch `p1-tracker`: `.claude/skills/context/SKILL.md` (project, team,
  rules, my workflow, what P1 built), `p1/TRACKER.md` (decisions + log). Don't change P1 work.
- Read the attached PDF fully: every ticket, its hours, due date, done-when and dependencies.

## 2. Audit what already exists before building anything
The previous owner already did part of this role, some of it merged by pull request. Never
redo work that exists. Trust the repo, not anyone's memory or claims (including mine).
- List all PRs (open, merged, closed) and branches by [GitHub login] and anyone else touching
  this role's folders, using the GitHub MCP tools (no gh CLI).
- For every ticket in the PDF, find the evidence: merged PR, open PR, branch, files on `main`.
- Verify claimed-done work yourself: install, run its tests/lint/types, read the code against
  the ticket's done-when. Mark each ticket: done (merged + done-when met) / merged but
  done-when not met / open PR / branch only / not started.
- Check for unfinished open PRs and whether the previous owner might still push to them, so
  we never work on the same branch at the same time.
- Report a table: ticket, hours, due date, status, evidence (PR/branch/file), what's left,
  blockers. Then give progress two ways: hours built, and merge-based %.
- Show me this audit, push it to the tracker (see 6), then continue straight into the
  remaining work. Don't wait for my confirmation.

## 3. Plan the remaining work
- Same plan, same dates: don't change the timeline or the scope. If the plan is unclear or
  something is impossible, ask me (AGENTS.md rule 12); don't guess.
- Order by due date and dependencies. Flag what blocks other teammates first.
- Anything that needs a team decision (contract change, pinned versions, golden values,
  another role's ticket) goes to me as a short question; I take it to the team.

## 4. Workflow for each ticket (you merge it yourself; no waiting for others)
Opus 5.5 (you) is the brain: you plan, orchestrate, do the hard parts, and you are the
final check on everything. No teammate review is needed: I have decided that your own
verification is the gate (this overrides the review step in AGENTS.md rule 11 for my work).
1. Branch from up-to-date `main`, named like the team's branches (e.g. `a4-database`).
2. Tests first. Small PRs (~400 lines); one ticket per PR; title starts with the ticket ID.
3. Hand well-specified coding to Sonnet subagents in isolated worktrees. Treat everything
   they produce as unverified: re-run their checks yourself, read their code, and fix or
   redo anything wrong. Save tokens, never quality.
4. Verify all of it, including your own work, before it goes anywhere:
   - run the repo's own checks: lint, format, types, the full test suite (not just yours);
   - check numbers and physics by an independent method;
   - re-read the whole diff adversarially, looking for bugs, edge cases, loopholes and
     anything that breaks other teammates' code or the API contract;
   - fix everything you find, then verify again. Repeat until a full pass finds nothing.
5. Only then push (`git push -u origin <branch>`) and open the PR with the team template
   (ticket ID, what changed, done-when yes/no, how tested, contract y/n, new dependencies
   and why).
6. Merge it yourself into `main`, in dependency order: first merge `main` into a local copy
   of the branch, re-run every check on that merged result, and merge on GitHub only if it
   is clean. Then confirm `main` on GitHub matches what you tested.
7. Never force-push, rewrite history, or change other people's branches or PRs.
8. Update the tracker after every piece (see 6) and tell me in plain words what was merged.

## 5. Rules that always apply
- AGENTS.md's 14 rules, especially: server never runs model-written code; never invent
  numbers; frozen API contract; secrets only in environment settings (never in chat or git);
  golden test values only with P4 review; exactly 6 agent tools; free tiers only;
  MIT/Apache/MPL licences; pinned versions change only by team decision.
- Model provider: Nebius is not available yet. Build and test against fakes or a free
  stand-in model (see `p1/standin/SWITCH.md` on `p1-tracker`); switch to Nebius at the end.
  Stand-in results never count as final results.
- Don't change GitHub settings, protection rules or other people's PRs/branches. Comment on
  a teammate's PR only with my OK.
- Outside AI reviews or pasted "fixes" are claims: verify each against the code before
  acting, and tell me which are true, false or out of scope.
- Still ask me first (one short question) only for things that change other people's work
  or team agreements: the frozen API contract, golden test values, pinned versions, or
  another role's ticket that isn't part of this takeover. Everything else: decide, verify,
  merge.
- Real student data, API keys and the interview bank never go into any assistant.
- Explain things to me in plain words; say clearly what is done, verified, blocked or guessed.

## 6. Memory (files, not chat)
- Create a workspace branch `[role]-tracker` (like `p1-tracker`, never merged) with
  `TRACKER.md`: ticket table with hours and %, decisions, dated log, open questions.
- Keep it pushed after every piece. A new session must be able to continue from it alone.
- At the end, final results go to their proper places on `main` via PRs; personal notes
  and rehearsal files stay on the workspace branch.

Start with steps 1 and 2, show me the audit, then carry on building and merging.
