from app.director.cues.cue_models import VisualAction, VisualCue
from app.director.cues.visual_outputs import resolve_visual_assignments
from app.director.outputs.osc_commands import build_osc_commands
from app.services.video_cue_catalog import get_video_cue_catalog_service


def test_default_clip_plays_on_all_available_projectors() -> None:
    visual = VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde")
    assignments = resolve_visual_assignments(visual)
    assert {output for output, _, _ in assignments} == {"rz21", "adam", "eva", "led"}


def test_narrator_clip_on_all_beamers_in_part2() -> None:
    visual = VisualCue(action=VisualAction.PLAY_CLIP, clip_id="nicolas")
    assignments = resolve_visual_assignments(visual)
    assert {output for output, _, _ in assignments} == {"rz21", "adam", "eva", "led"}


def test_explicit_projector_overrides_all_beamers_default() -> None:
    visual = VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde", projector="adam")
    assignments = resolve_visual_assignments(visual)
    assert assignments == [("adam", "clyde", VisualAction.PLAY_CLIP)]


def test_explicit_outputs_allow_mixed_clips_per_beamer() -> None:
    from app.director.cues.cue_models import VisualOutputAssignment

    visual = VisualCue(
        action=VisualAction.PLAY_CLIP,
        clip_id="clyde",
        outputs=[
            VisualOutputAssignment(output_id="rz21", clip_id="clyde"),
            VisualOutputAssignment(output_id="adam", clip_id="black"),
            VisualOutputAssignment(output_id="eva", clip_id="strand"),
        ],
    )
    assignments = resolve_visual_assignments(visual)
    assert assignments == [
        ("rz21", "clyde", VisualAction.PLAY_CLIP),
        ("adam", "black", VisualAction.PLAY_CLIP),
        ("eva", "strand", VisualAction.PLAY_CLIP),
    ]


def test_blackout_targets_all_projectors() -> None:
    visual = VisualCue(action=VisualAction.FADE_TO_BLACK)
    assignments = resolve_visual_assignments(visual)
    assert {output for output, clip, _ in assignments} == {"rz21", "adam", "eva", "led"}
    assert all(clip == "black" for _, clip, _ in assignments)


def test_osc_test_clyde_emits_four_pixera_commands() -> None:
    from app.director.cues.cue_models import DramaturgyDecision

    commands = build_osc_commands(
        DramaturgyDecision(visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde")),
        dry_run=True,
    )
    pixera_cmds = [c for c in commands if c.bridge == "pixera"]
    assert len(pixera_cmds) == 4
    assert {c.args[0] for c in pixera_cmds} == {
        "KI_RZ21.Clyde",
        "KI_Adam.Clyde",
        "KI_Eva.Clyde",
        "KI_LED.Clyde",
    }


def test_projectors_for_clip_uses_osc_list() -> None:
    service = get_video_cue_catalog_service()
    assert service.projectors_for_clip("clyde") == ["rz21", "adam", "eva", "led"]
    assert service.projectors_for_clip("inge") == ["rz21", "adam", "eva", "led"]
    part1 = service.projectors_for_clip("clyde", scope="part1")
    assert part1 == ["rz21", "adam", "eva", "led"]
