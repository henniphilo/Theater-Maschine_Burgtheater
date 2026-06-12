"""Phase 2/3: Lighting output via OSC stub (Art-Net planned for Phase 3)."""

from pythonosc import udp_client

from app.core.config import settings
from app.director.cues.cue_models import LightCue
from app.director.media.database import MediaDatabase
from app.director.outputs.osc_log import log_osc_command


class LightingBridge:
    def __init__(
        self,
        media_db: MediaDatabase | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.media_db = media_db or MediaDatabase()
        self.host = host or settings.osc_host
        self.port = port or settings.osc_port
        self._client = udp_client.SimpleUDPClient(self.host, self.port)

    def execute(self, cue: LightCue, dry_run: bool = False) -> None:
        if cue.scene_id is None:
            return
        scene = next((s for s in self.media_db.light_scenes if s.id == cue.scene_id), None)
        fade = cue.fade_time if cue.fade_time else (scene.fade_time if scene else 4.0)
        self._send("/light/set_scene", cue.scene_id, fade, dry_run=dry_run)
    def blackout(self, dry_run: bool = False) -> None:
        self._send("/light/blackout", dry_run=dry_run)

    def _send(self, address: str, *args: object, dry_run: bool = False) -> None:
        is_dry_run = dry_run or settings.osc_dry_run
        log_osc_command(
            self.host,
            self.port,
            address,
            list(args),
            dry_run=is_dry_run,
            bridge="light",
        )
        if is_dry_run:
            return
        self._client.send_message(address, list(args))
