#!/usr/bin/env python3
"""Prepare logs and director state for a performance tryout run."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
DEFAULT_API = "http://localhost:8000/api/v1"


def _archive(path: Path) -> Path | None:
    if not path.is_file() or path.stat().st_size == 0:
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    archived = path.with_name(f"{path.stem}_{stamp}{path.suffix}")
    shutil.move(path, archived)
    return archived


def _trace_paths() -> list[Path]:
    return [
        LOGS / "signal_trace.jsonl",
        ROOT / "backend" / "logs" / "signal_trace.jsonl",
    ]


def _reset_traces(*, archive: bool) -> tuple[Path, Path | None]:
    primary = LOGS / "signal_trace.jsonl"
    LOGS.mkdir(parents=True, exist_ok=True)
    (ROOT / "backend" / "logs").mkdir(parents=True, exist_ok=True)
    archived: Path | None = None
    for path in _trace_paths():
        if archive:
            archived = _archive(path) or archived
        path.write_text("", encoding="utf-8")
    return primary, archived


def _api_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare tryout run (logs + director safety)")
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--no-archive", action="store_true", help="Truncate trace instead of archiving")
    args = parser.parse_args()

    trace_path, archived = _reset_traces(archive=not args.no_archive)

    print("Tryout-Vorbereitung")
    print(f"  Trace-Datei: {trace_path}")
    print(f"  Backend-CWD: backend/logs/signal_trace.jsonl (bis Neustart mit SIGNAL_TRACE_PATH)")
    if archived:
        print(f"  Archiv:      {archived.name}")

    try:
        health = _api_json("GET", f"{args.api}/health")
        print(f"  Backend:     OK ({health.get('status', 'ok')})")
    except (URLError, TimeoutError, OSError) as exc:
        print(f"  Backend:     NICHT ERREICHBAR ({exc})", file=sys.stderr)
        print("  → make run starten und erneut ausführen", file=sys.stderr)
        return 1

    try:
        _api_json("POST", f"{args.api}/director/emergency-clear")
        status = _api_json(
            "PATCH",
            f"{args.api}/director/safety",
            {
                "autopilot_enabled": True,
                "visuals_enabled": True,
                "sound_enabled": True,
                "lights_enabled": False,
                "performance_tryout": True,
            },
        )
        safety = status.get("safety", {})
        print(
            "  Director:    tryout aktiv "
            f"(performance_tryout={safety.get('performance_tryout')}, "
            f"lights_enabled={safety.get('lights_enabled')})"
        )
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"  Director:    Fehler ({exc})", file=sys.stderr)
        return 1

    print()
    print("Nächste Schritte:")
    print("  1. http://localhost:3003/auffuehrung öffnen")
    print("  2. „Probebetrieb (OSC-Log, kein Licht)“ aktivieren")
    print("  3. Teil 1 oder Teil 2 starten")
    print("  4. Nach dem Lauf: make analyze-signal-trace")
    print("  5. Frontend-Trace: window.__TM_SIGNAL_TRACE__.exportJsonl() in der Browser-Konsole")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
