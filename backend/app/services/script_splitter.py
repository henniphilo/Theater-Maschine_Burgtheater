import re
import uuid

from app.schemas.script import ScriptBeat, ScriptSpeaker


def split_source_text(source_text: str) -> list[str]:
    text = source_text.strip()
    if not text:
        return []

    if re.search(r"^\s*---\s*$", text, re.MULTILINE):
        parts = [p.strip() for p in re.split(r"^\s*---\s*$", text, flags=re.MULTILINE)]
        return [p for p in parts if p]

    parts = [p.strip() for p in re.split(r"\n\s*\n+", text)]
    return [p for p in parts if p] or [text]


def default_speaker(order: int) -> ScriptSpeaker:
    if order % 2 == 0:
        return "AI_A"
    return "AI_B"


def build_beats_from_text(source_text: str) -> list[ScriptBeat]:
    chunks = split_source_text(source_text)
    beats: list[ScriptBeat] = []
    for index, chunk in enumerate(chunks):
        beats.append(
            ScriptBeat(
                id=str(uuid.uuid4()),
                order=index,
                text=chunk,
                speaker=default_speaker(index),
            )
        )
    return beats
