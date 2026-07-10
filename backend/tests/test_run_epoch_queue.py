"""Phase 5: stale run/epoch commands are dropped before transport send."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.director.cues.cue_models import CommandTraceMeta, OscCommand
from app.director.outputs.osc_queue import send_osc_batch
from app.director.run_state import get_director_run_state


def _command_for_current_epoch() -> OscCommand:
    current = get_director_run_state().current()
    return OscCommand(
        bridge="pixera",
        host="127.0.0.1",
        port=8990,
        address="/pixera/args/cue/apply",
        args=["Stale"],
        dry_run=False,
        trace=CommandTraceMeta(
            logical_signal_id="sig-stale01",
            command_id="cmd-stale01-01",
            run_id=current.run_id,
            run_epoch=current.run_epoch,
            http_request_id="req-stale01",
        ),
    )


def test_sync_send_drops_stale_epoch_before_transport(tmp_path: Path) -> None:
    trace_path = Path(settings.signal_trace_path)
    cmd = _command_for_current_epoch()
    get_director_run_state().create_barrier("test_stop")

    with patch("app.director.outputs.osc_queue.send_osc_commands") as send:
        sent = send_osc_batch([cmd], stagger=False, bridges={})

    assert sent == []
    send.assert_not_called()
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(e["event"] == "queue.stale_dropped" and e["command_id"] == "cmd-stale01-01" for e in events)


def test_status_exposes_authoritative_run_context() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    before = client.get("/api/v1/director/status").json()
    response = client.post("/api/v1/director/emergency-stop")
    assert response.status_code == 200
    after = response.json()

    assert after["run_id"] == before["run_id"]
    assert after["run_epoch"] == before["run_epoch"] + 1
