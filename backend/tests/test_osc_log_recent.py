from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes.director import _read_osc_log_tail
from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_read_osc_log_tail_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "osc_log_path", str(tmp_path / "missing.log"))
    assert _read_osc_log_tail(10) == []


def test_read_osc_log_tail_returns_last_lines(tmp_path, monkeypatch):
    log_path = tmp_path / "osc.log"
    log_path.write_text(
        "\n".join(
            [
                "[OSC SEND +1.000s] [pixera] → 127.0.0.1:8990 /a",
                "[MIDI DRY-RUN] [sound] → IAC note_on ch=1 note=36",
                "[OSC SEND +2.000s] [pixera] → 127.0.0.1:8990 /b",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "osc_log_path", str(log_path))
    lines = _read_osc_log_tail(2)
    assert len(lines) == 2
    assert "note_on" in lines[0]
    assert lines[1].endswith("/b")


def test_osc_log_recent_endpoint(tmp_path, monkeypatch):
    log_path = tmp_path / "osc.log"
    log_path.write_text("[OSC SEND +0.1s] [pixera] → 127.0.0.1:8990 /cue\n", encoding="utf-8")
    monkeypatch.setattr(settings, "osc_log_path", str(log_path))
    monkeypatch.setattr(settings, "director_enabled", True)
    res = client.get("/api/v1/director/osc-log/recent?limit=20")
    assert res.status_code == 200
    body = res.json()
    assert body["lines"] == ["[OSC SEND +0.1s] [pixera] → 127.0.0.1:8990 /cue"]
    assert Path(body["path"]).name == "osc.log"
