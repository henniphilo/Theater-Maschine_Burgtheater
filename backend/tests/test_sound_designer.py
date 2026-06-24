from datetime import UTC, datetime

from app.director.cues.cue_models import CuePointTrigger
from app.schemas.part1_selection import Part1BaerenklauSelection
from app.schemas.script import ScriptBeat
from app.services.sound_designer import (
    SoundCatalogIndex,
    SoundDesignPlanner,
    SoundMixState,
    assign_sounds_to_sentences,
    dramaturgy_with_sound_design,
    sound_family,
)
from app.services.sound_cue_catalog import get_sound_cue_catalog_service


def test_sound_family_strips_suffixes() -> None:
    assert sound_family("maschinen_grundader_fade_in") == "maschinen_grundader"
    assert sound_family("kaefigecho") == "kaefigecho"


def test_catalog_resolve_fade_variants() -> None:
    index = SoundCatalogIndex.from_catalog(get_sound_cue_catalog_service().load())
    assert index.resolve("maschinen_grundader", "fade_in") == "maschinen_grundader_fade_in"
    assert index.resolve("maschinen_grundader", "play") == "maschinen_grundader"
    assert index.resolve("alle_sounds", "cut_all") == "alle_sounds_cut"


def test_planner_fade_in_bed_then_layer_accent() -> None:
    catalog = get_sound_cue_catalog_service().load()
    index = SoundCatalogIndex.from_catalog(catalog)
    planner = SoundDesignPlanner(index=index, music_ids=[], sound_ids=["maschinen_grundader", "erinnerungsglitch"])
    state = SoundMixState()

    _, first = planner.plan_for_moment(
        state,
        "maschinen_grundader",
        sentence="Die Maschine summt im Keller.",
        moment_index=0,
        moment_count=3,
        intensity=0.4,
    )
    assert first
    assert first[0].cue_id == "maschinen_grundader_fade_in"
    assert "maschinen_grundader" in state.active_beds

    _, accent = planner.plan_for_moment(
        state,
        "erinnerungsglitch",
        sentence="Ein Glitch durchbricht die Erinnerung.",
        moment_index=1,
        moment_count=3,
        intensity=0.6,
    )
    assert accent
    assert accent[0].cue_id == "erinnerungsglitch"


def test_planner_silence_triggers_cut() -> None:
    catalog = get_sound_cue_catalog_service().load()
    index = SoundCatalogIndex.from_catalog(catalog)
    planner = SoundDesignPlanner(index=index, music_ids=[], sound_ids=["maschinen_grundader"])
    state = SoundMixState()
    state.active_beds.append("maschinen_grundader")

    _, main = planner.plan_for_moment(
        state,
        "maschinen_grundader",
        sentence="Dann herrscht plötzlich Stille im Raum.",
        moment_index=1,
        moment_count=2,
        intensity=0.5,
    )
    assert main
    assert main[0].cue_id == "alle_sounds_cut"
    assert state.active_beds == []


def test_dramaturgy_uses_fade_in_not_raw_play_for_beds() -> None:
    beat = ScriptBeat(
        id="b1",
        order=0,
        text="Die Maschine arbeitet. Ein Echo hallt nach.",
        speaker="AI_A",
    )
    selection = Part1BaerenklauSelection(
        script_id="s1",
        beat_id="b1",
        final_sounds=["maschinen_grundader", "kaefigecho", "erinnerungsglitch", "herz_unter_glas", "stallluft_digital", "puls_schritt"],
        final_music=["maschinen_grundader"],
        final_videos=["clyde", "bonnie", "inge", "odyssee", "hundethiel", "black"],
        final_lights=["blendung_zuschauerraum", "teppich_rot", "buehne_kalt_hart", "blendung_magenta", "seitenlicht_hart", "buehne_kalt_hart"],
        created_at=datetime.now(UTC),
    )
    decision = dramaturgy_with_sound_design(selection, beat)
    sound_ids = [p.sound.cue_id for p in decision.cue_points if p.sound and p.sound.cue_id]
    assert "maschinen_grundader_fade_in" in sound_ids
    assert any(p.trigger == CuePointTrigger.START for p in decision.cue_points)


def test_assign_sounds_prefers_text_match() -> None:
    index = SoundCatalogIndex.from_catalog(get_sound_cue_catalog_service().load())
    sentences = ["Das Herz schlägt unter Glas.", "Die Maschine dröhnt."]
    assigned = assign_sounds_to_sentences(sentences, ["herz_unter_glas", "maschinen_grundader"], index)
    assert assigned[0] == "herz_unter_glas"
    assert assigned[1] == "maschinen_grundader"
