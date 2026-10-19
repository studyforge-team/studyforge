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
