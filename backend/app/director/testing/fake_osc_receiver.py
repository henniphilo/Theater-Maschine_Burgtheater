"""UDP/OSC fake receiver for signal trace validation."""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

from app.director.outputs.signal_trace import emit_signal_trace_event, new_receiver_event_id


class FakeOscReceiver:
    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._host = host
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((host, port))
        self._port = self._sock.getsockname()[1]
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._messages: list[dict[str, Any]] = []

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="fake-osc-receiver", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        self._sock.close()

    def wait_for_messages(self, count: int = 1, timeout: float = 0.5) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self._messages) >= count:
                break
            time.sleep(0.01)
        return self.messages

    def _loop(self) -> None:
        self._sock.settimeout(0.1)
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(65535)
            except TimeoutError:
                continue
            except OSError:
                break
            message = {
                "host": addr[0],
                "port": addr[1],
                "bytes": len(data),
                "raw": data[:128],
            }
            self._messages.append(message)
            emit_signal_trace_event(
                "receiver.seen",
                status="seen",
                receiver_event_id=new_receiver_event_id(),
                receiver_host=addr[0],
                receiver_port=addr[1],
                raw_length=len(data),
            )
