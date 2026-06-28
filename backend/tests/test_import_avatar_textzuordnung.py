"""Tests for Numbers «Zeit» duration import."""

from __future__ import annotations

from datetime import datetime

from app.services.avatar_duration import normalize_duration_ms, parse_zeit_duration_ms
from scripts.import_avatar_textzuordnung import parse_zeit_duration_ms as import_parse_zeit


def test_parse_zeit_duration_ms_seven_seconds():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 7, 0)) == 7_000


def test_parse_zeit_duration_ms_one_minute_thirty_seconds():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 1, 30)) == 90_000


def test_import_script_uses_same_parse():
    assert import_parse_zeit(datetime(1900, 1, 1, 0, 7, 0)) == 7_000


def test_normalize_legacy_csv_duration():
    assert normalize_duration_ms(420_000) == 7_000
    assert normalize_duration_ms(540_000) == 9_000
    assert normalize_duration_ms(90_000) == 90_000


def test_parse_zeit_duration_ms_rejects_non_datetime():
    assert parse_zeit_duration_ms("not-a-duration") is None
    assert parse_zeit_duration_ms(None) is None


def test_parse_zeit_duration_ms_numbers_text_format():
    assert parse_zeit_duration_ms("00:24 Sek") == 24_000
    assert parse_zeit_duration_ms("00:07 Sek") == 7_000
    assert import_parse_zeit("00:07 Sek") == 7_000


def test_parse_zeit_duration_ms_zero_is_none():
    assert parse_zeit_duration_ms(datetime(1900, 1, 1, 0, 0, 0)) is None
