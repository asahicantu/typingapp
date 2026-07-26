# Literature Mode: Gutenberg Fallback Fix & Sequential Book Reading — Design Spec

**Date:** 2026-07-26
**Builds on:** `docs/superpowers/specs/2026-07-24-literature-text-and-rich-ui-design.md`

---

## Overview

Two related changes to literature mode:

1. **Bug fix:** `LessonEngine._build_literature_lesson` silently fell through to Markov-generated
   text on any live Gutenberg fetch failure, with no on-screen indication anything went wrong.
2. **New feature:** sequential whole-book reading — search Gutenberg and local `.epub` files by
   keyword, pin a specific book, read it start-to-finish across sessions with persisted progress
   and richer paragraph/heading-aware typography.

### Supersedes prior scope decisions

`2026-07-24-literature-text-and-rich-ui-design.md` §9 explicitly listed **"user-submitted/custom
Gutenberg book selection"** and **"persisting full book texts locally"** as out of scope for the
original literature-mode feature. This spec reverses both, at explicit user request. Since Project
Gutenberg's catalog is public domain, storing a pinned book's full text in the user's own local
SQLite DB (not committed to the repo) carries none of the copyright concerns the original
bounded-slice-cache decision was guarding against — this is a scope expansion, not a policy change.

---

## 1. Gutenberg Fallback Fix

Root cause: `_build_literature_lesson`'s three failure branches (no search results, excerpt fetch
returns `None`, both exhausted) all fell through to `_build_random_sentences` with no signal to
the caller. Fix: `LessonEngine.last_fallback_reason: str | None`, set on every fallback branch and
cleared at the top of every `get_lesson()` call. `LessonScreen` surfaces it as `⚠ {reason}` in the
existing `#hint-bar`, both at lesson start and after a mid-session extension fetch.

Separately, `gutendex.com` returns HTTP 403 to Python's default `urllib` User-Agent; `gutenberg.py`
now sends a browser-like UA on every request via a shared `_get()` helper.

---

## 2. Sequential Book Reading

### Data model

- `AppConfig.selected_book_id: str = ""` — `""` keeps the existing random-excerpt/Markov-fallback
  path completely unchanged; `"gutenberg:<id>"` / `"epub:<sha1prefix>"` pins sequential reading.
- `AppConfig.epub_folder: str = ""` — local folder `BookSearchScreen` scans for `.epub` files.
- `storage.books` — one row per pinned book: full cleaned text, `total_chars`, source metadata.
- `storage.book_progress` — one row per book: `current_offset`, `updated_at`.

### Markup convention

Both Gutenberg-sourced (`book_text.normalize_gutenberg_text`) and EPUB-sourced
(`epub_source.epub_to_flat_text`) book text share one convention: a line starting `"# "` is a
heading, a blank line is a paragraph boundary. `book_text.chunk_from_offset` walks paragraphs
(never splitting one mid-word) to build each lesson's text; `book_text.strip_heading_markup`
removes the `"# "` markers before the text is ever handed to a `Scorer` — headings are typed as
plain text, styled distinctly only in the *rendering* layer via tracked paragraph spans.

### Progress persistence

`LessonScreen` tracks book-absolute character offset separately from `Scorer.position` (which only
knows its own chunk). Progress persists on lesson completion, quit, menu navigation, and every
~20s of active typing — not just on full completion — so an ungraceful exit doesn't lose much
ground. See `CLAUDE.md` for the exact offset-math invariant (heading-marker stripping shifts
`Scorer.position` out of sync with the raw book offset unless corrected).

### EPUB parsing

Hand-rolled with stdlib (`zipfile` + `xml.etree.ElementTree` + `html.parser.HTMLParser`) rather
than adding a third-party EPUB dependency — this app has exactly one dependency (`textual`) today,
and the EPUB structure needed (container.xml → OPF spine → ordered XHTML → heading/paragraph
extraction) is a few hundred lines. Never raises, matching the existing network-call convention.

### Known trade-off

`SettingsScreen._pin_book` fetches a book's full text (up to 15s for Gutenberg) synchronously on
the UI thread. This app has no async/worker pattern anywhere yet; introducing Textual `@work`
workers for a once-per-book-selection action wasn't judged worth the complexity for this change.

---

## Testing

Followed the existing plain-pytest-per-module convention: `tests/test_book_text.py`,
`tests/test_epub_source.py` (new, pure-function unit tests), `tests/test_storage.py`,
`tests/test_gutenberg.py`, `tests/test_lesson.py` (extended). Two screen-level pilot tests were
added despite this repo's zero prior screen-test coverage
(`tests/test_book_search_screen.py`, `tests/test_lesson_screen_book_mode.py`) because manual pilot
testing surfaced real, non-obvious bugs — a `ListView.clear()`/`.index` reset that left keyboard
selection a no-op, and Rich-vs-Textual markup syntax incompatibility — that no pure-function test
would have caught.
