# Feedback log

Notes on Nebius / NVIDIA tools for the Devpost "feedback" field. Each entry is something we
saw while building and testing StudyForge (19–27 Oct 2026), with what we did about it.

## Nebius Token Factory

- **OpenAI-compatible API made model roles cheap to build.** One `openai` client with the
  Token Factory base URL serves four roles; switching a role from Super to Ultra, or adding a
  fallback model, is a one-line change in `config/models.yaml`.
- **`GET /v1/models` and the price page were enough to wire IDs and prices** (ticket G10).
  Logging tokens × price per call gave us cost per question (about $0.01–0.013).
- **An account with no credit is not refused; the card on file is charged.** We could not
  rely on an error to stop spending, so we count spend ourselves and switch to a teammate's
  key at a set amount (PR #160). A "refuse when credit is used up" option per key would help
  hackathon teams.
- **With reasoning on, a reply sometimes came back with empty content** (the whole answer in
  the reasoning channel). We now retry once with thinking off (PR #155). Clearer docs on when
  this happens would help.
- **Reasoning replies need a token budget.** Long reasoning replies needed `max_tokens` set per role
  (16000 for solving; 12000 for long page reads, 4000 cut them off). Recommended values per
  model in the docs would save trial and error.
- **Credits:** live testing of a full question (router, solve, independent re-solve, write-up)
  costs about a cent, so a few hundred test questions fit easily in the hackathon credits.

## NVIDIA Nemotron models

- **Nemotron 3 Nano** is fast and cheap enough to classify every question (median about
  0.6 s, $0.00003 a call).
- **Nemotron 3 Ultra** made the biggest accuracy difference: as solver and as an
  independent re-solver it removed the confident wrong answers we saw with Super alone
  (held-out set 46/48 vs 44/48; 0 wrong answers labelled high).
- **Nemotron 3.5 Super-VL** reads printed question images well once images keep their full
  resolution and thinking is on (12/12 images with every number read correctly vs 9/12).
- **Recall of textbook formulas is the weak spot:** real-gas, Wilson and Peng-Robinson
  formulas were sometimes recalled wrong. Giving the model tested tools to call fixed this,
  which is why StudyForge never lets the model state a number it did not compute.

<!-- Each teammate: add one point from your own use above this line. -->
