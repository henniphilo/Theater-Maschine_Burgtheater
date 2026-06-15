from typing import Literal

from pydantic import BaseModel, Field, field_validator

SoundCueAction = Literal["play", "fade_in", "fade_out"]


class SoundCueDefaults(BaseModel):
    channel: int = Field(default=1, ge=1, le=16)
    velocity: int = Field(default=100, ge=1, le=127)


class SoundCueEntry(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(default="", max_length=120)
    soundname: str = Field(default="", max_length=120)
    action: SoundCueAction = "play"
    description: str = Field(default="", max_length=500)
    ableton_hint: str = Field(default="", max_length=300)
    midi_note: int = Field(ge=0, le=127)
    channel: int | None = Field(default=None, ge=1, le=16)
    velocity: int | None = Field(default=None, ge=1, le=127)
    tags: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    intensity_min: float = Field(default=0.0, ge=0.0, le=1.0)
    intensity_max: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().lower()


class SoundCueCatalog(BaseModel):
    version: int = 1
    defaults: SoundCueDefaults = Field(default_factory=SoundCueDefaults)
    cues: list[SoundCueEntry] = Field(default_factory=list)
