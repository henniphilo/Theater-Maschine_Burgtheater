"""Authoritative Director performance run/epoch state."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_epoch: int


@dataclass(frozen=True)
class RunBarrier:
    run_id: str
    run_epoch: int
    barrier_id: str
    barrier_reason: str


def _new_run_id() -> str:
    now = datetime.now(UTC)
    return f"run-{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"


def _new_barrier_id() -> str:
    return f"barrier-{secrets.token_hex(3)}"


class DirectorRunState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run_id = _new_run_id()
        self._run_epoch = 0

    def current(self) -> RunContext:
        with self._lock:
            return RunContext(run_id=self._run_id, run_epoch=self._run_epoch)

    def start_run(self) -> RunContext:
        with self._lock:
            self._run_id = _new_run_id()
            self._run_epoch = 0
            return RunContext(run_id=self._run_id, run_epoch=self._run_epoch)

    def create_barrier(self, reason: str) -> RunBarrier:
        with self._lock:
            self._run_epoch += 1
            return RunBarrier(
                run_id=self._run_id,
                run_epoch=self._run_epoch,
                barrier_id=_new_barrier_id(),
                barrier_reason=reason,
            )

    def is_current(self, run_id: str | None, run_epoch: int | None) -> bool:
        if run_id is None or run_epoch is None:
            return False
        with self._lock:
            return self._run_id == run_id and self._run_epoch == run_epoch

    def reset_for_tests(self) -> None:
        with self._lock:
            self._run_id = _new_run_id()
            self._run_epoch = 0


_run_state = DirectorRunState()


def get_director_run_state() -> DirectorRunState:
    return _run_state
