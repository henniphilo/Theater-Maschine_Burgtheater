"""Tests for atmosphere video Numbers import."""

from __future__ import annotations

from datetime import datetime

from scripts.import_video_zuordnung import (
    numbers_clip_to_pixera,
    parse_numbers_sheet_duration_ms,
    slug_id,
)


def test_numbers_clip_to_pixera_atmosphere_names() -> None:
    assert numbers_clip_to_pixera("Bitcoinfahrt") == "Bitcoinfahrt"
    assert numbers_clip_to_pixera("Affen Slow_Odysee 2001") == "AffenSlowOdysee"
    assert numbers_clip_to_pixera("Tier unter der Erde") == "TierUnterDerErde"


def test_slug_id_from_pixera() -> None:
    assert slug_id("FischUndWassergewaechs") == "fischundwassergewaechs"


def test_parse_numbers_sheet_duration_mm_ss() -> None:
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 0, 22, 0)) == 22_000
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 1, 33, 0)) == 93_000
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 3, 16, 0)) == 196_000
    assert parse_numbers_sheet_duration_ms(datetime(2026, 6, 29, 18, 40, 0)) == 1_120_000
