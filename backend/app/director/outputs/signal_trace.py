"""Structured signal trace writer for dropped-signal debugging."""

from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.director.cues.cue_models import CommandTraceMeta, OscCommand
from app.director.run_state import get_director_run_state
from app.schemas.director import TraceContext

SCHEMA_VERSION = 1

_id_lock = threading.Lock()
_run_lock = threading.Lock()
_write_lock = threading.Lock()

_run_id: str | None = None
_run_epoch: int = 0


@dataclass(frozen=True)
class RequestTrace:
    http_request_id: str
    logical_signal_id: str
    run_id: str
    run_epoch: int
    context_source: str
    frontend_run_id: str | None = None
    frontend_generation: int | None = None
    source: str | None = None
    trigger: str | None = None
    cue_point_key: str | None = None
    segment_key: str | None = None
    frontend_route: str | None = None


def effective_signal_trace_enabled() -> bool:
    if settings.signal_trace_enabled is not None:
        return settings.signal_trace_enabled
    return settings.app_env == "dev"


def _hex_id(prefix: str, nbytes: int = 3) -> str:
    return f"{prefix}-{secrets.token_hex(nbytes)}"


def new_http_request_id() -> str:
    return _hex_id("req")


def new_logical_signal_id() -> str:
    return _hex_id("sig")


def new_command_id(logical_signal_id: str, seq: int) -> str:
    suffix = logical_signal_id.removeprefix("sig-")
    return f"cmd-{suffix}-{seq:02d}"


def new_queue_batch_id() -> str:
    return _hex_id("batch")


def new_receiver_event_id() -> str:
    return _hex_id("rx")


def new_barrier_id() -> str:
    return _hex_id("barrier")


def new_run_id() -> str:
    now = datetime.now(UTC)
    return f"run-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


def _resolve_run_context(trace: TraceContext | None) -> tuple[str, int, str]:
    current = get_director_run_state().current()
    if trace and trace.frontend_run_id:
        return current.run_id, current.run_epoch, "frontend"
    return current.run_id, current.run_epoch, "backend_generated"


def begin_request_trace(
    trace: TraceContext | None,
    *,
    http_request_id: str | None = None,
) -> RequestTrace:
    run_id, run_epoch, context_source = _resolve_run_context(trace)
    return RequestTrace(
        http_request_id=http_request_id or new_http_request_id(),
        logical_signal_id=new_logical_signal_id(),
        run_id=run_id,
        run_epoch=run_epoch,
        context_source=context_source,
        frontend_run_id=trace.frontend_run_id if trace else None,
        frontend_generation=trace.frontend_generation if trace else None,
        source=trace.source if trace else None,
        trigger=trace.trigger if trace else None,
        cue_point_key=trace.cue_point_key if trace else None,
        segment_key=trace.segment_key if trace else None,
        frontend_route=trace.frontend_route if trace else None,
    )


def request_trace_base_fields(request_trace: RequestTrace | None) -> dict[str, Any]:
    if request_trace is None:
        return {}
    fields: dict[str, Any] = {
        "http_request_id": request_trace.http_request_id,
        "logical_signal_id": request_trace.logical_signal_id,
        "run_id": request_trace.run_id,
        "run_epoch": request_trace.run_epoch,
        "context_source": request_trace.context_source,
    }
    if request_trace.frontend_run_id:
        fields["frontend_run_id"] = request_trace.frontend_run_id
    if request_trace.frontend_generation is not None:
        fields["frontend_generation"] = request_trace.frontend_generation
    if request_trace.source:
        fields["source"] = request_trace.source
    if request_trace.trigger:
        fields["trigger"] = request_trace.trigger
    if request_trace.cue_point_key:
        fields["cue_point_key"] = request_trace.cue_point_key
    if request_trace.segment_key:
        fields["segment_key"] = request_trace.segment_key
    if request_trace.frontend_route:
        fields["frontend_route"] = request_trace.frontend_route
    return fields


