"""Tests for Teil-2 cue overview builder."""

from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    LightCue,
    SoundCue,
    VisualCue,
)
from app.schemas.inszenierung import AvatarSpeechLayer, AvatarTextSegment
from app.services.teil2_cue_overview import build_cue_overview


def test_build_cue_overview_maps_keyword_and_atmosphere() -> None:
    dramaturgy = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.5,
        cue_points=[
            CuePoint(
                trigger=CuePointTrigger.KEYWORD,
                keyword="Delphin",
                sentence_index=0,
                light=LightCue(scene_id="warm"),
                sound=SoundCue(cue_id="drone"),
            )
        ],
    )
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["del1"],
            text_excerpt="Der Delphin spricht.",
            char_offset=0,
            start_sentence_index=0,
            end_sentence_index=0,
            avatar_layers=[
                AvatarSpeechLayer(
                    avatar_speech_id="del1",
                    avatar="delphin",
                    video_clip_id="del1_clip",
                    projector="rz21",
                )
            ],
        )
    ]
    atmosphere = [
        CuePoint(
            trigger=CuePointTrigger.TIME,
            time_offset_sec=12.0,
            visual=VisualCue(clip_id="clyde", projector="adam", video_type="atmosphere"),
        )
    ]
    overview = build_cue_overview(
        ["Der Delphin spricht.", "Zweiter Satz."],
        dramaturgy,
        segments,
        atmosphere,
    )
    assert len(overview.rows) == 2
    kinds = {item.kind for item in overview.rows[0].annotations}
    assert kinds == {"light", "sound", "avatar"}
    assert any("Stichwort: Delphin" in (item.reason or "") for item in overview.rows[0].annotations)
    assert overview.atmosphere_timeline[0].label == "clyde"
    assert overview.atmosphere_timeline[0].time_sec == 12.0
