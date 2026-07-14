#!/usr/bin/env python3
"""Import QLab video cues from CSV + local video folder (Pixera OSC cue numbers)."""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".MP4", ".MOV", ".M4V"}
_UMLAUT_MAP = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})
# Known filename typos / variants in local media folders.
_CLIP_ALIASES: dict[str, tuple[str, ...]] = {
    "MehlwuermerLangsam": ("mehlwurmner langsam", "mehlwuermer langsam"),
}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    stripped = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return stripped.translate(_UMLAUT_MAP)


def _ascii_fold(value: str) -> str:
    folded = _fold(value).lower()
    for src, dst in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        folded = folded.replace(src, dst)
    return folded


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _ascii_fold(value))


def _tokens(value: str) -> set[str]:
    folded = _fold(value)
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", folded)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    words = re.findall(r"[A-Za-z0-9]+", spaced)
    if len(words) <= 1:
        words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+", folded)
    return {_ascii_fold(word) for word in words if len(word) > 2}


def _match_score(clip_part: str, stem: str) -> int:
    target = _normalize_name(clip_part)
    normalized_stem = _normalize_name(stem)
    if not target:
        return 0
    if normalized_stem == target:
        return 100
    clip_tokens = _tokens(clip_part)
    stem_tokens = _tokens(stem)
    # Short Pixera names (Avatar, Clyde, Branko) — match if token appears in filename.
    if len(target) <= 10 and len(clip_tokens) <= 1:
        if target in stem_tokens or any(token.endswith(target) or target in token for token in stem_tokens):
            return 75
        return 0
    if target in normalized_stem or normalized_stem in target:
        return 85
    if not clip_tokens:
        return 0
    overlap = len(clip_tokens & stem_tokens) / len(clip_tokens)
    if overlap >= 0.6:
        return int(overlap * 80)
    if len(target) > 12 and len(normalized_stem) > 12:
        shared = sum(1 for left, right in zip(target, normalized_stem) if left == right)
        if shared / max(len(target), len(normalized_stem)) >= 0.85:
            return 65
    return 0


def _find_video_file(
    video_files: list[Path],
    clip_part: str,
) -> Path | None:
    best_path: Path | None = None
    best_score = 0
    aliases = {_normalize_name(alias) for alias in _CLIP_ALIASES.get(clip_part, ())}
    for path in video_files:
        stem_norm = _normalize_name(path.stem)
        if aliases and stem_norm in aliases:
            return path
        score = _match_score(clip_part, path.stem)
        if score > best_score:
            best_score = score
            best_path = path
    return best_path if best_score >= 50 else None


def _list_video_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise FileNotFoundError(f"Video-Ordner nicht gefunden: {folder}")
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix in VIDEO_EXTENSIONS
    )


def _load_csv_rows(
    csv_path: Path,
    *,
    source: str | None = None,
    projector: str | None = None,
) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"qlab_cue_number", "clip_part"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV braucht Spalten: {', '.join(sorted(required))}")
        rows = [dict(row) for row in reader]
    if source:
        rows = [row for row in rows if source in (row.get("source") or "")]
    if projector:
        rows = [row for row in rows if row.get("projector") == projector]
    return rows


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_applescript(cue_number: str, cue_name: str, video_path: Path) -> str:
    posix_path = _escape_applescript(str(video_path.resolve()))
    cue_number_esc = _escape_applescript(cue_number)
    cue_name_esc = _escape_applescript(cue_name)
    # QLab pattern: make selects new cue; avoid "at end of cues" (AppleScript "end" keyword).
    return f'''tell application id "com.figure53.QLab.5"
    activate
    if (count of workspaces) is 0 then error "Kein QLab-Workspace geöffnet"
    tell front workspace
        make type "video"
        set newCue to last item of (selected as list)
        set file target of newCue to POSIX file "{posix_path}"
        set the q number of newCue to "{cue_number_esc}"
        set the q name of newCue to "{cue_name_esc}"
    end tell
end tell'''


def _create_qlab_cue(cue_number: str, cue_name: str, video_path: Path) -> None:
    script = _build_applescript(cue_number, cue_name, video_path)
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)


def _existing_qlab_cue_numbers() -> set[str]:
    script = '''tell application id "com.figure53.QLab.5"
    if (count of workspaces) is 0 then return ""
    tell front workspace
        set out to ""
        repeat with c in cues
            try
                set n to q number of c
                if n is not missing value and n is not "" then
                    set out to out & n & linefeed
                end if
            end try
        end repeat
        return out
    end tell
end tell'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def import_cues(
    video_folder: Path,
    csv_path: Path,
    *,
    dry_run: bool = False,
    source: str | None = None,
    projector: str | None = None,
    skip_existing: bool = True,
) -> tuple[int, int, int, int]:
    rows = _load_csv_rows(csv_path, source=source, projector=projector)
    video_files = _list_video_files(video_folder)
    existing = _existing_qlab_cue_numbers() if skip_existing and not dry_run else set()
    created = 0
    missing = 0
    failed = 0
    skipped = 0

    for row in rows:
        cue_number = (row.get("qlab_cue_number") or "").strip()
        clip_part = (row.get("clip_part") or "").strip()
        if not cue_number or not clip_part:
            continue
        if cue_number in existing:
            skipped += 1
            continue
        match = _find_video_file(video_files, clip_part)
        if match is None:
            missing += 1
            print(f"  fehlt: {clip_part} (keine Datei in {video_folder})")
            continue
        if dry_run:
            print(f"  würde anlegen: {cue_number} <- {match.name}")
            created += 1
            continue
        try:
            _create_qlab_cue(cue_number, clip_part, match)
            existing.add(cue_number)
            created += 1
            print(f"  ok: {cue_number} <- {match.name}")
        except subprocess.CalledProcessError as exc:
            failed += 1
            err = (exc.stderr or exc.stdout or str(exc)).strip()
            print(f"  fehler: {cue_number} — {err}")

    return created, missing, failed, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QLab Video-Cues aus CSV importieren")
    parser.add_argument("video_folder", type=Path, help="Ordner mit .mp4/.mov Dateien")
    parser.add_argument("csv_path", type=Path, help="z. B. data/qlab_cue_list_rz21.csv")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts in QLab anlegen")
    parser.add_argument(
        "--source",
        choices=["avatar", "atmosphere", "database"],
        help="Nur Clips aus dieser OSC-Quelle (avatar|atmosphere|database)",
    )
    parser.add_argument(
        "--projector",
        choices=["rz21", "adam", "eva", "led"],
        help="Nur Cues für diesen Projektor (rz21|adam|eva|led)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Auch Cues anlegen, deren Nummer schon in QLab existiert",
    )
    args = parser.parse_args(argv)

    csv_path = args.csv_path if args.csv_path.is_absolute() else Path.cwd() / args.csv_path
    if not csv_path.is_file():
        print(f"CSV nicht gefunden: {csv_path}", file=sys.stderr)
        return 1

    print(f"CSV:   {csv_path}")
    print(f"Video: {args.video_folder}")
    if args.source:
        print(f"Filter: source={args.source}")
    if args.projector:
        print(f"Filter: projector={args.projector}")
    created, missing, failed, skipped = import_cues(
        args.video_folder,
        csv_path,
        dry_run=args.dry_run,
        source=args.source,
        projector=args.projector,
        skip_existing=not args.no_skip_existing,
    )
    print(f"Fertig: {created} angelegt, {skipped} übersprungen, {missing} ohne Datei, {failed} Fehler.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
