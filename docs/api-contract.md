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

## 3. Team note (to post with the PR)

> P1 contract requests, all optional, nothing breaks: (1) `GET /solve/{id}` to resume;
> (2) an optional `step_seq` echoed in the result body so retries are safe;
> (3) confirm = re-post `/solve` with `confirmed: true`; (4) optional `progress` label;
> (5-6) optional `final.flags` and `final.chemlab`; (7) `figure_description` on the
> upload read; (8) a quiz item report endpoint; (9) the canonical result shape;
> (10) CSP and bearer token for the deployed build. Details and status in
> `docs/api-contract.md`. Please reply with objections by the next check-in.
