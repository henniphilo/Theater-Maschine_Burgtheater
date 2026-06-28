"""Tests for Teil-2 CSV-to-script sentence alignment."""

from __future__ import annotations

from app.schemas.avatar_speech import AvatarSpeechCue
from app.services.teil2_text_alignment import align_avatar_csv_to_script, group_cues_into_segments


def _cue(
    cue_id: str,
    text: str,
    avatar: str = "delphin",
    clip: str = "avatar",
    duration_ms: int | None = None,
) -> AvatarSpeechCue:
    return AvatarSpeechCue(
        id=cue_id,
        avatar=avatar,
        text=text,
        video_clip_id=clip,
        duration_ms=duration_ms,
    )


def test_align_finds_baerenklauer_sentence_index():
    script = (
        "23. Der Delphin? Man hat mich dazu gezwungen.\n\n"
        "24. Der Bärenklauer übernimmt.\n\n"
        "25. Das Lamm Gottes,\n"
    )
    cues = [_cue("BK1_Caro", "24. Der Bärenklauer übernimmt.", "baerenklau", "bk1_caro", 900_000)]
    segments, warnings = align_avatar_csv_to_script(script, cues)
    assert not warnings
    assert len(segments) == 1
    assert segments[0].csv_cue_ids == ["BK1_Caro"]
    assert segments[0].char_offset is not None
    assert segments[0].start_sentence_index == 3
    assert segments[0].avatar_layers[0].visual_cue is not None
    assert segments[0].avatar_layers[0].visual_cue.duration_ms == 15_000


def test_chorus_groups_into_one_segment_with_three_layers():
    chorus_text = (
        "24 Der Bärenklauer Ich steige mit, ich steige hoch, ich wachse, "
        "mit allem, was ich habe, Ich schieße Geld nach, alles wird mehr werden, "
        "Egal, es wird mehr werden, alles wird mehr werden,"
    )
    script = chorus_text
    cues = [
        _cue("bk1_caro", chorus_text, "baerenklau", "bk1_caro"),
        _cue("bk1_caroline", chorus_text, "baerenklau", "bk1_caroline"),
        _cue("bk1_thomas", chorus_text, "baerenklau", "bk1_thomas"),
    ]
    groups = group_cues_into_segments(cues)
    assert len(groups) == 1
    assert len(groups[0]) == 3
    segments, warnings = align_avatar_csv_to_script(script, cues)
    assert not warnings
    assert len(segments) == 1
    assert len(segments[0].avatar_layers) == 3
    assert segments[0].csv_cue_ids == ["bk1_caro", "bk1_caroline", "bk1_thomas"]


def test_missing_text_emits_warning():
    script = "Nur ein bekannter Text."
    cues = [_cue("DEL1", "Unbekannter Avatar-Textabschnitt hier.")]
    segments, warnings = align_avatar_csv_to_script(script, cues)
    assert not segments
    assert any("DEL1" in warning for warning in warnings)
