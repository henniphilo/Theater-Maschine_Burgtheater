#!/usr/bin/env bash
# Backend-Tests mit Projekt-venv (nicht globales pytest / System-Python).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 fehlt. Installieren: brew install python@3.11" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Alte .venv mit Python < 3.11 — neu anlegen mit: rm -rf .venv && ./run-tests.sh" >&2
  exit 1
fi

pip install -q --upgrade pip
pip install -q -e ".[dev]"

export OSC_DRY_RUN="${OSC_DRY_RUN:-true}"
export OSC_HOST="${OSC_HOST:-127.0.0.1}"

ruff check app tests
exec pytest "$@"
