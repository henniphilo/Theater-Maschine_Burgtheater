#!/usr/bin/env bash
# Stoppt Theatermaschine (stop.sh). Für Desktop-App-Launcher.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "=== Theatermaschine stoppen ==="
./stop.sh
echo ""
echo "Fertig. Fenster kann geschlossen werden."
sleep 2
