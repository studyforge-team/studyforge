# Stand-in now, Nebius at the end: how the swap works

The P1 plan does not change. Its model steps (G10 and every ticket's live done-when check)
run twice: first against a free stand-in provider (rehearsal), then against Nebius Token
Factory (the run that counts). Only the model **provider** changes; code, prompts, tests
and dates stay as planned.

## Why the swap is safe

The app reads the provider from one YAML registry: `base_url`, `api_key_env`, model ids and
role settings. `config/models.yaml` on `main` is Nebius. Setting the environment variable
`STUDYFORGE_MODELS_PATH` to another registry swaps the provider; unsetting it swaps back.
No code changes either way.

| Loophole | What closes it |
|---|---|
| Demo or results accidentally run on the stand-in | `check.py` prints which provider is active and stamps every result file `"stand_in": true/false`. Only Token Factory results go in README/Devpost |
| Stand-in model ids leak onto `main` | Stand-in registries live only in `p1/standin/` on `p1-tracker` (never merged). `main` keeps the single registry (plan rule 6) |
| Key missing or wrong env var name | `check.py` fails on it before any call, and never prints the key |
| A role (e.g. vision) has no model id | `check.py` fails `role vision`. Today's Nebius config fails this on purpose: G10 must fill it |
| Provider rejects the Nemotron thinking flag | `check.py --live` shows 400 on every text role (tested with `mock_server.py --strict`). Fix below |
| Nemotron formats tool calls or thinking text differently | The client accepts native tool calls and fenced code, and strips thinking text in 4 forms. G10 probe + `check.py --live` exercise both on Nebius before anything else |
| Prompts tuned on the stand-in work worse on Nemotron | Prefer the NVIDIA stand-in (serves Nemotron). Re-run every live check on Nebius and retune there; those numbers are the ones that count |
| Replay fixtures recorded on the stand-in end up in CI | Record fixtures only after the switch; stand-in fixtures stay out of `api/tests/` |
| Cost runs away | Every call writes a cost row; `BudgetGuard` hook caps spend (ceiling proposed: $5 for G10 + A3) |
| Results only "remembered" | Every run writes a file under `p1/standin/results/` or `p1/g10_results*.json` and is pushed |

## Rehearsal (now)

1. Pick a provider and add its key in the environment settings (never in chat):
   - NVIDIA (`NVIDIA_API_KEY`, allow `integrate.api.nvidia.com`), preferred: same Nemotron family.
   - Gemini (`GEMINI_API_KEY`), already reachable from the cloud session.
   - Ollama on the laptop (`models.ollama.yaml`, `LOCAL_LLM_KEY=x`).
   Also allow `cdn.jsdelivr.net` (Pyodide packages for the sandbox runner).
2. List models and run the G10 checks against it:
   `python p1/g10_probe.py --base-url <URL> --key-env <NAME> --super <id> --nano <id> --vision <id> --photo <synthetic.png>`
3. Put the chosen ids into `p1/standin/models.<provider>.yaml`.
4. `STUDYFORGE_MODELS_PATH=p1/standin/models.<provider>.yaml python p1/standin/check.py --live`
   must print `RESULT: ALL PASS`. Push the result file.
5. Run the tickets' live checks with the same variable set (A3 live test, C2 photos, Q1
   quizzes, CH3 picks, S2/S2b smoke once the S1b runner exists). Push every report.

## Switch to Nebius (once a card/credit exists; target about 20 Oct)

1. Environment settings: add `TF_API_KEY`, allow `api.tokenfactory.nebius.com`.
2. `unset STUDYFORGE_MODELS_PATH` (back on `config/models.yaml`).
3. `python p1/g10_probe.py --super … --nano … --vision … --photo …` → fill ids and prices in
   `config/models.yaml` (PR "G10: model ids and prices"), record in `docs/decisions.md`.
4. `python p1/standin/check.py --live` → must print the NEBIUS banner and `RESULT: ALL PASS`.
5. Re-run every live check from rehearsal step 5 on Nebius; retune prompts where scores drop;
   record replay fixtures; put the real numbers in README/Devpost (F4/F8).

## Thinking flag

Nemotron's reasoning switch is sent as `extra_body={"chat_template_kwargs": {"enable_thinking": …}}`.
Roles without `reasoning:` send no flag, but JSON calls always send `enable_thinking: false`.
Nebius needs this flag. Ollama ignores unknown fields; NVIDIA serves Nemotron and should accept
it. If a stand-in rejects it (400 on every text role in `check.py --live`), add a registry option
that turns the flag off (default on, so Nebius is unchanged) as a small A3 follow-up PR with
tests. Only build it if a real provider needs it.

## Test the checker itself (no key, no network)

```
python p1/standin/mock_server.py --port 8765 &        # add --strict to reject the flag
MOCK_KEY=x STUDYFORGE_MODELS_PATH=<registry pointing at http://127.0.0.1:8765/v1/> \
  NO_PROXY=127.0.0.1 python p1/standin/check.py --live
```
Checked 10 Oct: Nebius config without key → FAIL (key, vision id); mock without key → FAIL
before any call; mock → ALL PASS; strict mock → FAIL with 400 on every flagged role.
