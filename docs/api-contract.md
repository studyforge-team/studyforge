# Solve API contract

One written copy of the solve contract (master plan §3.5), taken from what the web
client already types in `web/src/api/types.ts`, plus P1's change requests.
AGENTS.md rule 3: changing the contract needs a PR that touches this file plus a
team note. Every request below is **optional and additive**: the current web client
and its mock keep working unchanged.

## 1. Current contract (as typed in `web/src/api/types.ts`)

| Endpoint | Body | Reply |
|---|---|---|
| `POST /api/v1/solve` | `{question}` | `{solve_id, step}` |
| `POST /api/v1/solve/{id}/result` | `ResultBody` | `{step}` |

```ts
type Step =
  | { type: 'run_python'; code: string; timeout_s: 10 }
  | { type: 'need_confirm'; extracted_text: string }
  | { type: 'final'; answer_md: string; numbers: Record<string, number>;
      figures: string[]; diagram_mermaid?: string;
      sources: { title: string; url?: string }[];
      confidence: 'high' | 'medium' | 'low' }
type ResultBody = { stdout: string; result: unknown; figures: string[];
                    error: string | null; ms: number }
```

The four fields P3 marked "gap" (`numbers`, `figures`, `sources`, `confidence`) are
adopted as typed. Conventions the backend follows (branch `s2-agent-loop`):
- `numbers` keys carry the unit: `"answer (m^3)"`, `"X"` for dimensionless values.
- `figures` are `data:image/png;base64,...` URLs until the page CSP allows the
  Storage origin, then Storage URLs.
