"""Parse and resolve avatar clip durations (Numbers «Zeit» = Sekunden)."""

from __future__ import annotations

import re
from datetime import datetime

from app.schemas.avatar_speech import AvatarSpeechCue

_DURATION_TEXT = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_duration_text_ms(value: str) -> int | None:
    """«00:24 Sek» oder «0:07» → Millisekunden."""
    cleaned = value.strip().lower().replace("sek", "").replace("sec", "").strip()
    match = _DURATION_TEXT.match(cleaned)
    if not match:
        return None
    total_sec = int(match.group(1)) * 60 + int(match.group(2))
    return total_sec * 1000 if total_sec > 0 else None


def parse_zeit_duration_ms(value: object) -> int | None:
    """Numbers «Zeit»: Sekunden (0:07:00 = 7 s), MM:SS oder «00:24 Sek»."""
    if isinstance(value, str):
        return parse_duration_text_ms(value)
    if not isinstance(value, datetime):
        return None
    if value.hour != 0:
        total_sec = value.hour * 3600 + value.minute * 60 + value.second
    elif value.second == 0 and value.minute > 0:
        total_sec = value.minute
    else:
        total_sec = value.minute * 60 + value.second
    return total_sec * 1000 if total_sec > 0 else None


def normalize_duration_ms(raw: int) -> int:
    """Legacy CSV: falsch als minute*60*1000 gespeichert (420000 für 7 s)."""
    if raw >= 60_000 and raw % 60_000 == 0:
        seconds = raw // 60_000
        if 1 <= seconds <= 3600:
            return seconds * 1_000
    return raw


def estimate_duration_ms(text: str) -> int:
    chars = len(text)
    return max(4000, min(18000, 3500 + chars * 45))


def cue_duration_ms(cue: AvatarSpeechCue) -> int | None:
    if cue.duration_ms is not None and cue.duration_ms > 0:
        return normalize_duration_ms(cue.duration_ms)
    return None


def resolve_avatar_beat_duration_ms(text: str, cues: list[AvatarSpeechCue]) -> int:
    """Numbers/cue duration takes priority; chorus uses longest clip."""
    text_est = estimate_duration_ms(text)
    known = [d for cue in cues if (d := cue_duration_ms(cue)) is not None]
    if known:
        return max(max(known), text_est)
    return text_est


def layer_duration_ms(cue: AvatarSpeechCue) -> int:
    return cue_duration_ms(cue) or estimate_duration_ms(cue.text)
