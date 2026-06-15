from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.script import ProductionScript

PERFORMANCE_FORMAT_VERSION = 1


class PerformanceAudioEntry(BaseModel):
    beat_id: str
    beat_order: int
    kind: Literal["discussion", "performance"]
    turn_index: int | None = None
    speaker: str
    path: str
    extension: str


class PerformanceManifest(BaseModel):
    format_version: int = PERFORMANCE_FORMAT_VERSION
    exported_at: datetime
    tts_provider: str
    script: ProductionScript
    audio_files: list[PerformanceAudioEntry] = Field(default_factory=list)
