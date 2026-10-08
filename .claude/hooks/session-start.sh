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
"$VENV/bin/pip" install --quiet ruff mypy pytest

if [ -f "$ROOT/api/pyproject.toml" ]; then
  "$VENV/bin/pip" install --quiet -e "$ROOT/api[dev]"
fi

if [ -f "$ROOT/chemlab/pyproject.toml" ]; then
  "$VENV/bin/pip" install --quiet -e "$ROOT/chemlab[dev]" \
    || "$VENV/bin/pip" install --quiet -e "$ROOT/chemlab"
elif [ -f "$ROOT/chemlab/requirements.txt" ]; then
  "$VENV/bin/pip" install --quiet -r "$ROOT/chemlab/requirements.txt"
fi

# Node (npm install, not ci, so the cached container state is reused)
if [ -f "$ROOT/web/package.json" ]; then
  (cd "$ROOT/web" && npm install --no-audit --no-fund)
fi
if [ -f "$ROOT/runner/package.json" ]; then
  (cd "$ROOT/runner" && npm install --no-audit --no-fund)
fi

# Put the venv on PATH for the rest of the session
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$VENV\""
    echo "export PATH=\"$VENV/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi
