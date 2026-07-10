"""Tests for performance tryout and safety filtering."""

from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    LightCue,
    VisualCue,
)
from app.director.cues.safety import SafetyState, get_safety_state
from app.director.pipeline import (
    DirectorPipeline,
    _effective_dry_run,
    _filter_decision_for_safety,
)


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


def test_execute_layered_omits_light_commands_in_tryout() -> None:
    safety = get_safety_state()
    safety.update(performance_tryout=True, lights_enabled=False)
    pipeline = DirectorPipeline(safety=safety)
    decision = DramaturgyDecision(
        reason="test",
        tags=["teil2"],
        mood="anarchy",
        intensity=0.6,
        cue_points=[
            CuePoint(
                trigger=CuePointTrigger.KEYWORD,
                keyword="Geld",
                sound={"action": "trigger_cue", "cue_id": "drone"},
                light=LightCue(scene_id="warm"),
            )
        ],
    )
    result = pipeline.execute_layered(decision, skip_interval_check=True)
    assert result.executed
    assert not any(cmd.bridge == "light" for cmd in result.planned_commands)
    assert not any(cmd.bridge == "light" for cmd in result.osc_commands)
    safety.update(performance_tryout=False, lights_enabled=True)
