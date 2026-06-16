from app.services.dramaturgy_workshop_service import _clamp_statement
from app.services.script_splitter import (
    MIN_BEAT_LINES,
    build_beats_from_text,
    is_section_long_enough,
    merge_short_chunks,
    split_source_text,
)


def test_split_by_paragraphs() -> None:
    parts = split_source_text("Erster.\n\nZweiter.")
    assert len(parts) == 2


def test_split_by_separator() -> None:
    parts = split_source_text("A\n---\nB")
    assert parts == ["A", "B"]


def test_merge_short_paragraphs_to_min_lines() -> None:
    short = "Zeile eins.\nZeile zwei."
    merged = merge_short_chunks([short, short, short])
    assert len(merged) == 1
    assert is_section_long_enough(merged[0])


def test_build_beats_merges_short_sections() -> None:
    text = "\n\n".join(["Ein Satz hier."] * 4)
    beats = build_beats_from_text(text)
    assert len(beats) == 1
    assert is_section_long_enough(beats[0].text)


def test_split_long_paragraph_into_multiple_beats() -> None:
    long_text = "Erster Satz. " * 200
    beats = build_beats_from_text(long_text.strip())
    assert len(beats) >= 2


def test_build_beats_alternates_speakers() -> None:
    paragraph = "\n".join([f"Zeile {i} mit genug Inhalt." for i in range(MIN_BEAT_LINES)])
    text = "\n\n".join([paragraph, paragraph])
    beats = build_beats_from_text(text)
    assert len(beats) >= 2
    assert beats[0].speaker == "AI_A"
    assert beats[1].speaker == "AI_B"


def test_clamp_statement_at_sentence_boundary() -> None:
    long = ". ".join([f"Satz Nummer {i} mit Inhalt" for i in range(80)])
    clamped = _clamp_statement(long, max_chars=450)
    assert len(clamped) <= 450
    assert clamped.endswith(".")


def test_clamp_statement_short_unchanged() -> None:
    short = "Kurz und knapp."
    assert _clamp_statement(short, max_chars=450) == short
