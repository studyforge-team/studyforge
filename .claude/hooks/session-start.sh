#!/bin/bash
# SessionStart hook for Claude Code cloud sessions.
# Sets up a Python 3.12 venv with ruff/mypy/pytest, then installs each package's
# dependencies once its manifest exists (api after A2, chemlab after CH1a, web after A5).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
VENV="$ROOT/.venv"

# Python 3.12 (AGENTS.md pins api/ to 3.12)
if [ ! -x "$VENV/bin/python" ]; then
  python3.12 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
# Pinned (AGENTS.md rule 14); change only by team decision.
"$VENV/bin/pip" install --quiet ruff==0.16.10 mypy==2.4.0 pytest==9.1.1

if [ -f "$ROOT/api/pyproject.toml" ]; then
  "$VENV/bin/pip" install --quiet -e "$ROOT/api[dev]"
fi

if [ -f "$ROOT/chemlab/pyproject.toml" ]; then
  "$VENV/bin/pip" install --quiet -e "$ROOT/chemlab[dev]" \
    || "$VENV/bin/pip" install --quiet -e "$ROOT/chemlab"
elif [ -f "$ROOT/chemlab/requirements.txt" ]; then
  "$VENV/bin/pip" install --quiet -r "$ROOT/chemlab/requirements.txt"
fi

# Node: npm ci never rewrites package-lock.json. It reinstalls from scratch, so run it
# only when node_modules is missing or older than the lockfile (keeps restarts fast).
npm_ci() {
  local dir="$1"
  [ -f "$dir/package-lock.json" ] || return 0
  if [ ! -f "$dir/node_modules/.package-lock.json" ] \
    || [ "$dir/package-lock.json" -nt "$dir/node_modules/.package-lock.json" ]; then
    (cd "$dir" && npm ci --no-audit --no-fund)
  fi
}
npm_ci "$ROOT/web"
npm_ci "$ROOT/runner"

# Put the venv on PATH for the rest of the session
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    echo "export PATH=\"$VENV/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi
