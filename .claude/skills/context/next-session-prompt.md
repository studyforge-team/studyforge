Paste everything below the line into a new Claude Code session on studyforge-team/studyforge.

---

I'm Supreeth (GitHub ssupreethsg), P1 "Engine & ChemLab" on StudyForge (Nebius x NVIDIA hackathon,
submission 28 Oct 2026 21:00 IST). You continue the work of my previous Claude Code session.

1. Load the full context first. Run:
   git fetch origin && git checkout p1-tracker
   then read, in full: .claude/skills/context/SKILL.md, p1/TRACKER.md, AGENTS.md.
   Read .claude/skills/context/plan-v3.md sections when you need a ticket's design.
   Those files are the memory: project, team, rules, my standing rules, workflow, every branch/PR,
   progress numbers and the next job. Follow them exactly.
2. Verify before building: list open PRs (GitHub MCP tools, no gh CLI), check for new reviews,
   comments or merges since 10 Oct, confirm every P1 branch matches GitHub, and run
   `python p1/progress.py`. Tell me in a few lines what changed, and the progress
   (hours built of the ~61 non-Nebius hours, and the merge-based %).
3. Then start the NEXT JOB in SKILL.md section 9: the stand-in model pass (do the
   model-dependent work now with a free OpenAI-compatible model instead of Nebius; switch to
   Nebius at the end). Step 1 tells you which domain and env var I must add in the environment
   settings; if one is missing, tell me exactly what to add and carry on with the steps that
   don't need it. Never ask me to paste a key in chat.
4. My rules, short: don't change the timeline; build exactly what the plan says; Opus
   orchestrates and does the hard parts, Sonnet subagents do well-specified coding; verify
   everything (ruff, mypy, pytest, independent number checks); push every finished piece and
   update p1/TRACKER.md so nothing is lost; never merge a PR without a teammate's review unless
   I say so; other people's tickets only with the team's OK; stand-in results are rehearsal only,
   never presented as Nemotron results.
