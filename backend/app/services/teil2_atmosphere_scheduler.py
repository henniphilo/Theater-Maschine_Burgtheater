"""LLM-driven time-based atmosphere video scheduling for Teil 2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.core.config import settings
from app.director.cues.cue_models import (
    CuePoint,
    CuePointTrigger,
    DramaturgyDecision,
    VisualCue,
    VisualOutputAssignment,
)
from app.director.dramaturgy.llm_director import LLMDirector
from app.schemas.inszenierung import AnarchyCurve, AvatarTextSegment, Gesamtkonzept
from app.services.ai_service import AIService
from app.services.avatar_duration import estimate_duration_ms
from app.services.part2_cue_density import cue_intervals_for_anarchy
from app.services.teil2_atmosphere_cues import inject_atmosphere_visuals
from app.services.teil2_projector_assignment import ALL_PROJECTORS, pick_atmosphere_projectors
from app.services.video_scope import _clip_ids_for_scope


@dataclass(frozen=True)
class AvatarWindow:
    start_sec: float
    end_sec: float
    projectors: frozenset[str]


def estimate_script_duration_sec(script_text: str, segments: list[AvatarTextSegment]) -> float:
    words = max(1, len(script_text.split()))
    from_words = words * 0.4
    from_segments = 0.0
    script_len = max(1, len(script_text))
    for segment in segments:
        offset = segment.char_offset or 0
        duration_ms = _segment_duration_ms(segment)
        start = (offset / script_len) * from_words
        from_segments = max(from_segments, start + duration_ms / 1000.0)
    return max(60.0, from_words, from_segments) + 15.0


def _segment_duration_ms(segment: AvatarTextSegment) -> int:
    duration_ms = 0
    for layer in segment.avatar_layers:
        visual = layer.visual_cue
        if visual and visual.duration_ms:
            duration_ms = max(duration_ms, visual.duration_ms)
    if duration_ms > 0:
        return duration_ms
    return estimate_duration_ms(segment.text_excerpt)


def build_avatar_windows(
    script_text: str,
    segments: list[AvatarTextSegment],
    total_sec: float,
) -> list[AvatarWindow]:
    script_len = max(1, len(script_text))
    windows: list[AvatarWindow] = []
    for segment in segments:
        offset = segment.char_offset or 0
        start = (offset / script_len) * total_sec
        end = start + _segment_duration_ms(segment) / 1000.0
        projectors: set[str] = set()
        for layer in segment.avatar_layers:
            if layer.projector:
                projectors.add(layer.projector)
            for output in layer.outputs or []:
                projectors.add(output.output_id)
        if projectors:
            windows.append(
                AvatarWindow(
                    start_sec=start,
                    end_sec=end,
                    projectors=frozenset(projectors),
                )
            )
    return windows


def reserved_projectors_at(windows: list[AvatarWindow], time_sec: float) -> set[str]:
    reserved: set[str] = set()
    for window in windows:
        if window.start_sec <= time_sec < window.end_sec:
            reserved |= set(window.projectors)
    return reserved


def free_projectors_at(windows: list[AvatarWindow], time_sec: float) -> list[str]:
    reserved = reserved_projectors_at(windows, time_sec)
    return [p for p in ALL_PROJECTORS if p not in reserved]


def _atmosphere_clip_pool(*, avatar_clip_ids: set[str]) -> list[str]:
    allowed = _clip_ids_for_scope("part1")
    return [clip_id for clip_id in sorted(allowed) if clip_id not in avatar_clip_ids]


def _assign_atmosphere_visual(clip_id: str, projector: str) -> VisualCue:
    return VisualCue(
        clip_id=clip_id,
        video_type="atmosphere",
        projector=projector,  # type: ignore[arg-type]
        blend_mode="layer",
        lock_until_finished=False,
        can_be_interrupted=True,
        outputs=[VisualOutputAssignment(output_id=projector, clip_id=clip_id)],
    )


def _parse_llm_cue_points(raw: str) -> list[CuePoint]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    points_raw = data.get("cue_points", data if isinstance(data, list) else [])
    return [CuePoint.model_validate(item) for item in points_raw]


def _validate_atmosphere_points(
    points: list[CuePoint],
    *,
    allowed_clips: set[str],
    allowed_projectors: set[str],
    max_time_sec: float,
) -> list[CuePoint]:
    validated: list[CuePoint] = []
    for point in points:
        if point.trigger != CuePointTrigger.TIME and str(point.trigger) != "time":
            continue
        if point.time_offset_sec < 0 or point.time_offset_sec > max_time_sec + 5:
            continue
        visual = point.visual
        if visual is None or not visual.clip_id:
            continue
        if visual.clip_id not in allowed_clips:
            continue
        projector = visual.projector
        if not projector and visual.outputs:
            projector = visual.outputs[0].output_id  # type: ignore[assignment]
        if projector not in allowed_projectors:
            continue
        validated.append(
            CuePoint(
                trigger=CuePointTrigger.TIME,
                time_offset_sec=round(point.time_offset_sec, 2),
                function=point.function or "atmosphaere",
                intensity=point.intensity,
                visual=_assign_atmosphere_visual(visual.clip_id, projector),  # type: ignore[arg-type]
            )
        )
    validated.sort(key=lambda item: item.time_offset_sec)
    return validated


def _rule_based_atmosphere_points(
    *,
    script_text: str,
    sentences: list[str],
    segments: list[AvatarTextSegment],
    curve: AnarchyCurve,
    avatar_clip_ids: set[str],
    dramaturgy: DramaturgyDecision,
) -> list[CuePoint]:
    """Fallback: derive time cues from sentence-based injection."""
    working = dramaturgy.model_copy(deep=True)
    if not working.cue_points:
        working.cue_points = [
            CuePoint(
                trigger=CuePointTrigger.SENTENCE_END,
                sentence_index=index,
                function="atmosphaere",
                intensity=0.5,
            )
            for index in range(len(sentences))
        ]
    injected = inject_atmosphere_visuals(
        working,
        sentences=sentences,
        segments=segments,
        curve=curve,
        avatar_clip_ids=avatar_clip_ids,
    )
    total_sec = estimate_script_duration_sec(script_text, segments)
    windows = build_avatar_windows(script_text, segments, total_sec)
    sentence_duration = total_sec / max(1, len(sentences))
    points: list[CuePoint] = []
    for point in injected.cue_points:
        if not point.visual or not point.visual.clip_id:
            continue
        index = point.sentence_index or 0
        time_sec = min(total_sec - 1.0, index * sentence_duration)
        projector = point.visual.projector
        if not projector and point.visual.outputs:
            projector = point.visual.outputs[0].output_id
        if not projector:
            free = free_projectors_at(windows, time_sec)
            if not free:
                continue
            projector = pick_atmosphere_projectors(1, reserved=set(ALL_PROJECTORS) - set(free), seed=index)[0]
        points.append(
            CuePoint(
                trigger=CuePointTrigger.TIME,
                time_offset_sec=round(time_sec, 2),
                function=point.function or "atmosphaere",
                intensity=point.intensity,
                visual=_assign_atmosphere_visual(point.visual.clip_id, projector),
            )
        )
    return points


def _timeline_summary(windows: list[AvatarWindow], total_sec: float) -> str:
    lines = [f"Gesamtdauer geschätzt: {total_sec:.0f}s"]
    for window in windows[:40]:
        proj = ", ".join(sorted(window.projectors))
        lines.append(f"  {window.start_sec:.1f}s–{window.end_sec:.1f}s: Avatar auf {proj}")
    if len(windows) > 40:
        lines.append(f"  … +{len(windows) - 40} weitere Avatar-Fenster")
    return "\n".join(lines)


class Teil2AtmosphereScheduler:
    def __init__(
        self,
        ai_service: AIService | None = None,
        llm_director: LLMDirector | None = None,
    ) -> None:
        self.ai = ai_service or AIService()
        self.llm = llm_director or LLMDirector(ai_service=self.ai)

    async def schedule(
        self,
        *,
        script_text: str,
        sentences: list[str],
        segments: list[AvatarTextSegment],
        gesamtkonzept: Gesamtkonzept,
        dramaturgy: DramaturgyDecision,
        avatar_clip_ids: set[str],
        openai_model: str = "gpt-4o",
    ) -> list[CuePoint]:
        total_sec = estimate_script_duration_sec(script_text, segments)
        windows = build_avatar_windows(script_text, segments, total_sec)
        allowed_clips = set(_atmosphere_clip_pool(avatar_clip_ids=avatar_clip_ids))
        if not allowed_clips:
            return []

        mid_anarchy = (gesamtkonzept.anarchy_curve.start + gesamtkonzept.anarchy_curve.end) / 2
        intervals = cue_intervals_for_anarchy(mid_anarchy)
        video_min, video_max = intervals["video"]

        if settings.teil2_atmosphere_use_llm and settings.director_dramaturgy_mode != "rules" and "openai" in self.ai.providers:
            try:
                llm_points = await self._schedule_llm(
                    script_text=script_text,
                    gesamtkonzept=gesamtkonzept,
                    windows=windows,
                    total_sec=total_sec,
                    allowed_clips=allowed_clips,
                    video_interval=(video_min, video_max),
                    openai_model=openai_model,
                )
                if llm_points:
                    return llm_points
            except Exception:
                pass

        return _rule_based_atmosphere_points(
            script_text=script_text,
            sentences=sentences,
            segments=segments,
            curve=gesamtkonzept.anarchy_curve,
            avatar_clip_ids=avatar_clip_ids,
            dramaturgy=dramaturgy,
        )

    async def _schedule_llm(
        self,
        *,
        script_text: str,
        gesamtkonzept: Gesamtkonzept,
        windows: list[AvatarWindow],
        total_sec: float,
        allowed_clips: set[str],
        video_interval: tuple[float, float],
        openai_model: str,
    ) -> list[CuePoint]:
        digest = script_text[:8000] + ("…" if len(script_text) > 8000 else "")
        timeline = _timeline_summary(windows, total_sec)
        clip_sample = sorted(allowed_clips)[:40]
        prompt = (
            f"Anarchie-Kurve: {gesamtkonzept.anarchy_curve.start} → {gesamtkonzept.anarchy_curve.end}\n"
            f"Geschätzte Dauer: {total_sec:.0f}s\n\n"
            f"Skript-Auszug:\n{digest}\n\n"
            f"Avatar-Belegung (reservierte Beamers):\n{timeline}\n\n"
            "Plane Atmosphären-Videos (OhneAvatare) auf FREIEN Beamern.\n"
            "KEIN Dialog. Stimmungsunabhängig — variiere Clips nach Zeit/Anarchie, nicht nach Text.\n"
            f"Rhythmus: alle {video_interval[0]:.0f}–{video_interval[1]:.0f}s ein neuer Clip.\n"
            f"Nur clip_id aus: {clip_sample}\n"
            f"Projektoren: rz21, adam, eva, led — nur freie zum jeweiligen time_offset_sec.\n"
            f"Gesamtdauer: {total_sec:.0f}s\n\n"
            'Antworte nur mit JSON: {"cue_points":[{"trigger":"time","time_offset_sec":12.0,'
            '"function":"atmosphaere","intensity":0.5,'
            '"visual":{"clip_id":"clyde","projector":"adam","video_type":"atmosphere"}}]}'
        )
        raw = await self.ai.generate(
            "openai",
            openai_model,
            [
                {
                    "role": "system",
                    "content": (
                        "Du planst B-Roll auf freien Projektoren. Kein Dialog. "
                        "Stimmungsunabhängig — Rhythmus und Anarchie, nicht Textinhalt. "
                        "Keine Avatar-Clips. Nur gültiges JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=settings.dramaturgy_decision_max_tokens,
        )
        parsed = _parse_llm_cue_points(raw)
        allowed_projectors = set(ALL_PROJECTORS)
        validated = _validate_atmosphere_points(
            parsed,
            allowed_clips=allowed_clips,
            allowed_projectors=allowed_projectors,
            max_time_sec=total_sec,
        )
        if len(validated) < 3:
            return []
        rerouted: list[CuePoint] = []
        for point in validated:
            free = free_projectors_at(windows, point.time_offset_sec)
            visual = point.visual
            if visual is None or not visual.clip_id:
                continue
            projector = visual.projector
            if projector not in free:
                if not free:
                    continue
                projector = pick_atmosphere_projectors(
                    1,
                    reserved=set(ALL_PROJECTORS) - set(free),
                    seed=int(point.time_offset_sec),
                )[0]
            rerouted.append(
                CuePoint(
                    trigger=CuePointTrigger.TIME,
                    time_offset_sec=point.time_offset_sec,
                    function=point.function,
                    intensity=point.intensity,
                    visual=_assign_atmosphere_visual(visual.clip_id, projector),  # type: ignore[arg-type]
                )
            )
        return rerouted


_scheduler: Teil2AtmosphereScheduler | None = None


def get_teil2_atmosphere_scheduler() -> Teil2AtmosphereScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Teil2AtmosphereScheduler()
    return _scheduler
