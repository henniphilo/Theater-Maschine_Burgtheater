#!/usr/bin/env python3
"""Export Avatar Textzuordnung.csv from Numbers source + sync video/OSC catalogs."""

from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MEDIA_VIDEO = REPO_ROOT / "media" / "video"
NUMBERS_DEFAULT = MEDIA_VIDEO / "Textzuordnung Del-Wolf-28-06-26 Final-2.numbers"
CSV_OUT = MEDIA_VIDEO / "Avatar Textzuordnung.csv"
OSC_AVATAR_OUT = MEDIA_VIDEO / "OSCBefehllisteAvatare.txt"
SCRIPT_TXT = REPO_ROOT / "Stücktext" / "AVATAR Text Delfin bis Wolf.txt"
VIDEO_CSV = MEDIA_VIDEO / "Video Übersicht.csv"
PROJECTOR_CSV = MEDIA_VIDEO / "Projektor Übersicht.csv"

NUMBERS_TO_PIXERA: dict[str, str] = {
    "Hier unter der Erde": "HierUnterDerErde",
    "Kuscheltier Schlachtung": "KuscheltierSchlachtung",
    "Der Hase verlässt die Bühne": "DerHaseVerlaesstDieBuehne",
    "Der Hase verlässt die Bühne": "DerHaseVerlaesstDieBuehne",
    "BK8_Hai Schaedel": "BK8_HaiSchaedel",
    "BK8_Mavie 1": "BK8_Mavie1",
    "LG1_Das Lamm Gottes": "DasLammGottes",
}


def slug_id(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.strip())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    return normalized.strip("_")


def numbers_clip_to_pixera(name: str) -> str:
    stripped = name.strip()
    if stripped in NUMBERS_TO_PIXERA:
        return NUMBERS_TO_PIXERA[stripped]
    compact = stripped.replace(" ", "")
    decomposed = unicodedata.normalize("NFKD", compact)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def infer_avatar(clip_name: str) -> str:
    upper = clip_name.upper().replace(" ", "")
    if upper.startswith(("BK", "BAK", "BÄK", "BAEK")):
        return "baerenklau"
    if upper.startswith("LG"):
        return "lamm"
    if upper.startswith("PET"):
        return "petya"
    if upper.startswith("WO"):
        return "wolf"
    if upper.startswith(("MO", "SCH", "DEL", "HIER", "KUSCHELTIER", "DERHASE")):
        return "delphin"
    return "delphin"


def parse_zeit_duration_ms(value: object) -> int | None:
    """Numbers «Zeit»: Sekunden (0:07:00 = 7 s) oder MM:SS (0:01:30 = 90 s)."""
    from app.services.avatar_duration import parse_zeit_duration_ms as _parse

    return _parse(value)


def export_from_numbers(path: Path) -> list[dict[str, str | int]]:
    from numbers_parser import Document

    doc = Document(path)
    table = doc.sheets[0].tables[0]
    rows: list[dict[str, str | int]] = []
    for r in range(1, table.num_rows):
        clip_raw = table.cell(r, 0).value
        text = table.cell(r, 1).value
        zeit = table.cell(r, 2).value if table.num_cols > 2 else None
        if not clip_raw or not text:
            continue
        clip_name = str(clip_raw).strip()
        pixera = numbers_clip_to_pixera(clip_name)
        cue_id = slug_id(pixera)
        duration_ms = parse_zeit_duration_ms(zeit)
        row: dict[str, str | int] = {
            "id": cue_id,
            "text": str(text).strip(),
            "avatar": infer_avatar(clip_name),
            "video_clip_id": cue_id,
            "scene_ref": pixera,
        }
        if duration_ms is not None:
            row["duration_ms"] = duration_ms
        rows.append(row)
    return rows


def write_avatar_csv(rows: list[dict[str, str | int]]) -> None:
    with CSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "text", "avatar", "video_clip_id", "scene_ref", "duration_ms"],
            delimiter=";",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "text": row["text"],
                    "avatar": row["avatar"],
                    "video_clip_id": row["video_clip_id"],
                    "scene_ref": row["scene_ref"],
                    "duration_ms": row.get("duration_ms", ""),
                }
            )


def write_script_txt(rows: list[dict[str, str | int]]) -> None:
    seen: set[str] = set()
    parts: list[str] = []
    for row in rows:
        key = " ".join(str(row["text"]).split())
        if key in seen:
            continue
        seen.add(key)
        parts.append(str(row["text"]))
    SCRIPT_TXT.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def load_projector_prefixes() -> list[str]:
    prefixes: list[str] = []
    if PROJECTOR_CSV.is_file():
        with PROJECTOR_CSV.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                prefix = (row.get("pixera_prefix") or "").strip()
                if prefix:
                    prefixes.append(prefix)
    if not prefixes:
        prefixes = ["KI_RZ21", "KI_Adam", "KI_Eva", "KI_LED"]
    return prefixes