- Failures (model unavailable, out of budget, refused tool) arrive as a `final` step
  with `confidence: 'low'`, never as an HTTP error, because the client does not read
  error bodies. HTTP errors are only 401 (not signed in), 404 (unknown or another
  user's solve), 413 (result body over 3 MB) and 422 (malformed body).

## 2. P1 change requests (8 Oct)

| # | Request | Why | Backend status |
|---|---|---|---|
| 1 | `GET /api/v1/solve/{id}` → `{step}` | Resume the pending step after a reload or restart | Built (`s2-agent-loop`) |
| 2 | Optional `step_seq: number` on every step, echoed in `ResultBody` | Without it a network retry and a re-run of the same failing code post identical bodies, so the server cannot de-duplicate safely; today it does not try | Not built; needs P3 to echo it |
| 3 | Confirm round-trip: after the student edits the text read from a photo, the client re-posts `POST /solve {question: <edited>, upload_id, confirmed: true}` | §3.5 has no return path from `need_confirm` | Built |
| 4 | Optional `progress?: string` on each step | "Progress streamed" without an SSE endpoint: the client shows the label per step | Not built |
| 5 | `final`: optional `flags?: string[]` | Shows why an answer is low confidence (e.g. `unsupported_numbers`, `limit_reached`, `cross_check_disagreed`) | Tracked internally; not on the wire yet |
| 6 | `final`: optional `chemlab?: {template, inputs}` | "Open in ChemLab" keeps the inputs | Data available from template runs; not on the wire yet |
| 7 | `POST /uploads/{id}/read` reply: add `figure_description` | The vision read returns it; the confirm screen can show it | Built in `read_question` (C2) |
| 8 | Quiz: `POST /api/v1/quizzes/{id}/report {item_index, reason}` | The browser drops a numerical item whose key script fails or whose two methods disagree, and reports it | Not built (quiz storage needs A4) |
| 9 | Canonical sandbox result `{answer: {value, unit}, check: {value, unit, method}, values: {name: {value, unit}}, assumptions: [str]}` | Shared by the solver prompt, verify, B8 and P4's eval (T4) | Built |
| 10 | Page CSP: add the API and Supabase origins to `connect-src` and `img-src` (§3.6); send the bearer token on API calls | Today a deployed build cannot reach the API or show Storage images | Frontend (P3) |
| 11 | D8: `POST /api/v1/quizzes/{id}/answers {answers, score, correct}`: `correct` has one entry per stored item; an entry may be `null` for an item the student skipped (never saw), and it is not recorded | The browser skips numerical items whose key fails the double-check | Built |

## 3. Team note (to post with the PR)

> P1 contract requests, all optional, nothing breaks: (1) `GET /solve/{id}` to resume;
> (2) an optional `step_seq` echoed in the result body so retries are safe;
> (3) confirm = re-post `/solve` with `confirmed: true`; (4) optional `progress` label;
> (5-6) optional `final.flags` and `final.chemlab`; (7) `figure_description` on the
> upload read; (8) a quiz item report endpoint; (9) the canonical result shape;
> (10) CSP and bearer token for the deployed build. Details and status in
> `docs/api-contract.md`. Please reply with objections by the next check-in.

## 4. Notices (D1, 13 Oct): additive, new endpoints only

A notice is text a student pastes into StudyForge or shares to it from another app (a class
WhatsApp message, an email about a deadline). It is stored as given; nothing reads it yet.
Turning notices into tasks and reminders is a later ticket and needs a model.

| Endpoint | Body | Reply |
|---|---|---|
| `POST /api/v1/notices` | `{text, source?, title?, url?}` | `201 Created` (not 200) + `Notice` |
| `GET /api/v1/notices` | (none) | `{notices: Notice[]}`, newest first, at most 50 |
| `DELETE /api/v1/notices/{id}` | (none) | `204`; `404` if missing or not yours |

```ts
type NoticeIn = { text: string            // up to 5000 characters as sent (trim before posting);
                                          // must be non-empty after trimming; NUL removed
                  source?: 'paste' | 'share' // default 'paste'; 'share' = arrived via the Share menu
                  title?: string           // up to 200; what the sharing app sent as a title
                  url?: string }           // up to 2000; http(s) with a host, no spaces (shown as a link)
type Notice = { id: string; text: string; source: 'paste' | 'share';
                title: string | null; url: string | null; created_at: string } // ISO 8601, UTC
```

- Signed in only (Bearer token, like `/solve`); each user sees and deletes only their own notices.
- Errors (`{detail: string}`): 401 not signed in; 413 body over 64 KB; 422 bad body, e.g.
  `"invalid notice: text"` (the pasted text is never echoed back); 429 at 500 notices per user
  (`"notice limit reached (500)"`); 503 when the server has no database.
- Table `app.notices` (migration 0004), RLS on with no policies, like every other table.
  D10's export (`GET /me/export`) and delete (`DELETE /me`) must include it.

Team note: "D1 adds `POST/GET /api/v1/notices` and `DELETE /api/v1/notices/{id}` (additive,
nothing existing changes). A notice is pasted or shared text; it is only stored for now. Shape in
`docs/api-contract.md` section 4. D10 export/delete will include the new table."

## 5. Phone reminders (D1b, 16 Oct): additive, new endpoints only

The browser subscribes to web push; every reminder and check-in the keep-alive ping sends
(D6/D7) also goes to the student's subscribed devices. Off until the host has the VAPID keys.

| Endpoint | Body | Reply |
|---|---|---|
| `GET /api/v1/push/key` | (none) | `{public_key}` (base64url); `503` until the keys are set |
| `POST /api/v1/push/subscriptions` | `PushSubscription.toJSON()`: `{endpoint, keys: {p256dh, auth}}` | `201 {ok: true}` |
| `DELETE /api/v1/push/subscriptions?endpoint=…` | (none) | `204`; `404` if not this user's device |
| `POST /api/v1/push/test` | (none) | `{sent: n}`, a test notification to this user's devices |

- Signed in only. `endpoint` must be https on a browser push service (Google FCM, Mozilla,
  Apple, Microsoft); the server never posts anywhere else. Re-subscribing the same device moves
  it to the signed-in user. At most 10 devices per user (`429`); the test is limited to 3 per
  10 minutes (`429`).
- The notification payload (encrypted, RFC 8291) is `{title, body, url}`; `url` is a path on this
  site (`/#prep/<task>`, or `…?checkin=<id>` for a check-in), and the service worker opens only
  StudyForge pages.
- Table `app.push_subscriptions` (migration 0008), RLS on with no policies; covered by
  `GET /me/export` and `DELETE /me`.
