"""Tests for tools/qlab_import_video_cues.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "qlab_import_video_cues.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("qlab_import_video_cues", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_match_score_finds_german_filename_variants() -> None:
    module = _load_module()
    assert module._match_score("HierUnterDerErde", "Tier unter der Erde") >= 50
    assert module._match_score("MehlwuermerLangsam", "Mehlwürmer langsam") >= 50
    assert module._match_score("SturmFischskellet", "Sturm-Fischskelett") >= 50
    assert module._match_score("Branko", "BK6_Branko") >= 50


def test_applescript_uses_qlab_make_pattern() -> None:
    module = _load_module()
    script = module._build_applescript(
        "KI_RZ21.BAK2_Krabbe",
        "BAK2_Krabbe",
        Path("/tmp/BAK2_Krabbe.mp4"),
    )
    assert "make type \"video\"" in script
    assert "last item of (selected as list)" in script
    assert "at end of cues" not in script