def write_osc_avatar_befehlliste(rows: list[dict[str, str | int]]) -> int:
    """Write OSC cue/apply lines for every avatar clip on all projectors."""
    scene_refs = [str(row["scene_ref"]) for row in rows]
    prefixes = load_projector_prefixes()
    blocks: list[str] = []
    for prefix in prefixes:
        blocks.extend(
            f'("/pixera/args/cue/apply", "{prefix}.{scene_ref}")' for scene_ref in scene_refs
        )
        blocks.append("")
    OSC_AVATAR_OUT.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    return len(scene_refs) * len(prefixes)


def parse_osc_clip_names() -> dict[str, str]:
    from app.director.media.video_inventory import parse_osc_befehlliste

    names: dict[str, str] = {}
    for filename in ("OSCBefehllisteOhneAvatare.txt", "OSCBefehllisteAvatare.txt"):
        path = MEDIA_VIDEO / filename
        if not path.is_file():
            continue
        for _prefix, pixera_name in parse_osc_befehlliste(path):
            names[slug_id(pixera_name)] = pixera_name
    return names


def sync_video_overview(rows: list[dict[str, str | int]], osc_clips: dict[str, str]) -> None:
    existing: dict[str, dict[str, str]] = {}
    if VIDEO_CSV.is_file():
        with VIDEO_CSV.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                clip_id = (row.get("clip_id") or "").strip()
                if clip_id:
                    existing[clip_id] = row

    for row in rows:
        clip_id = str(row["video_clip_id"])
        pixera_name = str(row["scene_ref"])
        existing[clip_id] = {
            "clip_id": clip_id,
            "pixera_name": pixera_name,
            "beschreibung": pixera_name,
            "tags": str(row.get("avatar", "")),
            "stimmungen": "neutral,spannung",
        }

    for clip_id, pixera_name in sorted(osc_clips.items()):
        if clip_id in existing:
            existing[clip_id]["pixera_name"] = pixera_name
            continue
        existing[clip_id] = {
            "clip_id": clip_id,
            "pixera_name": pixera_name,
            "beschreibung": pixera_name,
            "tags": clip_id,
            "stimmungen": "neutral,spannung",
        }

    fieldnames = ["clip_id", "pixera_name", "beschreibung", "tags", "stimmungen"]
    with VIDEO_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for clip_id in sorted(existing.keys()):
            row = existing[clip_id]
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def sync_video_cue_durations(rows: list[dict[str, str | int]]) -> int:
    """Write duration_ms + video_type avatar into data/video_cues.json."""
    from app.services.video_cue_catalog import catalog_json_path

    path = catalog_json_path()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"version": 1, "osc_address": "/pixera/args/cue/apply", "projectors": [], "clips": []}

    clips_by_id = {c["id"]: c for c in payload.get("clips", []) if c.get("id")}
    updated = 0
    for row in rows:
        clip_id = str(row.get("video_clip_id") or "").strip()
        duration = row.get("duration_ms")
        if not clip_id or not duration:
            continue
        clip = clips_by_id.get(clip_id, {"id": clip_id, "pixera_name": row.get("scene_ref", clip_id)})
        clip["duration_ms"] = int(duration)
        clip["video_type"] = "avatar"
        clip["can_be_interrupted"] = False
        clips_by_id[clip_id] = clip
        updated += 1

    payload["clips"] = sorted(clips_by_id.values(), key=lambda c: c["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return updated


def main() -> int:
    numbers_path = Path(sys.argv[1]) if len(sys.argv) > 1 else NUMBERS_DEFAULT
    if not numbers_path.is_file():
        print(f"Numbers-Datei nicht gefunden: {numbers_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    rows = export_from_numbers(numbers_path)
    write_avatar_csv(rows)
    write_script_txt(rows)
    osc_line_count = write_osc_avatar_befehlliste(rows)
    osc_clips = parse_osc_clip_names()
    sync_video_overview(rows, osc_clips)
    duration_count = sync_video_cue_durations(rows)
    print(f"Exported {len(rows)} avatar cues → {CSV_OUT.name}")
    print(f"Wrote {osc_line_count} OSC lines → {OSC_AVATAR_OUT.name}")
    print(f"Updated {VIDEO_CSV.name} ({len(rows)} avatar clips)")
    print(f"Updated {SCRIPT_TXT.name}")
    print(f"Set duration_ms on {duration_count} avatar clips in video_cues.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
