#!/usr/bin/env bash
# Installiert Start-/Stop-Apps auf dem macOS-Desktop.
#
#   ./tools/desktop/install-desktop-apps.sh
#   make desktop-install

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DESKTOP="${HOME}/Desktop"
START_SH="${ROOT}/tools/desktop/start-theatermaschine.sh"
STOP_SH="${ROOT}/tools/desktop/stop-theatermaschine.sh"
START_APP="${DESKTOP}/Theatermaschine.app"
STOP_APP="${DESKTOP}/Theatermaschine Stop.app"

chmod +x "$START_SH" "$STOP_SH" "$0"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Desktop-Apps sind nur für macOS vorgesehen." >&2
  exit 1
fi

# AppleScript: Befehl in Terminal ausführen (sichtbare Logs, Ctrl+C möglich)
compile_terminal_app() {
  local app_path=$1
  local script_path=$2
  local title=$3
  local tmp
  tmp="$(mktemp -t tm-launcher).applescript"
  cat >"$tmp" <<EOF
on run
  set shPath to "${script_path}"
  set winTitle to "${title}"
  tell application "Terminal"
    activate
    do script "clear; printf '\\\\033]0;%s\\\\007' " & quoted form of winTitle & "; exec " & quoted form of shPath
  end tell
end run
EOF
  rm -rf "$app_path"
  osacompile -o "$app_path" "$tmp"
  rm -f "$tmp"
}

compile_terminal_app "$START_APP" "$START_SH" "Theatermaschine"
compile_terminal_app "$STOP_APP" "$STOP_SH" "Theatermaschine Stop"

# Optional: System-Icons setzen (Script Editor / Stop-Symbol)
# Start ≈ Terminal, Stop ≈ Auswerfen — ohne Custom-Asset
if command -v fileicon >/dev/null 2>&1; then
  :
fi

echo "Installiert:"
echo "  $START_APP"
echo "  $STOP_APP"
echo ""
echo "Doppelklick auf „Theatermaschine“ startet make run und öffnet http://localhost:3003"
echo "Doppelklick auf „Theatermaschine Stop“ beendet den Stack."
