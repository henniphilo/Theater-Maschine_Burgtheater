#!/usr/bin/env python3
"""Assign QLab video cues to preview stages by projector prefix in cue number."""

from __future__ import annotations

import argparse
import subprocess
import sys

STAGE_BY_PREFIX = (
    ("KI_RZ21.", 1),
    ("KI_Adam.", 2),
    ("KI_Eva.", 3),
    ("KI_LED.", 4),
)


def stage_for_cue_number(cue_number: str) -> int | None:
    for prefix, stage in STAGE_BY_PREFIX:
        if cue_number.startswith(prefix):
            return stage
    return None


def _build_applescript() -> str:
    branches = []
    for prefix, stage in STAGE_BY_PREFIX:
        branches.append(
            f'''                else if cueNum begins with "{prefix}" then
                    set stage number of c to {stage}
                    set updated to updated + 1'''
        )
    branch_block = "\n".join(branches).replace("else if", "if", 1)
    return f'''tell application id "com.figure53.QLab.5"
    activate
    if (count of workspaces) is 0 then error "Kein QLab-Workspace geöffnet"
    tell front workspace
        set updated to 0
        repeat with c in cues
            if q type of c is "Video" then
                set cueNum to q number of c
{branch_block}
                end if
            end if
        end repeat
        return updated
    end tell
end tell'''


def assign_stages(*, dry_run: bool = False) -> int:
    if dry_run:
        print("Dry-run — würde Video-Cues zuordnen:")
        for prefix, stage in STAGE_BY_PREFIX:
            print(f"  {prefix}* -> Stage {stage}")
        return 0

    script = _build_applescript()
    result = subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
    updated = int(result.stdout.strip() or "0")
    print(f"Video-Stages gesetzt: {updated} Cues")
    for prefix, stage in STAGE_BY_PREFIX:
        print(f"  {prefix}* -> Stage {stage}")
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QLab Video-Cues auf Preview-Stages verteilen")
    parser.add_argument("--dry-run", action="store_true", help="Nur Mapping anzeigen")
    args = parser.parse_args(argv)
    try:
        assign_stages(dry_run=args.dry_run)
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or str(exc)).strip()
        print(f"Fehler: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
