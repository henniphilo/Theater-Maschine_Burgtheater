"""Tests for OSC queue signal trace events."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.director.cues.cue_models import CommandTraceMeta, OscCommand
from app.director.outputs import osc_queue as osc_queue_mod
from app.director.outputs.osc_queue import get_osc_command_queue
from app.director.run_state import get_director_run_state


@pytest.fixture
def isolated_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    osc_queue_mod._queue = None
    monkeypatch.setattr(settings, "director_osc_queue", True)
    import app.director.pipeline as pipeline_mod
    import app.api.routes.director as director_routes

    pipeline_mod._pipeline = None
    director_routes._pipeline = pipeline_mod.get_director_pipeline()


def test_queue_trace_events_on_send_failure(isolated_queue: None, tmp_path: Path) -> None:
    trace_path = Path(settings.signal_trace_path)
    current = get_director_run_state().current()

    queue = get_osc_command_queue()
    cmd = OscCommand(
        bridge="pixera",
        host="127.0.0.1",
        port=8990,
        address="/pixera/args/cue/apply",
        args=["Fail"],
        dry_run=False,
        trace=CommandTraceMeta(
            logical_signal_id="sig-test01",
            command_id="cmd-test01-01",
            run_id=current.run_id,
            run_epoch=current.run_epoch,
            http_request_id="req-test01",
        ),
    )
    with patch(
        "app.director.outputs.osc_queue.send_osc_commands",
        side_effect=RuntimeError("bridge down"),
    ):
        queue.enqueue([cmd], stagger=False, bridges={}, wait=True, timeout=2.0)

    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_names = [e["event"] for e in events]
    assert "queue.enqueued" in event_names
    assert "queue.dequeued" in event_names
    assert "command.send_attempted" in event_names
    assert "command.send_failed" in event_names


def test_api_response_can_precede_send_completed(isolated_queue: None, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from app.director.cues.cue_models import DramaturgyDecision, SoundAction, SoundCue
    from app.main import app

    sent_at: list[float] = []

    def slow_send(
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict,
    ) -> list[OscCommand]:
        import time

        from app.director.outputs.signal_trace import log_command_send_lifecycle

        time.sleep(0.15)
        sent_at.append(time.monotonic())
        for cmd in commands:
            log_command_send_lifecycle(cmd, failed=False)
        return commands

    client = TestClient(app)
    decision = DramaturgyDecision(
        sound=SoundCue(action=SoundAction.TRIGGER_CUE, cue_id="maschinen_grundader", volume=0.5),
        reason="queue ordering",
    )
    with patch("app.director.outputs.osc_queue.send_osc_batch", side_effect=slow_send):
        response = client.post(
            "/api/v1/director/execute",
            json={"decision": decision.model_dump(), "force": True, "stagger": False},
        )
        assert response.status_code == 200
        get_osc_command_queue().flush(timeout=2.0)

    trace_path = Path(settings.signal_trace_path)
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    api_ts = next(e["ts_mono_ms"] for e in events if e["event"] == "api.response_executed")
    completed_ts = [
        e["ts_mono_ms"]
        for e in events
        if e["event"] in {"command.send_completed", "command.dry_run_suppressed_send"}
    ]
    assert completed_ts
    assert api_ts <= min(completed_ts)
