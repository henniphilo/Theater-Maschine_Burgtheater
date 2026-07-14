#!/usr/bin/env python3
"""Translate Pixera OSC (/pixera/args/cue/apply) to QLab (/cue/{name}/start).

Listens on PIXERA_LISTEN_PORT (default 8990), forwards to QLab on QLAB_PORT (default 53000).
See docs/qlab_setup.md for workspace and .env configuration.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

PIXERA_APPLY_ADDRESS = "/pixera/args/cue/apply"
DEFAULT_LISTEN_HOST = "127.0.0.1"
DEFAULT_LISTEN_PORT = 8990
DEFAULT_QLAB_HOST = "127.0.0.1"
DEFAULT_QLAB_PORT = 53000

logger = logging.getLogger("pixera_qlab_relay")


def qlab_start_address(pixera_address: str, args: list[object]) -> str | None:
    """Map Pixera apply message to QLab start address, or None if not applicable."""
    if pixera_address != PIXERA_APPLY_ADDRESS:
        return None
    if not args:
        return None
    cue_name = args[0]
    if not isinstance(cue_name, str) or not cue_name.strip():
        return None
    return f"/cue/{cue_name.strip()}/start"


def build_relay_handler(qlab_client: SimpleUDPClient):
    def _handler(address: str, *args: object) -> None:
        qlab_address = qlab_start_address(address, list(args))
        if qlab_address is None:
            logger.debug("ignore %s %s", address, args)
            return
        qlab_client.send_message(qlab_address, [])
        logger.info("relay %s %s -> %s", address, args, qlab_address)

    return _handler


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pixera OSC → QLab OSC relay")
    parser.add_argument(
        "--listen-host",
        default=os.environ.get("PIXERA_LISTEN_HOST", DEFAULT_LISTEN_HOST),
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=int(os.environ.get("PIXERA_LISTEN_PORT", DEFAULT_LISTEN_PORT)),
    )
    parser.add_argument(
        "--qlab-host",
        default=os.environ.get("QLAB_HOST", DEFAULT_QLAB_HOST),
    )
    parser.add_argument(
        "--qlab-port",
        type=int,
        default=int(os.environ.get("QLAB_PORT", DEFAULT_QLAB_PORT)),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    qlab_client = SimpleUDPClient(args.qlab_host, args.qlab_port)
    dispatcher = Dispatcher()
    dispatcher.map(PIXERA_APPLY_ADDRESS, build_relay_handler(qlab_client), needs_reply_address=False)

    server = BlockingOSCUDPServer((args.listen_host, args.listen_port), dispatcher)
    logger.info(
        "listening %s:%s -> QLab %s:%s",
        args.listen_host,
        args.listen_port,
        args.qlab_host,
        args.qlab_port,
    )

    def _shutdown(_signum: int, _frame: object) -> None:
        logger.info("shutting down")
        server.shutdown()
        sys.exit(0)

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.serve_forever()
    except OSError as exc:
        logger.error("failed to bind %s:%s (%s)", args.listen_host, args.listen_port, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