def attach_command_traces(
    commands: list[OscCommand],
    request_trace: RequestTrace,
) -> list[OscCommand]:
    traced: list[OscCommand] = []
    for idx, cmd in enumerate(commands, start=1):
        meta = CommandTraceMeta(
            logical_signal_id=request_trace.logical_signal_id,
            command_id=new_command_id(request_trace.logical_signal_id, idx),
            run_id=request_trace.run_id,
            run_epoch=request_trace.run_epoch,
            http_request_id=request_trace.http_request_id,
        )
        traced.append(cmd.model_copy(update={"trace": meta}))
    return traced


def emit_signal_trace_event(
    event: str,
    *,
    status: str | None = None,
    request_trace: RequestTrace | None = None,
    command: OscCommand | None = None,
    **extra: Any,
) -> None:
    if not effective_signal_trace_enabled():
        return
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event": event,
        "ts_wall": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "ts_mono_ms": round(time.monotonic() * 1000, 2),
    }
    if status is not None:
        payload["status"] = status
    payload.update(request_trace_base_fields(request_trace))
    if command is not None:
        if command.trace:
            payload["command_id"] = command.trace.command_id
            payload["logical_signal_id"] = command.trace.logical_signal_id
        payload["bridge"] = command.bridge
        payload["address"] = command.address
        payload["args"] = command.args
        payload["dry_run"] = command.dry_run
    payload.update(extra)
    SignalTraceWriter.get().write(payload)


def log_command_send_lifecycle(cmd: OscCommand, *, failed: bool = False, error: Exception | None = None) -> None:
    """Emit send lifecycle events for one OscCommand (sync or queue worker)."""
    if not effective_signal_trace_enabled():
        return
    base: dict[str, Any] = {}
    if cmd.trace:
        base = {
            "command_id": cmd.trace.command_id,
            "logical_signal_id": cmd.trace.logical_signal_id,
            "run_id": cmd.trace.run_id,
            "run_epoch": cmd.trace.run_epoch,
            "http_request_id": cmd.trace.http_request_id,
        }
    emit_signal_trace_event(
        "command.send_attempted",
        status="send_attempted",
        bridge=cmd.bridge,
        address=cmd.address,
        dry_run=cmd.dry_run,
        **base,
    )
    if cmd.dry_run:
        emit_signal_trace_event(
            "command.dry_run_suppressed_send",
            status="dry_run_suppressed",
            bridge=cmd.bridge,
            address=cmd.address,
            dry_run=True,
            **base,
        )
        return
    if failed:
        emit_signal_trace_event(
            "command.send_failed",
            status="send_failed",
            bridge=cmd.bridge,
            address=cmd.address,
            error_class=type(error).__name__ if error else "Exception",
            error_message=str(error) if error else "send failed",
            **base,
        )
        return
    emit_signal_trace_event(
        "command.send_completed",
        status="send_completed",
        bridge=cmd.bridge,
        address=cmd.address,
        **base,
    )


def advance_run_epoch(*, barrier_id: str | None = None, barrier_reason: str | None = None) -> int:
    """Backward-compatible Phase 1 helper; Phase 5 code uses DirectorRunState."""
    barrier = get_director_run_state().create_barrier(barrier_reason or "manual")
    emit_signal_trace_event(
        "run.epoch_advanced",
        status="epoch_advanced",
        run_id=barrier.run_id,
        run_epoch=barrier.run_epoch,
        barrier_id=barrier_id or barrier.barrier_id,
        barrier_reason=barrier_reason or barrier.barrier_reason,
    )
    return barrier.run_epoch


def reset_run_state_for_tests() -> None:
    global _run_id, _run_epoch
    with _run_lock:
        _run_id = None
        _run_epoch = 0
    get_director_run_state().reset_for_tests()


class SignalTraceWriter:
    _instance: SignalTraceWriter | None = None
    _instance_lock = threading.Lock()

    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def get(cls) -> SignalTraceWriter:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(Path(settings.signal_trace_path))
            return cls._instance

    @classmethod
    def reset_for_tests(cls, path: Path) -> None:
        with cls._instance_lock:
            cls._instance = cls(path)

    def write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with _write_lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
