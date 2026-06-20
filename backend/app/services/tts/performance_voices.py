from app.schemas.script import ScriptSpeaker

PERFORMANCE_SPEAKERS: tuple[ScriptSpeaker, ...] = ("AI_A", "AI_B", "narrator")


def performance_speaker_for_sentence(
    beat_speaker: ScriptSpeaker | str,
    sentence_index: int,
    beat_order: int,
    pool: list[ScriptSpeaker] | None = None,
) -> ScriptSpeaker:
    speakers: tuple[ScriptSpeaker, ...]
    if pool:
        valid = [s for s in pool if s in PERFORMANCE_SPEAKERS]
        speakers = tuple(valid) if valid else PERFORMANCE_SPEAKERS
    else:
        speakers = PERFORMANCE_SPEAKERS

    try:
        start = speakers.index(beat_speaker)  # type: ignore[arg-type]
    except ValueError:
        start = beat_order % len(speakers)
    return speakers[(start + sentence_index) % len(speakers)]
