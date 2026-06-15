import re
import uuid

from app.schemas.script import ScriptBeat, ScriptSpeaker

MIN_BEAT_LINES = 4
MAX_BEAT_CHARS = 1800


def split_source_text(source_text: str) -> list[str]:
    text = source_text.strip()
    if not text:
        return []

    if re.search(r"^\s*---\s*$", text, re.MULTILINE):
        parts = [p.strip() for p in re.split(r"^\s*---\s*$", text, flags=re.MULTILINE)]
        return [p for p in parts if p]

    parts = [p.strip() for p in re.split(r"\n\s*\n+", text)]
    return [p for p in parts if p] or [text]


def split_sentences(text: str) -> list[str]:
    trimmed = text.strip()
    if not trimmed:
        return []
    parts = re.findall(r"[^.!?…]+[.!?…]+[\s]*", trimmed)
    if not parts:
        return [trimmed]
    joined = "".join(parts)
    tail = trimmed[len(joined) :].strip()
    sentences = [p.strip() for p in parts]
    if tail:
        sentences.append(tail)
    return sentences


def count_lines(text: str) -> int:
    return len([ln for ln in text.splitlines() if ln.strip()])


def is_section_long_enough(text: str) -> bool:
    if count_lines(text) >= MIN_BEAT_LINES:
        return True
    return len(split_sentences(text)) >= MIN_BEAT_LINES


def merge_short_chunks(chunks: list[str]) -> list[str]:
    if not chunks:
        return []

    merged: list[str] = []
    current = chunks[0]
    for chunk in chunks[1:]:
        combined = f"{current}\n\n{chunk}"
        if not is_section_long_enough(current) and len(combined) <= MAX_BEAT_CHARS:
            current = combined
        else:
            merged.append(current)
            current = chunk
    merged.append(current)

    if len(merged) >= 2 and not is_section_long_enough(merged[-1]):
        tail = merged.pop()
        candidate = f"{merged[-1]}\n\n{tail}"
        if len(candidate) <= MAX_BEAT_CHARS:
            merged[-1] = candidate
        else:
            merged.append(tail)

    return merged


def split_long_chunk(chunk: str) -> list[str]:
    if len(chunk) <= MAX_BEAT_CHARS:
        return [chunk]
    sentences = split_sentences(chunk)
    if len(sentences) <= 1:
        return [chunk[:MAX_BEAT_CHARS].rstrip()]
    groups: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        sentence_len = len(sentence)
        if current and current_len + sentence_len > MAX_BEAT_CHARS:
            groups.append(" ".join(current))
            current = [sentence]
            current_len = sentence_len
        else:
            current.append(sentence)
            current_len += sentence_len + 1
    if current:
        groups.append(" ".join(current))
    return groups or [chunk]


def default_speaker(order: int) -> ScriptSpeaker:
    if order % 2 == 0:
        return "AI_A"
    return "AI_B"


def build_beats_from_text(source_text: str) -> list[ScriptBeat]:
    chunks = merge_short_chunks(split_source_text(source_text))
    expanded: list[str] = []
    for chunk in chunks:
        expanded.extend(split_long_chunk(chunk))

    beats: list[ScriptBeat] = []
    for index, chunk in enumerate(expanded):
        beats.append(
            ScriptBeat(
                id=str(uuid.uuid4()),
                order=index,
                text=chunk,
                speaker=default_speaker(index),
            )
        )
    return beats
