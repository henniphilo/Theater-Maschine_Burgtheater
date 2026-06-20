from app.director.cues.cue_models import (
    DramaturgyDecision,
    LightAction,
    LightCue,
    SoundAction,
    SoundCue,
    VisualAction,
    VisualCue,
)
from app.director.outputs.osc_commands import build_osc_commands


def test_neutral_reset_builds_video_blackout_sound_cut_and_light_out() -> None:
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.FADE_TO_BLACK, fade_time=2, opacity=0),
        sound=SoundCue(action=SoundAction.TRIGGER_CUE, cue_id="alle_sounds_cut", volume=0),
        light=LightCue(action=LightAction.FADE_BLACKOUT, fade_time=2),
        reason="Neutrale Ausgangslage vor Stücktext",
    )
    commands = build_osc_commands(decision, dry_run=True)
    bridges = {cmd.bridge for cmd in commands}
    assert "sound" in bridges or "lighting" in bridges or "touchdesigner" in bridges or "pixera" in bridges
