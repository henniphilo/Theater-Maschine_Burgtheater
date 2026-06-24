"""Sound output via MIDI and/or OSC (QLab/Ableton/TouchDesigner)."""

from pythonosc import udp_client

from app.core.config import settings
from app.director.cues.cue_models import SoundCue
from app.director.outputs.osc_log import log_osc_command
from app.director.outputs.sound_midi import get_sound_midi_bridge
from app.services.sound_cue_catalog import get_sound_cue_catalog_service


class SoundBridge:
    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.host = host or settings.osc_host
        self.port = port or settings.osc_port
        self._osc_client: udp_client.SimpleUDPClient | None = None
        if settings.sound_output in {"osc", "both"} or settings.sound_osc_mirror:
            self._osc_client = udp_client.SimpleUDPClient(self.host, self.port)

    def execute(self, cue: SoundCue, dry_run: bool = False) -> None:
        if cue.cue_id is None:
            return
        catalog = get_sound_cue_catalog_service().load()
        entry = next((c for c in catalog.cues if c.id == cue.cue_id), None)
        if entry is not None and entry.action == "cut_all":
            self.stop_all(dry_run=dry_run)
            return
        if cue.action.value == "trigger_cue":
            self._trigger(cue.cue_id, cue.volume, dry_run=dry_run)
        elif cue.action.value == "stop_cue":
            self._stop(cue.cue_id, dry_run=dry_run)
        elif cue.action.value == "set_volume":
            self._set_volume(cue.cue_id, cue.volume, dry_run=dry_run)

    def hold(self, cue: SoundCue, dry_run: bool = False) -> None:
        if cue.cue_id is None:
            return
        if settings.sound_output in {"midi", "both"}:
            get_sound_midi_bridge().hold(cue.cue_id, cue.volume, dry_run=dry_run)
        if settings.sound_output in {"osc", "both"} or (
            settings.sound_output == "midi" and settings.sound_osc_mirror
        ):
            self._send_osc("/sound/hold", cue.cue_id, cue.volume, dry_run=dry_run)

    def stop_all(self, dry_run: bool = False) -> None:
        if settings.sound_output in {"midi", "both"}:
            get_sound_midi_bridge().stop_all(dry_run=dry_run)
        if settings.sound_output in {"osc", "both"} or (
            settings.sound_output == "midi" and settings.sound_osc_mirror
        ):
            self._send_osc("/sound/stop_all", dry_run=dry_run)

    def _trigger(self, cue_id: str, volume: float, *, dry_run: bool) -> None:
        if settings.sound_output in {"midi", "both"}:
            get_sound_midi_bridge().trigger(cue_id, volume, dry_run=dry_run)
        if settings.sound_output in {"osc", "both"} or (
            settings.sound_output == "midi" and settings.sound_osc_mirror
        ):
            self._send_osc("/sound/trigger", cue_id, volume, dry_run=dry_run)

    def _stop(self, cue_id: str, *, dry_run: bool) -> None:
        if settings.sound_output in {"midi", "both"}:
            get_sound_midi_bridge().stop(cue_id, dry_run=dry_run)
        if settings.sound_output in {"osc", "both"} or (
            settings.sound_output == "midi" and settings.sound_osc_mirror
        ):
            self._send_osc("/sound/stop", cue_id, dry_run=dry_run)

    def _set_volume(self, cue_id: str, volume: float, *, dry_run: bool) -> None:
        if settings.sound_output in {"midi", "both"}:
            get_sound_midi_bridge().trigger(cue_id, volume, dry_run=dry_run)
        if settings.sound_output in {"osc", "both"} or (
            settings.sound_output == "midi" and settings.sound_osc_mirror
        ):
            self._send_osc("/sound/volume", cue_id, volume, dry_run=dry_run)

    def _send_osc(self, address: str, *args: object, dry_run: bool = False) -> None:
        is_dry_run = dry_run or settings.osc_dry_run
        log_osc_command(
            self.host,
            self.port,
            address,
            list(args),
            dry_run=is_dry_run,
            bridge="sound",
        )
        if is_dry_run or self._osc_client is None:
            return
        self._osc_client.send_message(address, list(args))
