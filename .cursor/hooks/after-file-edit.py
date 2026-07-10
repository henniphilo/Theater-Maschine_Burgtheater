#!/usr/bin/env python3
"""Cursor hook: scoped lint after file edits + text-split sync reminder."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SPLIT_PAIR = {
    "backend/app/services/text_split.py": "frontend/lib/text/splitSentences.ts",
    "frontend/lib/text/splitSentences.ts": "backend/app/services/text_split.py",
}


def _rel(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        try:
            return p.relative_to(ROOT)
        except ValueError:
            return p
    return p


def _lint_python(rel: Path) -> list[str]:
    venv_ruff = ROOT / "backend" / ".venv" / "bin" / "ruff"
    ruff = str(venv_ruff) if venv_ruff.is_file() else "ruff"
    try:
        result = subprocess.run(
            [ruff, "check", str(ROOT / rel)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT / "backend",
        )
        if result.returncode != 0:
            return [f"ruff check failed for {rel}:\n{result.stdout}{result.stderr}".strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return [f"ruff skipped for {rel}: {exc}"]
    return []


def _lint_typescript(rel: Path) -> list[str]:
    eslint = ROOT / "frontend" / "node_modules" / ".bin" / "eslint"
    if not eslint.is_file():
        return []
    try:
        result = subprocess.run(
            [str(eslint), str(ROOT / rel)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT / "frontend",
        )
        if result.returncode != 0:
            return [f"eslint failed for {rel}:\n{result.stdout}{result.stderr}".strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return [f"eslint skipped for {rel}: {exc}"]
    return []


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(json.dumps({}))
        return 0

    file_path = payload.get("file_path") or payload.get("path") or ""
    if not file_path:
        print(json.dumps({}))
        return 0

    rel = _rel(str(file_path))
    rel_posix = rel.as_posix()
    notes: list[str] = []

    if rel_posix.endswith(".py") and rel_posix.startswith("backend/"):
        notes.extend(_lint_python(rel))
    elif rel.suffix in {".ts", ".tsx"} and rel_posix.startswith("frontend/"):
        notes.extend(_lint_typescript(rel))

    counterpart = SPLIT_PAIR.get(rel_posix)
    if counterpart:
        notes.append(
            f"Text-split pair changed: also verify `{counterpart}` stays in sync "
            f"and run alignment tests (test_teil2_*, teil2TextSyncPlayback.test.ts)."
        )

    if notes:
        print(json.dumps({"additional_context": "\n\n".join(notes)}))
    else:
        print(json.dumps({}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
