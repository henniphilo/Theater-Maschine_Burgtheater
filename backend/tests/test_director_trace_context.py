"""Tests for director execute trace context propagation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.director.cues.cue_models import DramaturgyDecision, LightCue, SoundAction, SoundCue, VisualAction, VisualCue
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_execute_emits_trace_ids(client: TestClient, tmp_path: Path) -> None:
    trace_path = Path(settings.signal_trace_path)
    decision = DramaturgyDecision(
        visual=VisualCue(action=VisualAction.PLAY_CLIP, clip_id="clyde", opacity=0.8),
        sound=SoundCue(action=SoundAction.TRIGGER_CUE, cue_id="maschinen_grundader", volume=0.5),
        light=LightCue(scene_id="vorbuehnenzug"),
        reason="trace test",
    )
    response = client.post(
        "/api/v1/director/execute",
        json={
            "decision": decision.model_dump(),
            "force": True,
            "stagger": False,
            "trace": {
                "frontend_run_id": "fe-run-test",
                "frontend_generation": 7,
                "source": "test",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["executed"] is True
    assert body["osc_commands"]
    assert all(cmd.get("trace", {}).get("command_id") for cmd in body["osc_commands"])

    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_names = {e["event"] for e in events}
    assert "director.execute_received" in event_names
    assert "signal.planned" in event_names
    assert "command.built" in event_names
    assert "api.response_executed" in event_names
    assert any(e.get("frontend_run_id") == "fe-run-test" for e in events)


def test_missing_frontend_context_marked_backend_generated(client: TestClient, tmp_path: Path) -> None:
    trace_path = Path(settings.signal_trace_path)
    decision = DramaturgyDecision(
        sound=SoundCue(action=SoundAction.TRIGGER_CUE, cue_id="maschinen_grundader", volume=0.5),
        reason="no frontend",
    )
    response = client.post(
        "/api/v1/director/execute",
        json={"decision": decision.model_dump(), "force": True, "stagger": False},
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(e.get("context_source") == "backend_generated" for e in events)
