"""Dramaturgy must not occupy avatar beamers."""

from __future__ import annotations

import warnings

from app.director.cues.cue_models import VisualOutputAssignment
from app.director.outputs.osc_commands import build_osc_commands
from app.schemas.inszenierung import AnarchyCurve, Gesamtkonzept, SceneCorpus
from app.services.inszenierung_komposition_service import InszenierungKompositionService
from app.services.teil2_beat_dramaturgy import build_dramaturgy_for_beat
from app.services.teil2_script_service import SCRIPT_SOURCE, build_timeline_from_csv, load_canonical_script_text


def test_dramaturgy_visual_avoids_avatar_projector() -> None:
    plan = build_timeline_from_csv(anarchy_curve=AnarchyCurve(start=0.2, end=0.2))
    moment = plan.moments[0]
    dramaturgy = build_dramaturgy_for_beat(moment)

    avatar_projector = moment.avatar_layers[0].projector
    assert avatar_projector == "rz21"

    cmds = build_osc_commands(dramaturgy, dry_run=True, video_scope="part2")
    pixera_targets = [cmd.args[0].split(".")[0] for cmd in cmds if cmd.bridge == "pixera"]
    assert pixera_targets
    assert all("RZ21" not in target.upper() for target in pixera_targets)

    for point in dramaturgy.cue_points:
        if point.visual and point.visual.projector:
            assert point.visual.projector != avatar_projector


def test_avatar_visual_cue_still_on_reserved_projector() -> None:
    plan = build_timeline_from_csv(anarchy_curve=AnarchyCurve(start=0.2, end=0.2))
    moment = plan.moments[0]
    visual = moment.avatar_layers[0].visual_cue
    assert visual is not None
    assert visual.projector == "rz21"
    assert visual.video_type == "avatar"


def test_atmosphere_video_cues_use_visual_output_assignment() -> None:
    plan = build_timeline_from_csv(anarchy_curve=AnarchyCurve(start=0.5, end=0.5))
    moment = plan.moments[0]
    moment.anarchy_level = 0.5
    build_dramaturgy_for_beat(moment)

    assert moment.atmosphere_video_cues
    first_output = moment.atmosphere_video_cues[0].outputs[0]
    assert isinstance(first_output, VisualOutputAssignment)


def test_compose_plan_serializes_without_visual_output_assignment_warnings() -> None:
    corpus = SceneCorpus(
        id="test-corpus",
        title="AVATAR Text Delfin bis Wolf",
        script_source=SCRIPT_SOURCE,
        script_text=load_canonical_script_text(),
        gesamtkonzept=Gesamtkonzept(
            thesis="Geld als Maske",
            anarchy_curve=AnarchyCurve(start=0.35, end=1.0),
        ),
    )
    plan = InszenierungKompositionService().compose_plan(corpus)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plan.model_dump_json()

    assignment_warnings = [
        w for w in caught if "VisualOutputAssignment" in str(w.message)
    ]
    assert not assignment_warnings
