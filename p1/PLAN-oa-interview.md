# Plan: chemical-company Mock OA + interview cards (demo, 20 Oct)

**Scope:** 2 small, web-only PRs. **No server, database or AI-code change.** They reuse the merged quiz route (#103) and progress (#101/#102).
**Time:** about 4 h total, with 2 Sonnet workers in parallel and Opus review. **Extra credits:** one quiz call per Mock OA started.
**Start trigger:** Supreeth says "start OA plan".

## Data: who writes it
- Demo data for **3 companies** is written by Claude (Sonnet writes, Opus checks): generic chemical-engineering patterns and textbook questions.
- **No scraping and no copying** of real interview posts or real OA questions.
- Every company page shows: **"Illustrative demo pattern, not provided by the company."**
- **Companies (default):** ExxonMobil, Shell, Reliance Industries. If Supreeth prefers made-up names to avoid any claim about real firms, swap the names in the JSON; nothing else changes.
- Questions are **conceptual**, with no computed numbers, so no unchecked numbers appear (rule 2).
- Real seniors' data later: humans type it into the same files (rule 13). Never through an AI.

## FO1: Chemical Mock OA (about 2 h). PR "FO1: chemical company mock OA (demo)", reviewer @samarthkombli-ops
- **New `web/src/data/oa-chem.json`:** an array of 3 objects:
  ```
  { "id": "exxonmobil",
    "company": "ExxonMobil",
    "role": "Graduate Process Engineer",
    "note": "Illustrative demo pattern, not provided by the company.",
    "sections": [ {"name": "Aptitude", "questions": 15, "minutes": 20},
                  {"name": "Chemical technical", "questions": 20, "minutes": 30} ],
    "quiz": { "topic": "<=80 chars, e.g. 'Process engineering: thermodynamics, heat transfer, fluid flow'",
              "n_items": 10, "kinds": "mcq", "marks_per_q": 1 } }
  ```
- **`web/src/pages/OA.tsx`:** add a tab bar at the top: **"Coding"** (the existing page, unchanged) and **"Chemical companies"** (new).
- **Chemical tab:**
  - pick a company (3 cards), then see its pattern (sections table, total time, the note);
  - button **"Start mock OA"** renders the existing `Quiz` component with `load={(slow) => getQuiz({...company.quiz, topic: company.quiz.topic}, slow)}` and `heading={company.company + " mock OA"}`. This is the same `load` path prep packs use, so the quiz flow, marks, saving and progress all work unchanged.
  - Show "Suggested time: {sum of section minutes} min (keep time yourself)".
- Load the JSON with dynamic `import()` inside the tab, so other pages are not slowed.
- **Tests (Playwright, mocked API):**
  - the tab switch keeps the coding tab working;
  - 3 company cards; the pattern table; the note visible;
  - "Start mock OA" posts the company's quiz request;
  - 375 px, no horizontal scroll.

## FO2: Chemical interview cards (about 2 h). PR "FO2: chemical company interview cards (demo)", reviewer @samarthkombli-ops
- **New `web/src/data/interview-chem.json`:** 3 cards (same companies):
  ```
  { "id", "company", "role", "note" (same disclaimer),
    "rounds": ["Online test", "Technical interview", "HR interview"],
    "topics": ["Distillation", "Heat exchangers", "Pumps and NPSH", "Process safety (HAZOP)", ...],
    "questions": [ {"q": "...", "a": "2-4 sentence model answer, no computed numbers", "topic": "..."} ]   (6 per company),
    "tips": ["...", "..."] }
  ```
- **`web/src/pages/InterviewBank.tsx`:**
  - add a **Field** filter "Chemical / Computer science" (default Chemical). The existing CS questions are unchanged under "Computer science".
  - **Chemical** shows the 3 company cards: rounds, topics, expandable Q&A, tips, the note.
  - Button **"Practice this company"** goes to the OA page's Chemical tab with that company selected (`#oa?company=<id>`).
- **Validator:** `web/scripts/check-chem-data.mjs`, run in the existing web CI step if easy, else locally. It checks:
  - required fields; unique ids;
  - quiz topic ≤ 80; `n_items` 3–20; `kinds` one of mcq/blank/mixed;
  - no emails or phone numbers.
- **Tests (Playwright):** the filter switches; cards render; Q&A expands; the practice link opens the OA chemical tab with the company; 375 px.

## Safety
- Web only.
- No change to: api/, Quiz.tsx logic (only used through its existing `load` prop), client.ts (it reuses `getQuiz`), contract, models.yaml, wiring.py.
- Lazy JSON keeps the other pages unchanged in size and speed.
- Full gate before each PR: `npx tsc -b`, `npm run lint` (no new warnings), the Playwright specs above plus the existing OA and interview specs. One PR per ticket, then merge after Samarth approves.

## Order
FO1 and FO2 run in parallel (different files). Opus reviews the data for wrong facts or answers, then the code. Report after each PR.
