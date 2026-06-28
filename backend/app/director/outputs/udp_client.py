"""Lazy OSC UDP client — no socket at import time (CI, tests, unreachable hosts)."""

from __future__ import annotations

import logging

from pythonosc import udp_client

_logger = logging.getLogger(__name__)


def create_udp_client(host: str, port: int) -> udp_client.SimpleUDPClient | None:
    try:
        return udp_client.SimpleUDPClient(host, port)
    except OSError as exc:
        _logger.warning("OSC UDP client unavailable for %s:%s (%s)", host, port, exc)
        return None
