"""Tests for performance tryout and safety filtering."""

from app.director.cues.cue_models import DramaturgyDecision, LightCue, VisualCue
from app.director.cues.safety import SafetyState
from app.director.pipeline import _filter_decision_for_safety, _effective_dry_run


def test_filter_decision_strips_light_when_tryout() -> None:
    safety = SafetyState(performance_tryout=True, lights_enabled=False)
    decision = DramaturgyDecision(
        reason="test",
        tags=[],
        mood="tension",
        intensity=0.5,
        visual=VisualCue(clip_id="thiemo", video_type="avatar"),
        light=LightCue(scene_id="vorbuehnenzug"),
    )
    filtered = _filter_decision_for_safety(decision, safety)
    assert filtered.visual is not None
    assert filtered.light is None


def test_effective_dry_run_when_tryout() -> None:
    safety = SafetyState(performance_tryout=True)
    assert _effective_dry_run(safety) is True
