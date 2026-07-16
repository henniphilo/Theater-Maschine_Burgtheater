"""Tests for performance tryout and safety filtering."""

from unittest.mock import MagicMock, patch

from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    LightCue,
    OscCommand,
    VisualCue,
)
from app.director.cues.safety import SafetyState, get_safety_state
from app.director.outputs.osc_commands import apply_runtime_safety_dry_run, send_osc_commands
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


def test_runtime_safety_forces_light_dry_run_in_tryout() -> None:
    safety = get_safety_state()
    safety.update(performance_tryout=True, lights_enabled=False)
    cmd = OscCommand(
        bridge="light",
        host="10.101.90.112",
        port=3032,
        address="/eos/chan/1",
        args=[50.0],
        dry_run=False,
    )
    patched = apply_runtime_safety_dry_run(cmd)
    assert patched.dry_run is True
    safety.update(performance_tryout=False, lights_enabled=True)


def test_send_osc_commands_skips_light_tcp_when_tryout() -> None:
    safety = get_safety_state()
    safety.update(performance_tryout=True, lights_enabled=False)
    lighting = MagicMock()
    cmd = OscCommand(
        bridge="light",
        host="10.101.90.112",
        port=3032,
        address="/eos/chan/6",
        args=[40.0],
        dry_run=False,
    )
    with patch("app.director.outputs.osc_commands.settings") as mock_settings:
        mock_settings.osc_dry_run = False
        send_osc_commands(
            [cmd],
            {
                "touchdesigner": MagicMock(),
                "pixera": None,
                "sound": MagicMock(),
                "lighting": lighting,
            },
        )
    lighting.apply_channel.assert_called_once_with(6, intensity=0.4, dry_run=True)
    safety.update(performance_tryout=False, lights_enabled=True)
