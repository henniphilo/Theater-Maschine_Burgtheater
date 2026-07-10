"""Tests for signal trace writer and schema."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from app.director.outputs.signal_trace import (
    SCHEMA_VERSION,
    SignalTraceWriter,
    attach_command_traces,
    begin_request_trace,
    emit_signal_trace_event,
    new_command_id,
    new_http_request_id,
    new_logical_signal_id,
    reset_run_state_for_tests,
)
from app.director.cues.cue_models import OscCommand
from app.schemas.director import TraceContext


@pytest.fixture
def trace_file(tmp_path: Path) -> Path:
    path = tmp_path / "signal_trace.jsonl"
    SignalTraceWriter.reset_for_tests(path)
    reset_run_state_for_tests()
    return path


def test_id_formats() -> None:
    assert new_http_request_id().startswith("req-")
    assert new_logical_signal_id().startswith("sig-")
    sig = new_logical_signal_id()
    assert new_command_id(sig, 1).startswith("cmd-")


def test_writer_emits_valid_jsonl(trace_file: Path) -> None:
    req = begin_request_trace(TraceContext(frontend_run_id="fe-run-1", frontend_generation=3))
    emit_signal_trace_event("signal.planned", status="planned", request_trace=req, planned_command_count=1)

    lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["event"] == "signal.planned"
    assert payload["status"] == "planned"
    assert payload["http_request_id"] == req.http_request_id
    assert payload["logical_signal_id"] == req.logical_signal_id
    assert payload["frontend_run_id"] == "fe-run-1"
    assert payload["frontend_generation"] == 3
    assert "ts_wall" in payload
    assert "ts_mono_ms" in payload


def test_attach_command_traces_assigns_ids(trace_file: Path) -> None:
    req = begin_request_trace(None)
    cmd = OscCommand(
        bridge="pixera",
        host="127.0.0.1",
        port=8990,
        address="/pixera/args/cue/apply",
        args=["Test"],
        dry_run=True,
    )
    traced = attach_command_traces([cmd], req)
    assert traced[0].trace is not None
    assert traced[0].trace.logical_signal_id == req.logical_signal_id
    assert traced[0].trace.command_id.endswith("-01")


def test_writer_thread_safe(trace_file: Path) -> None:
    def worker() -> None:
        for _ in range(20):
            emit_signal_trace_event("command.built", status="built", bridge="pixera")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = [line for line in trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 80
