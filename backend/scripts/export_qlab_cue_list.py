#!/usr/bin/env python3
"""Export QLab cue numbers from Pixera OSC lists (database + avatar + atmosphere)."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from app.core.config import settings
from app.director.media.video_inventory import parse_osc_befehlliste
from app.services.video_pixera_aliases import catalog_pixera_to_osc_name, osc_pixera_to_catalog_name

OSC_PATTERN = re.compile(r'\("/pixera/args/cue/apply",\s*"([^"]+)\.([^"]+)"\)')

OSC_SOURCES: list[tuple[str, str]] = [
    ("OSCBefehlliste.txt", "database"),
    ("media/video/OSCBefehllisteAvatare.txt", "avatar"),
    ("media/video/OSCBefehllisteOhneAvatare.txt", "atmosphere"),
]

PROJECTOR_LABELS = {
    "KI_RZ21": "rz21",
    "KI_Adam": "adam",
    "KI_Eva": "eva",
    "KI_LED": "led",
}


def _repo_root() -> Path:
    data_dir = Path(settings.director_data_dir)
    if not data_dir.is_absolute():
        data_dir = SCRIPT_ROOT.parent / data_dir
    return data_dir.parent


def _load_catalog():
    from app.schemas.video_cues import VideoCueCatalog
    from app.services.video_cue_catalog import get_video_cue_catalog_service

    catalog_path = _repo_root() / "data" / "video_cues.json"
    if catalog_path.is_file():
        return VideoCueCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    return get_video_cue_catalog_service().load("part2")


def _clip_lookup(catalog) -> dict[str, object]:
    by_pixera: dict[str, object] = {}
    for clip in catalog.clips:
        by_pixera[clip.pixera_name] = clip
        osc_name = catalog_pixera_to_osc_name(clip.pixera_name)
        if osc_name != clip.pixera_name:
            by_pixera[osc_name] = clip
    return by_pixera


def _resolve_clip(clip_name: str, by_pixera: dict[str, object]):
    clip = by_pixera.get(clip_name)
    if clip is not None:
        return clip
    catalog_name = osc_pixera_to_catalog_name(clip_name)
    if catalog_name != clip_name:
        return by_pixera.get(catalog_name)
    return None


def _theatermaschine_cue_name(prefix: str, clip_name: str, clip) -> str:
    osc_clip = catalog_pixera_to_osc_name(clip.pixera_name) if clip is not None else clip_name
    return f"{prefix}.{osc_clip}"


def _parse_osc_file(path: Path, source: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for prefix, clip_name in parse_osc_befehlliste(path):
        rows.append(
            {
                "osc_list_name": f"{prefix}.{clip_name}",
                "projector_prefix": prefix,
                "projector_id": PROJECTOR_LABELS.get(prefix, prefix.lower()),
                "clip_part": clip_name,
                "source": source,
                "osc_file": path.name,
            }
        )
    return rows


def collect_rows() -> list[dict[str, str]]:
    root = _repo_root()
    catalog = _load_catalog()
    by_pixera = _clip_lookup(catalog)

    merged: dict[str, dict[str, str]] = {}
    for rel_path, source in OSC_SOURCES:
        path = root / rel_path
        if not path.is_file():
            continue
        for row in _parse_osc_file(path, source):
            clip = _resolve_clip(row["clip_part"], by_pixera)
            qlab_number = _theatermaschine_cue_name(row["projector_prefix"], row["clip_part"], clip)
            clip_id = clip.id if clip is not None else ""
            pixera_catalog_name = clip.pixera_name if clip is not None else ""
            alias_note = ""
            if clip is not None:
                osc_from_catalog = catalog_pixera_to_osc_name(clip.pixera_name)
                if osc_from_catalog != row["clip_part"] and row["clip_part"] != clip.pixera_name:
                    alias_note = f"OSC-Liste: {row['clip_part']} → TM sendet: {osc_from_catalog}"

            entry = {
                "qlab_cue_number": qlab_number,
                "osc_list_name": row["osc_list_name"],
                "projector": row["projector_id"],
                "projector_prefix": row["projector_prefix"],
                "clip_part": row["clip_part"],
                "clip_id": clip_id,
                "pixera_catalog_name": pixera_catalog_name,
                "source": row["source"],
                "osc_file": row["osc_file"],
                "alias_note": alias_note,
                "suggested_filename": f"{row['clip_part']}.mp4",
            }
            existing = merged.get(qlab_number)
            if existing is None:
                merged[qlab_number] = entry
                continue
            if existing["source"] != entry["source"]:
                existing["source"] = f"{existing['source']}+{entry['source']}"

    return sorted(merged.values(), key=lambda row: (row["projector_prefix"], row["clip_part"]))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "qlab_cue_number",
        "projector",
        "clip_part",
        "clip_id",
        "source",
        "osc_file",
        "osc_list_name",
        "pixera_catalog_name",
        "alias_note",
        "suggested_filename",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export QLab cue list from Pixera OSC files")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_repo_root() / "data",
        help="Output directory for CSV files",
    )
    args = parser.parse_args()

    rows = collect_rows()
    if not rows:
        print("Keine OSC-Einträge gefunden.", file=sys.stderr)
        return 1

    all_path = args.out_dir / "qlab_cue_list_all.csv"
    rz21_path = args.out_dir / "qlab_cue_list_rz21.csv"
    rz21_rows = [row for row in rows if row["projector"] == "rz21"]

    write_csv(all_path, rows)
    write_csv(rz21_path, rz21_rows)

    counts = Counter(row["source"] for row in rows)
    print(f"Export: {len(rows)} QLab-Cues → {all_path}")
    print(f"RZ21:   {len(rz21_rows)} QLab-Cues → {rz21_path}")
    print("Quellen:", dict(counts))
    alias_rows = [row for row in rows if row["alias_note"]]
    if alias_rows:
        print(f"Hinweis: {len(alias_rows)} Einträge mit Alias (Spalte alias_note in CSV)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
