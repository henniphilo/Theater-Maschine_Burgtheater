from datetime import UTC, datetime, timedelta

from app.director.cues.cue_models import VisualCue
from app.director.cues.projector_state import ProjectorState


def test_avatar_lock_blocks_same_projector() -> None:
    state = ProjectorState()
    now = datetime.now(UTC)
    avatar = VisualCue(
        clip_id="avatar_del",
        video_type="avatar",
        projector="adam",
        lock_until_finished=True,
        duration_ms=5000,
        outputs=[{"output_id": "adam", "clip_id": "avatar_del"}],
    )
    state.lock_after_play(avatar, now=now, text_excerpt="Ein kurzer Text.")
    allowed, reason = state.can_play(
        VisualCue(clip_id="other", projector="adam", outputs=[{"output_id": "adam", "clip_id": "other"}]),
        now=now + timedelta(seconds=1),
    )
    assert allowed is False
    assert reason is not None


def test_rz21_atmosphere_parallel_while_avatar_locked() -> None:
    state = ProjectorState()
    now = datetime.now(UTC)
    avatar = VisualCue(
        clip_id="avatar_eva",
        video_type="avatar",
        projector="eva",
        lock_until_finished=True,
        duration_ms=8000,
        outputs=[{"output_id": "eva", "clip_id": "avatar_eva"}],
    )
    state.lock_after_play(avatar, now=now)
    atmo = VisualCue(
        clip_id="wolken",
        video_type="atmosphere",
        projector="rz21",
        outputs=[{"output_id": "rz21", "clip_id": "wolken"}],
    )
    allowed, _ = state.can_play(atmo, now=now + timedelta(seconds=1))
    assert allowed is True


def test_avatar_interrupt_allows_replacement_on_locked_projector() -> None:
    state = ProjectorState(allow_avatar_interrupt=True)
    now = datetime.now(UTC)
    first = VisualCue(
        clip_id="thiemo",
        video_type="avatar",
        projector="rz21",
        lock_until_finished=True,
        can_be_interrupted=True,
        duration_ms=7_000,
        outputs=[{"output_id": "rz21", "clip_id": "thiemo"}],
    )
    state.lock_after_play(first, now=now)
    second = VisualCue(
        clip_id="branko",
        video_type="avatar",
        projector="rz21",
        lock_until_finished=True,
        can_be_interrupted=True,
        duration_ms=9_000,
        outputs=[{"output_id": "rz21", "clip_id": "branko"}],
    )
    allowed, reason = state.can_play(second, now=now + timedelta(seconds=2))
    assert allowed is True
    assert reason is None
