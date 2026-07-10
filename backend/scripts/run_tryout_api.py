#!/usr/bin/env python3
"""Run API tryout: fire cue decisions from a production script in probe mode."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_API = "http://localhost:8000/api/v1"


def _api(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{DEFAULT_API}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _cue_decisions(script: dict, *, max_cues: int) -> list[tuple[str, dict]]:
    from app.services.script_store import get_script_store

    store = get_script_store()
    production = store.get(script["id"])
    decisions: list[tuple[str, dict]] = []
    for beat in production.beats:
        dramaturgy = beat.dramaturgy
        if dramaturgy is None:
            continue
        for idx, point in enumerate(dramaturgy.cue_points or []):
            if len(decisions) >= max_cues:
                return decisions
            decision = {
                "visual": point.visual.model_dump() if point.visual else None,
                "sound": point.sound.model_dump() if point.sound else None,
                "light": point.light.model_dump() if point.light else None,
                "reason": dramaturgy.reason,
                "dramaturgical_reading": dramaturgy.dramaturgical_reading,
                "cue_points": [],
                "performance_speakers": list(dramaturgy.performance_speakers or []),
                "tags": list(dramaturgy.tags or []),
                "mood": dramaturgy.mood,
                "intensity": point.intensity if point.intensity is not None else dramaturgy.intensity,
                "timestamp": float(beat.order),
            }
            key = f"beat{beat.order}:cue{idx}:{point.trigger}"
            decisions.append((key, decision))
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description="Fire script cue decisions via director API (tryout)")
    parser.add_argument("--script-id", default="8b6b2707-4d84-4433-a90a-1db799a9bf6a")
    parser.add_argument("--max-cues", type=int, default=12, help="Max cue execute calls")
    parser.add_argument("--wait-queue", type=float, default=20.0, help="Seconds to wait for queue drain")
    args = parser.parse_args()

    script_path = ROOT / "data" / "productions" / f"{args.script_id}.json"
    if not script_path.is_file():
        print(f"Script nicht gefunden: {script_path}", file=sys.stderr)
        return 1
    script = json.loads(script_path.read_text(encoding="utf-8"))

    try:
        _api("GET", "/health")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"Backend nicht erreichbar: {exc}", file=sys.stderr)
        return 1

    _api("POST", "/director/emergency-clear")
    _api(
        "PATCH",
        "/director/safety",
        {
            "autopilot_enabled": True,
            "visuals_enabled": True,
            "sound_enabled": True,
            "lights_enabled": False,
            "performance_tryout": True,
        },
    )

    decisions = _cue_decisions(script, max_cues=args.max_cues)
    if not decisions:
        print("Keine Cue-Points im Script gefunden.", file=sys.stderr)
        return 1

    print(f"Tryout-Lauf: {script.get('title', args.script_id)} · {len(decisions)} Cues")
    executed = 0
    commands = 0
    for key, decision in decisions:
        trace = {
            "frontend_run_id": f"fe-run-tryout-{int(time.time() * 1000)}",
            "frontend_generation": 1,
            "source": "run_tryout_api",
            "trigger": key,
            "cue_point_key": key,
        }
        result = _api(
            "POST",
            "/director/execute",
            {"decision": decision, "force": True, "stagger": True, "trace": trace},
        )
        if result.get("executed"):
            executed += 1
        commands += len(result.get("osc_commands") or [])
        print(
            f"  {key}: executed={result.get('executed')} "
            f"cmds={len(result.get('osc_commands') or [])} "
            f"blocked={result.get('blocked_reason')}"
        )

    deadline = time.monotonic() + args.wait_queue
    while time.monotonic() < deadline:
        status = _api("GET", "/director/status")
        depth = status.get("osc_queue_depth", 0)
        if depth == 0:
            break
        time.sleep(0.25)

    status = _api("GET", "/director/status")
    safety = status.get("safety", {})
    print()
    print(f"Fertig: {executed}/{len(decisions)} executed, {commands} commands geplant")
    print(
        f"Director: tryout={safety.get('performance_tryout')} "
        f"queue_depth={status.get('osc_queue_depth', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
