"""Sentence splitting aligned with frontend/lib/text/splitSentences.ts."""

from __future__ import annotations

import re


def split_sentences(text: str) -> list[str]:
    trimmed = text.strip()
    if not trimmed:
        return []
    parts = re.findall(r"[^.!?…]+[.!?…]+[\s]*", trimmed)
    if not parts:
        return [trimmed]
    joined = "".join(parts)
    tail = trimmed[len(joined) :].strip()
    if tail:
        return [p.rstrip() for p in parts[:-1]] + [parts[-1].rstrip(), tail]
    return [p.rstrip() for p in parts]


def sentence_char_ranges(text: str) -> list[tuple[int, int]]:
    sentences = split_sentences(text)
    ranges: list[tuple[int, int]] = []
    search_from = 0
    for sentence in sentences:
        stripped = sentence.strip()
        start = text.find(stripped, search_from)
        if start < 0 and len(stripped) > 12:
            start = text.find(stripped[: min(32, len(stripped))], search_from)
        if start < 0:
            start = search_from
        end = start + len(stripped)
        ranges.append((start, end))
        search_from = max(search_from, end)
    return ranges


def sentence_index_at_offset(ranges: list[tuple[int, int]], offset: int) -> int:
    if not ranges:
        return 0
    for index, (start, end) in enumerate(ranges):
        if start <= offset < end:
            return index
        if offset < start:
            return max(0, index - 1)
    return len(ranges) - 1