- Host env (never in the repo): `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (from
  `npx web-push generate-vapid-keys`) and `VAPID_SUBJECT` (`mailto:…`). `/keepalive` reports
  `"pushed": n` (`null` while off).

Team note: "D1b adds `/api/v1/push/*` (additive). Phone reminders switch on once the three VAPID
variables are set on Render. Shape in `docs/api-contract.md` section 5."

## 6. Prep pack (D5, 16 Oct): additive, new endpoint only

`GET /api/v1/prep/{key}`, where `key` is the 16-hex task key in the reminder and check-in links
(`/#prep/<key>`), answers `{task: {title, deadline_utc}, quiz_id, quiz: Quiz, links}`:
- `quiz` has the Q1 `Quiz` shape (5 items, numerical keys checked in the browser sandbox as for any quiz).
- `links[i]` is `{upload_id, page}` (the student's notes page matching question i; open it with
  `GET /api/v1/uploads/{upload_id}`) or `null`. The same link is in `quiz.items[i].source` as
  `"notes:<upload_id>#page=<n>"`.
- Built from the student's notes the first time it is opened, then stored as quiz `prep-<key>`
  (covered by export/delete like every quiz); later opens never call the model.
- Always 5 questions; a build that yields fewer stores nothing (502). A question links to a notes
  page only when they share at least two real words; with no notes, every link is `null`.
- Model use counts against the student's own daily caps (same as `/solve`); one build at a time
  per pack, and after a failed build no new model call for a minute.
- Errors: 404 not one of this student's tasks; 401 not signed in; 503 no database, or the pack is
  not built yet and the model is unavailable (or a build failed under a minute ago); 502 the model
  failed (nothing stored, try again); 429 the model budget is used up.

Team note: "D5 adds `GET /api/v1/prep/{key}` (additive). Reminder and check-in links open it;
it needs the model only the first time. Shape in `docs/api-contract.md` section 6."

## 7. PDF reading (TE and PY, 16 Oct): additive, one new endpoint

```
POST /api/v1/pdf/read   multipart: file (PDF, 10 MB max)
  -> 200 { pages: number,    // the true page count
           words: number,    // words in the text layer of the first 200 pages (0 for a scan)
           text: string[] }  // one entry per page, first 200 pages, line breaks kept, ≤ 5000 chars each
```

- Signed in only. Nothing is stored: the file is read in memory and dropped.
- Errors (`{detail: string}`): 401 not signed in; 411 no Content-Length; 413 over 10 MB;
  415 not a PDF, or a PDF that can't be read (broken or password-locked).

Team note: "TE and PY add `POST /api/v1/pdf/read` (additive, nothing existing changes). It returns
a PDF's page count, word count and text, and stores nothing. TE uses the page count; PY uses the
text of past papers. Shape in `docs/api-contract.md` section 7."

## 8. Make a quiz (T1 and T2): additive, one new endpoint, one new item type

```
POST /api/v1/quizzes   (signed in)
  { topic: string,            // 1 to 80 characters, required
    n_items?: 3..20,          // default 5; the generator writes at most 10
    kinds?: "mcq" | "blank" | "mixed",   // default "mcq"
    marks_per_q?: 1 | 2 | 4,  // default 1
    upload_id?: string }      // one of the student's own uploads (question-... or notes-...)
  -> 200 { id, title, items, topic, marks_per_q,
           total_marks,        // items.length * marks_per_q
           suggested_minutes } // items.length * (2 for "mcq", else 3)
```

- Unknown request fields are refused (422). `items` has the same shape as a prep-pack quiz.
- With `upload_id`: a PDF's text layer (first 10 pages, 12,000 characters) is sent to the model as
  quoted notes. A scan, handwriting or a photo (under 200 characters of text) is read with the
  vision model on up to 3 pages instead. Nothing readable gives 422.
- The quiz is stored like a prep pack's (`app.quizzes`, covered by export/delete) with `topic` and
  `marks_per_q` added, so `POST /quizzes/{id}/answers` accepts it unchanged.
- Model use counts against the student's own daily caps (same as `/solve`).
- Errors: 401 not signed in; 404 no such upload (also another student's); 422 bad request or an
  upload with no readable text; 429 the model budget is used up; 502 the model failed or wrote too
  few usable questions (nothing stored, try again); 503 no database, no model, or an upload given
  while storage is off (`{"detail": "quiz not available"}` when there is no model).

New item type (T2), added to the quiz item union (existing types are unchanged):

```
{ type: "blank", topic, stem,   // stem contains the gap "____"
  answers: string[],            // 1 to 5 accepted words or short phrases, 1 to 60 characters each
  explanation: string, source?, tags? }
```

- The blank is a word or short phrase. A numerical answer is a `numerical` item, so it stays
  sandbox-checked. Clients grade a blank by comparing lowercase, trimmed, space-collapsed text.

Team note: "T1 adds `POST /api/v1/quizzes` (additive; the web client already calls it) and T2 adds the
`blank` quiz item type. Shape in `docs/api-contract.md` section 8."

## 9. Quiz progress (T4): additive, one new endpoint

```
GET /api/v1/quiz-attempts
  -> 200 { topics: [ { topic: string,
                       attempts: [ { quiz_id: string, score: number, total: number,
                                     marks_per_q: number, created_at: string } ] } ] }
```

- Signed in only; only the caller's own attempts. Attempts are oldest first, at most 50 per topic
  (the newest 50). Topics are sorted by their latest attempt, newest first.
- `score` is marks scored, `total` is the number of answered (non-skipped) questions, `marks_per_q`
  is marks per question (1 unless the quiz sets it).
- `POST /api/v1/quizzes/{quiz_id}/answers` now also stores one attempt per save (topic = the
  quiz's topic, else its title). Its request and response are unchanged (`{recorded: n}`).
- Errors (`{detail: string}`): 401 not signed in; 503 no database.
- Covered by `GET /me/export` and `DELETE /me` like every per-user table.

Team note: "T4 adds `GET /api/v1/quiz-attempts` (additive) and a new table `app.quiz_attempts`
(migration 0009). `save_answers` also stores an attempt; its response is unchanged. Shape in
`docs/api-contract.md` section 9."

## 10. History of solved questions (T5): additive, one new endpoint

```
GET /api/v1/solves?before=<ISO datetime, optional>&q=<text, optional, max 80>
  -> 200 { items: [{ id, question, status, updated_at }],   // newest first, at most 20
           next: string | null }                            // updated_at of the last item, or null
```

- Signed in only; the student's own solves only. Ordered by `updated_at` descending.
- `question` is the first 200 characters. `status` is the solve's status (empty string if unknown).
  The list never returns `state`, figures or answers; open one with the existing `GET /solve/{id}`.
- `before`: only solves updated before this time (pass the previous page's `next`). A time without
  a zone is read as UTC.
- `q`: case-insensitive substring match on the question; `%` and `_` match themselves.
- Errors (`{detail: string}`): 401 not signed in; 422 `q` over 80 characters or `before` not a time;
  503 no database.

Team note: "T5 adds `GET /api/v1/solves` (additive, nothing existing changes). It lists the
student's past questions for the History page; tapping one uses the existing `GET /solve/{id}`.
Shape in `docs/api-contract.md` section 10."

## 11. Practice attempts (FO1)

```
POST /api/v1/practice-attempts
  { topic: string (1..80), score: number (>= 0), total: integer (1..50), marks_per_q?: 1 | 2 | 4 (default 1) }
  -> 200 { ok: true }
```

- Saves a self-marked practice result (company OA, interview practice) into `app.quiz_attempts`,
  with `quiz_id = "practice:" + topic`. It then shows in `GET /api/v1/quiz-attempts` like a quiz.
- `score` above `total` is stored as `total`. Signed in only; each student sees only their own.
- Errors (`{detail: string}`): 401 not signed in; 422 bad input (e.g. `total` 0, extra fields);
  503 no database.

Team note: "FO1 adds `POST /api/v1/practice-attempts` (additive, no migration; it writes the
existing `app.quiz_attempts`). Shape in `docs/api-contract.md` section 11."
