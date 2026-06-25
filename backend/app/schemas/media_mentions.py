from typing import Literal

from pydantic import BaseModel, Field

MediaMentionMedium = Literal["sound", "music", "video", "light"]


class MediaMention(BaseModel):
    medium: MediaMentionMedium
    media_id: str = Field(min_length=1, max_length=80)
    keyword: str | None = Field(default=None, max_length=120)
    char_offset: int = Field(default=0, ge=0)
