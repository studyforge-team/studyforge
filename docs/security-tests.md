# X1 security checklist

| # | Item | Test | Status |
|---|------|------|--------|
| 1 | anon-key REST read returns nothing | `api/tests/integration/test_db.py::test_x1_anon_and_authenticated_cannot_read` (roles `anon`/`authenticated` get permission denied on all 4 tables; nothing in `public`) | CI (needs DATABASE_URL) |
| 2 | cross-user read | `api/tests/unit/agent/test_solve_routes.py::test_unknown_or_foreign_solve_is_404`, `test_loop.py::test_other_users_solve_is_not_found` | CI |
| 3 | injected PDF | `api/tests/unit/test_security.py::test_x1_injected_pdf` (unknown tool refused, code only returned to browser sandbox); `test_loop.py::test_unknown_tool_is_refused_and_counted` | CI |
| 4 | sandbox escape set | `web/tests/sandbox.spec.ts` (fetch, nested Worker, run_js fetch, infinite loop, socket) | CI (Playwright) |
| 5 | oversized upload | `test_solve_routes.py::test_body_limits` (413 on result body > 3 MB); `test_read_question.py::test_oversized_input`, `test_decompression_bomb`. No upload HTTP route exists in `api/` yet | CI (route gap: none to test) |
| 6 | anonymous sign-up flood | Supabase Auth rate limits + Turnstile (A7, not built). No code to test | gap: not testable in CI yet; Turnstile lands with A7 |
| 7 | spoofed X-Forwarded-For | `test_spend.py::test_client_ip` (rightmost wins, prepended entries ignored), `test_spend_context_sets_who` (through the router) | CI |
