import logging
import sys
from pathlib import Path

from app.core.config import settings

_midi_logger = logging.getLogger("theatermaschine.midi")
_configured = False


def _ensure_midi_logger() -> None:
    global _configured
    if _configured:
        return
    formatter = logging.Formatter("%(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    _midi_logger.addHandler(stream_handler)

    log_path = Path(settings.osc_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    _midi_logger.addHandler(file_handler)

    _midi_logger.setLevel(logging.INFO)
    _midi_logger.propagate = False
    _configured = True


def log_midi_command(port: str, message: str, *, dry_run: bool = False, bridge: str = "sound") -> None:
    if not settings.osc_log_commands:
        return
    _ensure_midi_logger()
    mode = "DRY-RUN" if dry_run else "SEND"
    _midi_logger.info(f"[MIDI {mode}] [{bridge}] → {port} {message}")
