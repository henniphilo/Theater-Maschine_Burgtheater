#!/usr/bin/env python3
"""Cursor hook: block dangerous shell commands (live OSC, .env commits)."""

from __future__ import annotations

import json
import re
import sys

DENY_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"git\s+(add|commit|push).*(\.env|backend/\.env)", re.I),
        "Attempting to commit environment files with secrets.",
        "Do not commit backend/.env or .env. Use backend/.env.example for templates.",
    ),
    (
        re.compile(r"git\s+add\s+.*\.env\b", re.I),
        "Attempting to stage .env file.",
        "Remove .env from staging. Secrets must stay local.",
    ),
]

WARN_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"OSC_DRY_RUN\s*=\s*false", re.I),
        "OSC_DRY_RUN=false may send live OSC to stage hardware.",
        "Use OSC_DRY_RUN=true for tests, or fake_osc_receiver for isolated live tests.",
    ),
    (
        re.compile(r"pytest.*OSC_DRY_RUN\s*=\s*false", re.I),
        "Running pytest with live OSC enabled.",
        "Default conftest sets OSC_DRY_RUN=true. Avoid overriding unless using fake receivers.",
    ),
    (
        re.compile(r"10\.101\.90\.112", re.I),
        "Command references production lighting desk IP.",
        "Verify this is intentional and not during development/testing.",
    ),
]


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return 0

    command = str(payload.get("command") or "")

    for pattern, user_msg, agent_msg in DENY_PATTERNS:
        if pattern.search(command):
            print(
                json.dumps(
                    {
                        "permission": "deny",
                        "user_message": user_msg,
                        "agent_message": agent_msg,
                    }
                )
            )
            return 0

    for pattern, user_msg, agent_msg in WARN_PATTERNS:
        if pattern.search(command):
            print(
                json.dumps(
                    {
                        "permission": "ask",
                        "user_message": user_msg,
                        "agent_message": agent_msg,
                    }
                )
            )
            return 0

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
