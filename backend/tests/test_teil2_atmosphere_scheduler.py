"""Tests for Teil-2 atmosphere scheduler."""

from app.director.cues.cue_models import CuePointTrigger, DramaturgyDecision
from app.schemas.inszenierung import AnarchyCurve, AvatarSpeechLayer, AvatarTextSegment
from app.services.teil2_atmosphere_scheduler import (
    build_avatar_windows,
    estimate_script_duration_sec,
    free_projectors_at,
    reserved_projectors_at,
)


def test_free_projectors_excludes_avatar_beamer() -> None:
    script = "A" * 1000
    segments = [
        AvatarTextSegment(
            csv_cue_ids=["bak1"],
            text_excerpt="test",
            char_offset=100,
            start_sentence_index=1,
            end_sentence_index=1,
            avatar_layers=[
                AvatarSpeechLayer(
                    avatar_speech_id="bak1",
                    avatar="baerenklau",
                    video_clip_id="bak1_clip",
                    projector="rz21",
                )
            ],
        )
    ]
    total = estimate_script_duration_sec(script, segments)
    windows = build_avatar_windows(script, segments, total)
    assert windows
    mid = (windows[0].start_sec + windows[0].end_sec) / 2
    reserved = reserved_projectors_at(windows, mid)
    assert "rz21" in reserved
    free = free_projectors_at(windows, mid)
    assert "rz21" not in free
    assert "adam" in free or "eva" in free


def test_rule_fallback_produces_time_cues(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.director_dramaturgy_mode", "rules")
    from app.services.teil2_atmosphere_scheduler import Teil2AtmosphereScheduler

    script = "Erster Satz. Zweiter Satz. Dritter Satz."
    segments: list[AvatarTextSegment] = []
    dramaturgy = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.5,
        cue_points=[],
    )
    scheduler = Teil2AtmosphereScheduler()
    points = __import__("asyncio").run(
        scheduler.schedule(
            script_text=script,
            sentences=["Erster Satz.", "Zweiter Satz.", "Dritter Satz."],
            segments=segments,
            gesamtkonzept=__import__(
                "app.schemas.inszenierung", fromlist=["Gesamtkonzept"]
            ).Gesamtkonzept(anarchy_curve=AnarchyCurve()),
            dramaturgy=dramaturgy,
            avatar_clip_ids=set(),
        )
    )
    assert points
    assert all(p.trigger == CuePointTrigger.TIME for p in points)
    assert all(p.visual and p.visual.clip_id for p in points)
