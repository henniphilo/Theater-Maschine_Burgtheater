from pathlib import Path

from app.services.avatar_speech_catalog import (
    match_avatar_cues,
    normalize_avatar_text,
    parse_avatar_csv,
)

FIXTURE_CSV = Path(__file__).resolve().parent / "fixtures" / "avatar_textzuordnung.csv"


def _avatar_csv_path() -> Path:
    assert FIXTURE_CSV.is_file()
    return FIXTURE_CSV


def test_avatar_csv_loads_delphin_and_baerenklau_clips() -> None:
    catalog = parse_avatar_csv(_avatar_csv_path())
    assert len(catalog.cues) >= 40
    nicolas = next(c for c in catalog.cues if c.id == "nicolas")
    assert nicolas.avatar == "delphin"
    assert nicolas.video_clip_id == "nicolas"
    bk = next(c for c in catalog.cues if c.id == "bk1_caro")
    assert bk.avatar == "baerenklau"
    assert bk.video_clip_id == "bk1_caro"


def test_chorus_rows_share_text_in_catalog() -> None:
    catalog = parse_avatar_csv(_avatar_csv_path())
    caro = next(c for c in catalog.cues if c.id == "bk1_caro")
    caroline = next(c for c in catalog.cues if c.id == "bk1_caroline")
    assert caro.text == caroline.text


def test_normalize_avatar_text_strips_control_chars() -> None:
    assert "_x000B_" not in normalize_avatar_text("Geld_x000B_könnte")


def test_match_avatar_cues_finds_overlap() -> None:
    from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service

    catalog = get_avatar_speech_catalog_service().load()
    cue = next(c for c in catalog.cues if len(c.text) >= 80)
    matches = match_avatar_cues(cue.text[:80])
    assert any(m.id == cue.id for m in matches)
