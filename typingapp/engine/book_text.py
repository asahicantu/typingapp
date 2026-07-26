from __future__ import annotations
import math
import re

CHARS_PER_PAGE = 1200
SENTENCE_END_RE = re.compile(r'[.!?]["\')\]]?(?=\s|$)')
SHORT_HEADING_MAX_WORDS = 8


def normalize_gutenberg_text(raw: str) -> str:
    """Rewrite short standalone lines (surrounded by blank lines) as '# heading' markup."""
    lines = raw.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        prev_blank = i == 0 or not lines[i - 1].strip()
        next_blank = i == len(lines) - 1 or not lines[i + 1].strip()
        if (
            stripped
            and prev_blank
            and next_blank
            and not stripped.startswith("#")
            and len(stripped.split()) <= SHORT_HEADING_MAX_WORDS
            and stripped == stripped.upper()
            and any(c.isalpha() for c in stripped)
        ):
            out.append(f"# {stripped}")
        else:
            out.append(line)
    return "\n".join(out)


def paragraphs(full_text: str) -> list[tuple[str, str]]:
    """Split markup text into [(kind, text), ...] where kind is 'heading' or 'paragraph'."""
    blocks = re.split(r"\n\s*\n", full_text.strip())
    result: list[tuple[str, str]] = []
    for block in blocks:
        text = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not text:
            continue
        if text.startswith("# "):
            result.append(("heading", text[2:].strip()))
        else:
            result.append(("paragraph", text))
    return result


def strip_heading_markup(full_text: str) -> tuple[str, list[tuple[str, int, int]]]:
    """Remove '# ' heading markers (they're markup, not something the user should have to type)
    and return (stripped_text, spans), where spans are (kind, start, end) character offsets into
    stripped_text for each paragraph's content. Used to build the literal text a lesson makes the
    user type, plus enough structure to render it paragraph-aware without re-parsing markup that
    no longer exists in the typed string."""
    out_parts: list[str] = []
    spans: list[tuple[str, int, int]] = []
    pos = 0
    for block in re.split(r"(\n\s*\n)", full_text):
        if block.strip() == "" and "\n" in block:
            out_parts.append(block)
            pos += len(block)
            continue
        if block.startswith("# "):
            kind, content = "heading", block[2:]
        else:
            kind, content = "paragraph", block
        if content:
            spans.append((kind, pos, pos + len(content)))
        out_parts.append(content)
        pos += len(content)
    return "".join(out_parts), spans


def chunk_from_offset(full_text: str, start_offset: int, target_word_count: int, max_words: int) -> tuple[str, int]:
    """Return (chunk_text, end_offset), always ending at a paragraph boundary (or a sentence
    boundary if a single paragraph alone exceeds max_words)."""
    remaining = full_text[start_offset:]
    if not remaining.strip():
        return "", start_offset

    lstripped = remaining.lstrip()
    leading_skip = len(remaining) - len(lstripped)

    # lstripped never starts with whitespace, so the first block from this split is always real
    # paragraph content — that keeps consumed_len exactly in sync with the (unstripped-on-the-left)
    # chunk text, so callers can rely on start_offset + len(chunk_text) == end_offset.
    blocks = re.split(r"(\n\s*\n)", lstripped)
    word_count = 0
    consumed_len = 0
    chunk_parts: list[str] = []

    for block in blocks:
        if block.strip() == "" and "\n" in block:
            # separator between paragraphs
            if chunk_parts:
                chunk_parts.append(block)
                consumed_len += len(block)
            continue

        block_words = block.split()

        if len(block_words) > max_words:
            # a single oversized paragraph/block: cut at the nearest sentence end at/after target
            cut_text, cut_len = _cut_oversized_block(block, target_word_count)
            chunk_parts.append(cut_text)
            consumed_len += cut_len
            word_count += len(cut_text.split())
            break

        if word_count > 0 and word_count + len(block_words) > max_words:
            break

        chunk_parts.append(block)
        consumed_len += len(block)
        word_count += len(block_words)

        if word_count >= target_word_count:
            break

    chunk_text = "".join(chunk_parts).strip()
    end_offset = start_offset + leading_skip + consumed_len
    return chunk_text, end_offset


def _cut_oversized_block(block: str, target_word_count: int) -> tuple[str, int]:
    words = block.split()
    if len(words) <= target_word_count:
        return block, len(block)
    # Find the char offset within `block` covering target_word_count words, then look for
    # the next sentence-ending punctuation at/after that point.
    approx_char = len(" ".join(words[:target_word_count]))
    match = SENTENCE_END_RE.search(block, approx_char)
    if match:
        end = match.end()
        return block[:end], end
    return block, len(block)


def page_info(total_chars: int, current_offset: int) -> tuple[int, int, float]:
    total_chars = max(total_chars, 1)
    current_offset = max(0, min(current_offset, total_chars))
    page = current_offset // CHARS_PER_PAGE + 1
    total_pages = max(1, math.ceil(total_chars / CHARS_PER_PAGE))
    pct = (current_offset / total_chars) * 100
    return page, total_pages, pct
