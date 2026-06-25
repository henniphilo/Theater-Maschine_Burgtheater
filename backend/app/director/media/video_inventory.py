import csv
import re
from pathlib import Path

from app.schemas.video_cues import VideoClipEntry, VideoCueCatalog, VideoProjectorEntry


def resolve_video_overview_paths(data_dir: Path) -> tuple[Path | None, Path | None]:
    resolved_data = data_dir.resolve() if data_dir.is_absolute() else (Path.cwd() / data_dir).resolve()
    roots = [
        resolved_data.parent,
        data_dir.parent,
        Path.cwd(),
        Path.cwd().parent,
        Path("/app"),
    ]
    clips_path: Path | None = None
    projectors_path: Path | None = None
    for root in roots:
        candidate_clips = root / "media" / "video" / "Video Übersicht.csv"
        candidate_projectors = root / "media" / "video" / "Projektor Übersicht.csv"
        if candidate_clips.is_file():
            clips_path = candidate_clips.resolve()
        if candidate_projectors.is_file():
            projectors_path = candidate_projectors.resolve()
        if clips_path and projectors_path:
            break
    return clips_path, projectors_path


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _slug_id(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    return normalized.strip("_")


def parse_osc_befehlliste(path: Path) -> list[tuple[str, str]]:
    """Parse Pixera OSC list lines into (pixera_prefix, clip_name) pairs."""
    pairs: list[tuple[str, str]] = []
    pattern = re.compile(
        r'\("/pixera/args/cue/apply",\s*"([^"]+)\.([^"]+)"\)',
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        pairs.append((match.group(1), match.group(2)))
    return pairs


OSC_PART1_FILENAME = "OSCBefehllisteOhneAvatare.txt"
OSC_PART2_AVATAR_FILENAME = "OSCBefehllisteAvatare.txt"
OSC_LEGACY_FILENAME = "OSCBefehlliste.txt"


def resolve_osc_befehlliste_path(data_dir: Path, *, filename: str | None = None) -> Path | None:
    target_name = filename or OSC_LEGACY_FILENAME
    resolved_data = data_dir.resolve() if data_dir.is_absolute() else (Path.cwd() / data_dir).resolve()
    roots = [
        resolved_data.parent,
        data_dir.parent,
        Path.cwd(),
        Path.cwd().parent,
        Path("/app"),
    ]
    for root in roots:
        candidate = root / "media" / "video" / target_name
        if candidate.is_file():
            return candidate.resolve()
    return None


def resolve_osc_befehlliste_paths_for_scope(data_dir: Path, scope: str) -> list[Path]:
    """part1 → ohne Avatare; part2 → ohne + Erzähler-Avatare (Vereinigung)."""
    part1_path = resolve_osc_befehlliste_path(data_dir, filename=OSC_PART1_FILENAME)
    avatar_path = resolve_osc_befehlliste_path(data_dir, filename=OSC_PART2_AVATAR_FILENAME)
    if scope == "part1":
        if part1_path:
            return [part1_path]
        legacy = resolve_osc_befehlliste_path(data_dir, filename=OSC_LEGACY_FILENAME)
        return [legacy] if legacy else []
    paths: list[Path] = []
    if part1_path:
        paths.append(part1_path)
    if avatar_path:
        paths.append(avatar_path)
    if paths:
        return paths
    legacy = resolve_osc_befehlliste_path(data_dir, filename=OSC_LEGACY_FILENAME)
    return [legacy] if legacy else []


def parse_osc_befehlliste_files(paths: list[Path]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for path in paths:
        pairs.extend(parse_osc_befehlliste(path))
    return pairs


def load_video_cues_from_csv(
    clips_path: Path,
    projectors_path: Path | None = None,
) -> VideoCueCatalog:
    projectors: list[VideoProjectorEntry] = []
    if projectors_path and projectors_path.is_file():
        with projectors_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            for row in reader:
                output_id = _slug_id(row.get("output_id", ""))
                prefix = (row.get("pixera_prefix") or "").strip()
                if not output_id or not prefix:
                    continue
                projectors.append(
                    VideoProjectorEntry(
                        id=output_id,
                        pixera_prefix=prefix,
                        name=(row.get("name") or output_id).strip(),
                        description=(row.get("beschreibung") or "").strip(),
                    )
                )

    clips: list[VideoClipEntry] = []
    with clips_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            clip_id = _slug_id(row.get("clip_id", ""))
            pixera_name = (row.get("pixera_name") or "").strip()
            if not clip_id or not pixera_name:
                continue
            label = (row.get("label") or pixera_name).strip()
            clips.append(
                VideoClipEntry(
                    id=clip_id,
                    pixera_name=pixera_name,
                    label=label,
                    description=(row.get("beschreibung") or "").strip(),
                    tags=_split_list(row.get("tags", "")) or [clip_id],
                    moods=_split_list(row.get("stimmungen") or row.get("moods", "")) or ["neutral"],
                )
            )

    return VideoCueCatalog(projectors=projectors, clips=clips)
