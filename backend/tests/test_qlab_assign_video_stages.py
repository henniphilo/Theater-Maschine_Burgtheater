"""Tests for tools/qlab_assign_video_stages.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "qlab_assign_video_stages.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("qlab_assign_video_stages", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_for_cue_number_mapping() -> None:
    module = _load_module()
    assert module.stage_for_cue_number("KI_RZ21.BAK2_Krabbe") == 1
    assert module.stage_for_cue_number("KI_Adam.Clyde") == 2
    assert module.stage_for_cue_number("KI_Eva.Inge") == 3
    assert module.stage_for_cue_number("KI_LED.Wasserfahrt") == 4
    assert module.stage_for_cue_number("other") is None


def test_applescript_contains_stage_number_assignment() -> None:
    module = _load_module()
    script = module._build_applescript()
    assert "set stage number of c to 1" in script
    assert "set stage number of c to 4" in script
    assert "KI_Adam." in script
