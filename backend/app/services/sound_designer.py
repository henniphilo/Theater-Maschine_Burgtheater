"""Intelligent sound mixing for Teil 1 — dramaturg repertoire, professional layering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.director.cues.cue_models import CuePoint, CuePointTrigger, DramaturgyDecision, LightCue, SoundCue, VisualCue
from app.schemas.part1_selection import Part1BaerenklauSelection
from app.schemas.script import ScriptBeat
from app.schemas.sound_cues import SoundCueCatalog, SoundCueEntry
from app.services.script_splitter import split_sentences
from app.services.sound_cue_catalog import get_sound_cue_catalog_service

BED_TAGS = frozenset({"drone", "grundton", "dauer", "ambient", "atmo", "musik", "music", "pad"})
ACCENT_TAGS = frozenset({"stinger", "glitch", "hit", "akkzent", "einmalig", "impuls", "cut", "knack"})
SILENCE_KEYWORDS = frozenset({"stille", "schweigen", "verstumm", "ruhe", "schweigt", "lauscht"})


def sound_family(play_cue_id: str) -> str:
    return (
        play_cue_id.removesuffix("_fade_in")
        .removesuffix("_fade_out")
        .removesuffix("_out")
        .strip()
    )


@dataclass
class SoundMixState:
    music_family: str | None = None
    active_beds: list[str] = field(default_factory=list)
    active_accents: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SoundCatalogIndex:
    play_ids: frozenset[str]
    by_id: dict[str, SoundCueEntry]
    by_family: dict[str, SoundCueEntry]

    @classmethod
    def from_catalog(cls, catalog: SoundCueCatalog) -> SoundCatalogIndex:
        by_id = {c.id: c for c in catalog.cues}
        by_family: dict[str, SoundCueEntry] = {}
        for cue in catalog.cues:
            if cue.action == "play":
                by_family[sound_family(cue.id)] = cue
        return cls(play_ids=frozenset(by_family.keys()), by_id=by_id, by_family=by_family)

    def resolve(self, family: str, action: str) -> str | None:
        if action == "cut_all":
            return "alle_sounds_cut" if "alle_sounds_cut" in self.by_id else None
        if action == "play":
            return family if family in self.play_ids else None
        candidate = f"{family}_{action}"
        if candidate in self.by_id:
            return candidate
        if action == "out":
            candidate = f"{family}_out"
            return candidate if candidate in self.by_id else None
        return None

    def meta(self, play_cue_id: str) -> SoundCueEntry | None:
        return self.by_family.get(sound_family(play_cue_id))


def _is_music(entry: SoundCueEntry) -> bool:
    tags = {t.lower() for t in entry.tags}
    return bool(tags & {"musik", "music"})


def _is_bed(entry: SoundCueEntry) -> bool:
    tags = {t.lower() for t in entry.tags}
    return bool(tags & BED_TAGS) or entry.action == "fade_in"


def _is_accent(entry: SoundCueEntry) -> bool:
    tags = {t.lower() for t in entry.tags}
    return bool(tags & ACCENT_TAGS)


def _sentence_needs_silence(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(word in lowered for word in SILENCE_KEYWORDS)


def _score_sound_for_sentence(entry: SoundCueEntry, sentence: str) -> float:
    lowered = sentence.lower()
    score = 0.0
    for tag in entry.tags:
        if tag.lower() in lowered:
            score += 2.0
    for mood in entry.moods:
        if mood.lower() in lowered:
            score += 1.0
    for token in re.findall(r"[a-zäöüß]{4,}", entry.description.lower()):
        if token in lowered:
            score += 0.5
    for token in re.findall(r"[a-zäöüß]{4,}", (entry.soundname or entry.label).lower()):
        if token in lowered:
            score += 0.75
    return score


def assign_sounds_to_sentences(
    sentences: list[str],
    sound_ids: list[str],
    index: SoundCatalogIndex,
) -> list[str]:
    if not sentences:
        return []
    if not sound_ids:
        return [""] * len(sentences)

    used: set[str] = set()
    assignments: list[str] = []
    for sentence_index, sentence in enumerate(sentences):
        ranked = sorted(
            sound_ids,
            key=lambda sid: _score_sound_for_sentence(index.meta(sid) or SoundCueEntry(id=sid, midi_note=0), sentence),
            reverse=True,
        )
        chosen = ranked[0]
        for candidate in ranked:
            if candidate not in used or sentence_index >= len(sound_ids):
                chosen = candidate
                break
        used.add(chosen)
        assignments.append(chosen)
    return assignments


@dataclass
class SoundDesignPlanner:
    index: SoundCatalogIndex
    music_ids: list[str]
    sound_ids: list[str]

    def _cue(self, family: str, action: str, *, volume: float) -> SoundCue | None:
        cue_id = self.index.resolve(family, action)
        if cue_id is None:
            return None
        return SoundCue(cue_id=cue_id, volume=round(volume, 2))

    def start_music(self, state: SoundMixState) -> list[SoundCue]:
        if not self.music_ids:
            return []
        family = sound_family(self.music_ids[0])
        cue = self._cue(family, "fade_in", volume=0.45)
        if cue is None:
            cue = self._cue(family, "play", volume=0.45)
        if cue is None:
            return []
        state.music_family = family
        if family not in state.active_beds:
            state.active_beds.append(family)
        return [cue]

    def plan_for_moment(
        self,
        state: SoundMixState,
        play_cue_id: str,
        *,
        sentence: str,
        moment_index: int,
        moment_count: int,
        intensity: float,
    ) -> tuple[list[SoundCue], list[SoundCue]]:
        """Return (pre_ops, main_ops) — pre fade-outs, then play/fade-in/layer."""
        pre: list[SoundCue] = []
        main: list[SoundCue] = []
        entry = self.index.meta(play_cue_id)
        if entry is None:
            return pre, main

        family = sound_family(play_cue_id)
        volume = round(0.45 + intensity * 0.35, 2)

        if _sentence_needs_silence(sentence):
            cut = self._cue("alle_sounds", "cut_all", volume=0.0)
            if cut:
                main.append(cut)
            state.active_beds.clear()
            state.active_accents.clear()
            state.music_family = None
            return pre, main

        if moment_index == moment_count - 1 and moment_count > 2:
            for bed in list(state.active_beds):
                fade = self._cue(bed, "fade_out", volume=0.0)
                if fade:
                    pre.append(fade)
            state.active_beds.clear()
            state.active_accents.clear()

        if _is_music(entry):
            if state.music_family and state.music_family != family:
                fade = self._cue(state.music_family, "fade_out", volume=0.0)
                if fade:
                    pre.append(fade)
            cue = self._cue(family, "fade_in", volume=volume) or self._cue(family, "play", volume=volume)
            if cue:
                main.append(cue)
                state.music_family = family
                if family not in state.active_beds:
                    state.active_beds.append(family)
            return pre, main

        if _is_accent(entry):
            cue = self._cue(family, "play", volume=min(1.0, volume + 0.15))
            if cue:
                main.append(cue)
                if family not in state.active_accents:
                    state.active_accents.append(family)
            return pre, main

        if _is_bed(entry):
            for bed in list(state.active_beds):
                if bed == family:
                    continue
                bed_entry = self.index.meta(bed)
                if bed_entry and (_is_bed(bed_entry) or _is_music(bed_entry)):
                    fade = self._cue(bed, "fade_out", volume=0.0)
                    if fade:
                        pre.append(fade)
                    state.active_beds.remove(bed)
            cue = self._cue(family, "fade_in", volume=volume)
            if cue is None:
                cue = self._cue(family, "play", volume=volume)
            if cue:
                main.append(cue)
                state.active_beds.append(family)
            return pre, main

        if family in state.active_beds or family in state.active_accents:
            return pre, main

        cue = self._cue(family, "play", volume=volume)
        if cue:
            main.append(cue)
            state.active_accents.append(family)
        return pre, main


def _sound_point(
    sound: SoundCue,
    *,
    trigger: CuePointTrigger,
    sentence_index: int | None,
    function: str,
    intensity: float,
) -> CuePoint:
    return CuePoint(
        trigger=trigger,
        sentence_index=sentence_index,
        function=function,
        intensity=intensity,
        sound=sound,
    )


def dramaturgy_with_sound_design(
    selection: Part1BaerenklauSelection,
    beat: ScriptBeat,
) -> DramaturgyDecision:
    catalog = get_sound_cue_catalog_service().load()
    index = SoundCatalogIndex.from_catalog(catalog)
    sentences = split_sentences(beat.text) or [beat.text.strip()]
    sound_assignments = assign_sounds_to_sentences(sentences, selection.final_sounds, index)
    planner = SoundDesignPlanner(
        index=index,
        music_ids=list(selection.final_music),
        sound_ids=list(selection.final_sounds),
    )
    state = SoundMixState()
    points: list[CuePoint] = []

    for music_cue in planner.start_music(state):
        points.append(
            _sound_point(
                music_cue,
                trigger=CuePointTrigger.START,
                sentence_index=None,
                function="sounddesign_musik_ein",
                intensity=0.35,
            )
        )

    moment_count = len(sentences)
    for moment_index, sentence in enumerate(sentences):
        play_id = sound_assignments[moment_index]
        if not play_id:
            continue
        intensity = 0.2 + (moment_index / max(1, moment_count - 1)) * 0.55
        video_id = selection.final_videos[moment_index % len(selection.final_videos)]
        light_id = selection.final_lights[moment_index % len(selection.final_lights)]
        trigger = CuePointTrigger.START if moment_index == 0 else CuePointTrigger.SENTENCE_END
        sentence_index = None if moment_index == 0 else moment_index

        pre_ops, main_ops = planner.plan_for_moment(
            state,
            play_id,
            sentence=sentence,
            moment_index=moment_index,
            moment_count=moment_count,
            intensity=intensity,
        )
        for op in pre_ops:
            points.append(
                _sound_point(
                    op,
                    trigger=trigger,
                    sentence_index=sentence_index,
                    function="sounddesign_ausblenden",
                    intensity=intensity,
                )
            )
        primary_sound = main_ops[0] if main_ops else None
        for extra in main_ops[1:]:
            points.append(
                _sound_point(
                    extra,
                    trigger=trigger,
                    sentence_index=sentence_index,
                    function="sounddesign_layer",
                    intensity=intensity,
                )
            )
        if primary_sound or video_id or light_id:
            points.append(
                CuePoint(
                    trigger=trigger,
                    sentence_index=sentence_index,
                    function="verstärken",
                    intensity=intensity,
                    visual=VisualCue(clip_id=video_id, blend_mode="replace"),
                    sound=primary_sound,
                    light=LightCue(scene_id=light_id, intensity=round(0.35 + intensity * 0.45, 2)),
                )
            )

    if not points:
        points.append(
            CuePoint(
                trigger=CuePointTrigger.START,
                function="verstärken",
                intensity=0.4,
                sound=SoundCue(cue_id=selection.final_sounds[0], volume=0.55) if selection.final_sounds else None,
                visual=VisualCue(clip_id=selection.final_videos[0], blend_mode="replace") if selection.final_videos else None,
                light=LightCue(scene_id=selection.final_lights[0], intensity=0.5) if selection.final_lights else None,
            )
        )

    return DramaturgyDecision(
        reason=selection.dramaturgical_reading or selection.cue_strategy,
        dramaturgical_reading=selection.dramaturgical_reading,
        cue_points=points,
        intensity=0.25,
        mood="kontrolliert",
    )
