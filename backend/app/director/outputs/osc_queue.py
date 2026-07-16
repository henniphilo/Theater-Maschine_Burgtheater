"""Background OSC send queue — HTTP handlers return before hardware I/O finishes."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.director.cues.cue_models import OscCommand
from app.director.outputs.osc_commands import apply_runtime_safety_dry_run, send_osc_commands
from app.director.outputs.signal_trace import (
    emit_signal_trace_event,
    log_command_send_lifecycle,
    new_queue_batch_id,
)
from app.director.run_state import get_director_run_state

CUE_STAGGER_SECONDS = 0.15
_logger = logging.getLogger("theatermaschine.osc")


@dataclass
class _OscBatch:
    commands: list[OscCommand]
    stagger: bool
    bridges: dict[str, Any]
    queue_batch_id: str
    run_id: str | None = None
    run_epoch: int | None = None
    done: threading.Event = field(default_factory=threading.Event)
    sent: list[OscCommand] = field(default_factory=list)


class OscCommandQueue:
    def __init__(self) -> None:
        self._queue: queue.Queue[_OscBatch] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, name="osc-queue", daemon=True)
        self._started = False
        self._start_lock = threading.Lock()

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                return
            self._thread.start()
            self._started = True

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    def enqueue(
        self,
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict[str, Any],
        wait: bool = False,
        timeout: float | None = None,
    ) -> list[OscCommand]:
        """Queue OSC batch; return planned commands unless wait=True (tests)."""
        if not commands:
            return []
        self.start()
        batch_id = new_queue_batch_id()
        batch = _OscBatch(
            commands=commands,
            stagger=stagger,
            bridges=bridges,
            queue_batch_id=batch_id,
            run_id=commands[0].trace.run_id if commands[0].trace else None,
            run_epoch=commands[0].trace.run_epoch if commands[0].trace else None,
        )
        wait_timeout = timeout if timeout is not None else 30.0
        enqueued_at = time.monotonic()
        depth_after = self.depth + 1
        _logger.info(
            "[OSC QUEUE] enqueue depth=%d cmds=%d stagger=%s",
            depth_after,
            len(commands),
            stagger,
        )
        for cmd in commands:
            base: dict[str, Any] = {"queue_batch_id": batch_id, "queue_depth_after": depth_after}
            if cmd.trace:
                base["command_id"] = cmd.trace.command_id
                base["logical_signal_id"] = cmd.trace.logical_signal_id
            emit_signal_trace_event("queue.enqueued", status="enqueued", **base)
        self._queue.put(batch)
        if wait:
            if not batch.done.wait(timeout=wait_timeout):
                raise TimeoutError("OSC queue batch did not complete in time")
            elapsed_ms = (time.monotonic() - enqueued_at) * 1000
            _logger.info(
                "[OSC QUEUE] done waited_ms=%.0f sent=%d",
                elapsed_ms,
                len(batch.sent),
            )
            return batch.sent
        return list(commands)

    def flush(self, timeout: float = 30.0) -> None:
        """Block until all queued batches finish (tests)."""
        self.start()
        sentinel = _OscBatch(commands=[], stagger=False, bridges={}, queue_batch_id="batch-sentinel")
        self._queue.put(sentinel)
        if not sentinel.done.wait(timeout):
            raise TimeoutError("OSC queue flush timed out")

    def _worker(self) -> None:
        while True:
            batch = self._queue.get()
            try:
                if batch.commands:
                    if _batch_is_stale(batch):
                        for cmd in batch.commands:
                            _log_stale_dropped(cmd, queue_batch_id=batch.queue_batch_id)
                        batch.sent = []
                        continue
                    for cmd in batch.commands:
                        base: dict[str, Any] = {"queue_batch_id": batch.queue_batch_id}
                        if cmd.trace:
                            base["command_id"] = cmd.trace.command_id
                            base["logical_signal_id"] = cmd.trace.logical_signal_id
                        emit_signal_trace_event("queue.dequeued", status="dequeued", **base)
                    batch.sent = self._send_batch(
                        batch.commands,
                        stagger=batch.stagger,
                        bridges=batch.bridges,
                    )
            except Exception:
                _logger.exception("[OSC QUEUE] batch failed")
            finally:
                batch.done.set()
                self._queue.task_done()

    @staticmethod
    def _send_batch(
        commands: list[OscCommand],
        *,
        stagger: bool,
        bridges: dict[str, Any],
    ) -> list[OscCommand]:
        return send_osc_batch(commands, stagger=stagger, bridges=bridges)


def send_osc_batch(
    commands: list[OscCommand],
    *,
    stagger: bool,
    bridges: dict[str, Any],
) -> list[OscCommand]:
    sent: list[OscCommand] = []
    last_bridge: str | None = None
    for cmd in commands:
        if _command_is_stale(cmd):
            _log_stale_dropped(cmd)
            continue
        cmd = apply_runtime_safety_dry_run(cmd)
        if stagger and last_bridge is not None and cmd.bridge != last_bridge:
            time.sleep(CUE_STAGGER_SECONDS)
        last_bridge = cmd.bridge
        try:
            send_osc_commands([cmd], bridges)
        except Exception as exc:
            _logger.warning(
                "[CUE FAILED] bridge=%s address=%s: %s",
                cmd.bridge,
                cmd.address,
                exc,
            )
            log_command_send_lifecycle(cmd, failed=True, error=exc)
        else:
            log_command_send_lifecycle(cmd, failed=False)
        sent.append(cmd)
    return sent


def _batch_is_stale(batch: _OscBatch) -> bool:
    if batch.run_id is None or batch.run_epoch is None:
        return False
    return not get_director_run_state().is_current(batch.run_id, batch.run_epoch)


def _command_is_stale(cmd: OscCommand) -> bool:
    if cmd.trace is None:
        return False
    return not get_director_run_state().is_current(cmd.trace.run_id, cmd.trace.run_epoch)


def _log_stale_dropped(cmd: OscCommand, *, queue_batch_id: str | None = None) -> None:
    active = get_director_run_state().current()
    extra: dict[str, Any] = {
        "active_run_id": active.run_id,
        "active_run_epoch": active.run_epoch,
    }
    if queue_batch_id is not None:
        extra["queue_batch_id"] = queue_batch_id
    if cmd.trace:
        extra["command_id"] = cmd.trace.command_id
        extra["logical_signal_id"] = cmd.trace.logical_signal_id
        extra["run_id"] = cmd.trace.run_id
        extra["run_epoch"] = cmd.trace.run_epoch
        extra["http_request_id"] = cmd.trace.http_request_id
    emit_signal_trace_event(
        "queue.stale_dropped",
        status="stale_dropped",
        command=cmd,
        **extra,
    )


_queue: OscCommandQueue | None = None


def get_osc_command_queue() -> OscCommandQueue:
    global _queue
    if _queue is None:
        _queue = OscCommandQueue()
    return _queue
