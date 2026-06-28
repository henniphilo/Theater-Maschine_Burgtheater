"""Route atmosphere visuals away from reserved avatar beamers."""

from __future__ import annotations

from app.director.cues.cue_models import DramaturgyDecision, VisualCue, VisualOutputAssignment
from app.services.teil2_projector_assignment import ALL_PROJECTORS


def _assign_atmosphere_visual(visual: VisualCue, projector: str) -> VisualCue:
    clip_id = visual.clip_id
    return visual.model_copy(
        update={
            "video_type": "atmosphere",
            "projector": projector,  # type: ignore[arg-type]
            "lock_until_finished": False,
            "can_be_interrupted": True,
            "blend_mode": "layer",
            "outputs": [VisualOutputAssignment(output_id=projector, clip_id=clip_id)],
        }
    )


def _pick_dramaturgy_projectors(
    reserved: set[str],
    count: int,
    *,
    seed: int = 0,
) -> list[str]:
    pool = [p for p in ALL_PROJECTORS if p not in reserved]
    if not pool:
        pool = list(ALL_PROJECTORS)
    if count <= 1:
        return [pool[seed % len(pool)]]
    return [pool[(seed + index) % len(pool)] for index in range(count)]


def route_dramaturgy_away_from_projectors(
    decision: DramaturgyDecision,
    reserved_projectors: set[str],
    *,
    avatar_clip_ids: set[str] | None = None,
    seed: int = 0,
) -> DramaturgyDecision:
    """Keep reserved beamers free; strip avatar clips from LLM visuals."""
    avatar_clips = avatar_clip_ids or set()
    cue_count = max(1, len(decision.cue_points))
    dram_projectors = _pick_dramaturgy_projectors(reserved_projectors, cue_count, seed=seed)

    if (
        decision.visual
        and decision.visual.clip_id
        and decision.visual.clip_id not in avatar_clips
        and decision.visual.video_type != "avatar"
    ):
        decision.visual = _assign_atmosphere_visual(decision.visual, dram_projectors[0])

    for index, point in enumerate(decision.cue_points):
        if not point.visual or not point.visual.clip_id:
            continue
        if point.visual.clip_id in avatar_clips or point.visual.video_type == "avatar":
            point.visual = None
            continue
        target = dram_projectors[index % len(dram_projectors)]
        point.visual = _assign_atmosphere_visual(point.visual, target)

    return decision


def reserved_projectors_from_segments(segments) -> set[str]:
    reserved: set[str] = set()
    for segment in segments:
        for layer in segment.avatar_layers:
            if layer.projector:
                reserved.add(layer.projector)
            for output in layer.outputs or []:
                reserved.add(output.output_id)
    return reserved
