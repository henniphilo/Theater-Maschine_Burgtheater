from app.schemas.script import ScriptSpeaker

PERFORMANCE_SPEAKERS: tuple[ScriptSpeaker, ...] = ("AI_A", "AI_B", "narrator")


def performance_speaker_for_sentence(
    beat_speaker: ScriptSpeaker | str,
    sentence_index: int,
    beat_order: int,
) -> ScriptSpeaker:
    try:
        start = PERFORMANCE_SPEAKERS.index(beat_speaker)  # type: ignore[arg-type]
    except ValueError:
        start = beat_order % len(PERFORMANCE_SPEAKERS)
    return PERFORMANCE_SPEAKERS[(start + sentence_index) % len(PERFORMANCE_SPEAKERS)]
