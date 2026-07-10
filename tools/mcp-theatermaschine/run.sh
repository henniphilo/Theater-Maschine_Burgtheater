#!/usr/bin/env bash
# Start Theatermaschine debug MCP server (uses backend venv when available).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export THEATERMASCHINE_ROOT="$ROOT"
export PYTHONPATH="$ROOT/backend"

VENV_PY="$ROOT/backend/.venv/bin/python"
REQ="$ROOT/tools/mcp-theatermaschine/requirements.txt"

if [[ -x "$VENV_PY" ]]; then
  "$VENV_PY" -m pip install -q -r "$REQ" 2>/dev/null || true
  exec "$VENV_PY" "$ROOT/tools/mcp-theatermaschine/server.py"
fi

python3 -m pip install -q -r "$REQ" 2>/dev/null || true
exec python3 "$ROOT/tools/mcp-theatermaschine/server.py"
