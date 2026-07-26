import pytest
from typingapp.engine.book_text import (
    normalize_gutenberg_text, paragraphs, chunk_from_offset, page_info, CHARS_PER_PAGE,
)


def test_normalize_marks_short_standalone_uppercase_line_as_heading():
    raw = "Some intro.\n\nCHAPTER ONE\n\nThe story begins here with real prose."
    normalized = normalize_gutenberg_text(raw)
    assert "# CHAPTER ONE" in normalized


def test_normalize_leaves_ordinary_paragraphs_alone():
    raw = "This is a normal paragraph that happens to be reasonably long and lowercase."
    normalized = normalize_gutenberg_text(raw)
    assert normalized == raw


def test_paragraphs_splits_on_blank_lines_and_tags_headings():
    text = "# Chapter One\n\nFirst paragraph.\n\nSecond paragraph."
    result = paragraphs(text)
    assert result == [
        ("heading", "Chapter One"),
        ("paragraph", "First paragraph."),
        ("paragraph", "Second paragraph."),
    ]


def test_chunk_from_offset_stops_at_paragraph_boundary():
    text = "One two three four five.\n\nSix seven eight nine ten.\n\nEleven twelve thirteen."
    chunk, end_offset = chunk_from_offset(text, start_offset=0, target_word_count=8, max_words=20)
    assert chunk == "One two three four five.\n\nSix seven eight nine ten."
    assert text[end_offset:].lstrip() == "Eleven twelve thirteen."


def test_chunk_from_offset_splits_oversized_paragraph_at_sentence_boundary():
    long_paragraph = " ".join(f"word{i}" for i in range(50)) + ". " + " ".join(f"more{i}" for i in range(20)) + "."
    chunk, end_offset = chunk_from_offset(long_paragraph, start_offset=0, target_word_count=10, max_words=20)
    assert chunk.endswith(".")
    assert len(chunk.split()) <= 51  # cut at/after target, not mid-word, not the whole 71-word block
    assert end_offset <= len(long_paragraph)


def test_chunk_from_offset_handles_end_of_book():
    text = "Only paragraph left."
    chunk, end_offset = chunk_from_offset(text, start_offset=0, target_word_count=50, max_words=100)
    assert chunk == "Only paragraph left."
    assert end_offset == len(text)


def test_chunk_from_offset_at_true_end_returns_empty():
    text = "Only paragraph left."
    chunk, end_offset = chunk_from_offset(text, start_offset=len(text), target_word_count=50, max_words=100)
    assert chunk == ""
    assert end_offset == len(text)


def test_page_info_arithmetic():
    total_chars = CHARS_PER_PAGE * 3
    page, total_pages, pct = page_info(total_chars, current_offset=CHARS_PER_PAGE)
    assert page == 2
    assert total_pages == 3
    assert pct == pytest.approx(33.33, abs=0.5)


def test_page_info_at_start_and_end():
    page, total_pages, pct = page_info(1000, 0)
    assert page == 1 and pct == 0
    page, total_pages, pct = page_info(1000, 1000)
    assert page == total_pages
    assert pct == 100
