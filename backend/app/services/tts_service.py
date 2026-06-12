import platform
from pathlib import Path

from app.core.config import settings
from app.services.tts.edge_provider import EdgeTTSProvider
from app.services.tts.mac_say import MacSayProvider
from app.services.tts.voice_map import voice_for_speaker


class TTSService:
    def resolve_provider(self) -> str:
        mode = settings.tts_provider.lower()
        if mode == "say":
            if not MacSayProvider.is_available():
                raise RuntimeError("TTS_PROVIDER=say, aber macOS say ist nicht verfügbar.")
            return "say"
        if mode == "edge":
            return "edge"
        if MacSayProvider.is_available():
            return "say"
        return "edge"

    def is_available(self) -> bool:
        try:
            self.resolve_provider()
            return True
        except RuntimeError:
            return False

    def status_hint(self) -> str:
        try:
            provider = self.resolve_provider()
        except RuntimeError as exc:
            return str(exc)
        if provider == "say":
            return (
                "Vertonung: Siri/System-Stimmen (macOS). "
                "Stimmen unter Systemeinstellungen → Bedienungshilfen → Gesprochene Inhalte."
            )
        return (
            "Vertonung: edge-tts (Microsoft Neural Voices, kostenlos). "
            "Funktioniert in Docker — Internetverbindung nötig."
        )

    def voice_labels(self) -> tuple[str, str, str]:
        provider = self.resolve_provider()
        if provider == "say":
            return (
                MacSayProvider.voice_for_speaker("AI_A"),
                MacSayProvider.voice_for_speaker("AI_B"),
                MacSayProvider.voice_for_speaker("narrator"),
            )
        return (
            EdgeTTSProvider.voice_for_speaker("AI_A"),
            EdgeTTSProvider.voice_for_speaker("AI_B"),
            EdgeTTSProvider.voice_for_speaker("narrator"),
        )

    async def list_voices(self) -> list[str]:
        provider = self.resolve_provider()
        if provider == "say":
            return MacSayProvider.list_voices()
        return await EdgeTTSProvider.list_voices()

    async def synthesize(self, text: str, speaker: str) -> Path:
        provider = self.resolve_provider()
        voice = voice_for_speaker(speaker, provider=provider)
        if provider == "say":
            return MacSayProvider.synthesize(text, speaker, voice=voice)
        return await EdgeTTSProvider.synthesize(text, speaker, voice=voice)

    @property
    def platform(self) -> str:
        return platform.system()
