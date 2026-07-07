"""Tests für visualize_show_logs Parser."""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from visualize_show_logs import (  # noqa: E402
    load_sound_note_labels,
    parse_director_log,
    parse_osc_log,
)


def test_parse_osc_log_pixera_beamer_and_light(tmp_path: Path) -> None:
    log = tmp_path / "osc.log"
    log.write_text(
        "\n".join(
            [
                "[OSC DRY-RUN +1.000s] [pixera] → 172.27.27.1:8990 /pixera/args/cue/apply 'KI_Adam.Clyde'",
                "[OSC DRY-RUN +1.200s] [pixera] → 172.27.27.1:8990 /pixera/args/cue/apply 'KI_RZ21.BK1_Caro'",
                "[OSC DRY-RUN +2.000s] [light] → 10.101.90.112:3032 tcp/osc binary /eos/chan/22 0.0",
                "[OSC DRY-RUN +2.100s] [light] → 10.101.90.112:3032 tcp/osc binary /eos/chan/22 79.0",
                "[MIDI DRY-RUN] [sound] → IAC-Treiber Bus 1 note_on ch=1 note=36 vel=87",
            ]
        ),
        encoding="utf-8",
    )
    result = parse_osc_log(log, note_labels={36: "maschinen_grundader"})
    lanes = {e.lane for e in result.events}
    assert "video:adam" in lanes
    assert "video:rz21" in lanes
    assert "sound" in lanes
    assert "light" in lanes
    adam = next(e for e in result.events if e.lane == "video:adam")
    assert adam.label == "Clyde"
    sound = next(e for e in result.events if e.lane == "sound")
    assert sound.label == "maschinen_grundader"


def test_parse_director_log_decisions(tmp_path: Path) -> None:
    log = tmp_path / "director.log"
    log.write_text(
        json_line(
            {
                "logged_at": "2026-06-29T20:00:00+00:00",
                "executed": True,
                "blocked_reason": None,
                "decision": {
                    "visual": {"clip_id": "bak1_caro", "projector": "rz21"},
                    "sound": {"cue_id": "maschinen_grundader"},
                    "light": {"scene_id": "vorbuehnenzug"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events = parse_director_log(log)
    assert len(events) == 3
    assert any(e.lane == "video:rz21" for e in events)


def json_line(obj: dict) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


def test_load_sound_note_labels() -> None:
    labels = load_sound_note_labels()
    assert isinstance(labels, dict)
