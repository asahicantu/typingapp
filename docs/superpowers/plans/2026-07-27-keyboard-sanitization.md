# Keyboard Sanitization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure no lesson/book text ever contains a character the user's keyboard layout cannot physically type, so a session can never get permanently stuck on an untypeable character.

**Architecture:** A new pure function `sanitize_for_keyboard(text: str, layout: str = "en-us-qwerty") -> str` in a new `typingapp/engine/keyboard_sanitize.py` module. It walks the input character-by-character; each character either passes through unchanged (already typeable), gets replaced by exactly one ASCII equivalent character via a translation table (curly quotes → straight quotes, em/en-dash → hyphen, ellipsis character → a single period, non-breaking space → space, etc.), or — if there's no reasonable equivalent — gets replaced by a single space. Every replacement is exactly one character, so `len(output) == len(input)` always. `LessonScreen` calls this once on every piece of text it receives before it ever reaches `strip_heading_markup`/`Scorer`, at both places new text enters a session: `_load_lesson_text` (initial chunk, called from `_start_lesson`) and `_maybe_extend_text` (mid-session extension chunk).

**Tech Stack:** Pure Python (`str.translate` + a regex fallback pass), no new dependencies. Follows the existing pattern in this codebase of small, Textual-free, independently-unit-tested modules under `typingapp/engine/`.

## Global Constraints

- Never delete characters, and never replace one character with a multi-character string (e.g. `"..."` for `…`) — every replacement must be exactly ONE character (a single ASCII character or a single space), so `len(output) == len(input)` always. This repo's book-progress/page-percent math (`book_text.chunk_from_offset`, `LessonScreen._book_raw_offset`) assumes strict 1:1 character correspondence between the original book text and what gets typed, and this plan must not break that.
- Only fixes `en-us-qwerty` per the confirmed design scope — no other layouts.
- Local corpora (`words.txt`, `sentences.txt`, and the es/fr variants) are already pure ASCII (confirmed directly by reading the files) — sanitization is only needed for Gutenberg/EPUB-sourced book text and the Markov-generated random-sentences text (which is built from those same corpora plus cached Gutenberg excerpts, so it can inherit non-ASCII characters from the excerpts).
- Follow this repo's existing test convention: plain pytest unit tests, one file per engine module, no Textual/pilot tests for pure logic (screen-level tests only where screen *behavior*, not pure logic, needs verifying — see Task 3).

---

### Task 1: `sanitize_for_keyboard` pure function

**Files:**
- Create: `typingapp/engine/keyboard_sanitize.py`
- Test: `tests/test_keyboard_sanitize.py`

**Interfaces:**
- Produces: `sanitize_for_keyboard(text: str, layout: str = "en-us-qwerty") -> str` — used by Task 2 (`LessonScreen`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_keyboard_sanitize.py
from typingapp.engine.keyboard_sanitize import sanitize_for_keyboard


def test_ascii_text_passes_through_unchanged():
    text = "The quick brown fox jumps over the lazy dog. 123!"
    assert sanitize_for_keyboard(text) == text


def test_curly_double_quotes_become_straight_quotes():
    assert sanitize_for_keyboard("“Hello”") == '"Hello"'


def test_curly_single_quotes_and_apostrophe_become_straight_apostrophe():
    assert sanitize_for_keyboard("‘Hello’") == "'Hello'"
    assert sanitize_for_keyboard("don’t") == "don't"


def test_em_dash_and_en_dash_become_hyphen():
    assert sanitize_for_keyboard("wait—no") == "wait-no"
    assert sanitize_for_keyboard("pages 1–2") == "pages 1-2"


def test_ellipsis_character_becomes_a_single_period():
    # NOTE: the single-character ellipsis (U+2026) must become exactly ONE
    # ASCII character, not "...", to preserve 1:1 character-offset correspondence
    # with the original book text (see Global Constraints).
    assert sanitize_for_keyboard("wait…") == "wait."


def test_non_breaking_space_becomes_a_regular_space():
    assert sanitize_for_keyboard("100 km") == "100 km"


def test_unmappable_character_becomes_a_single_space():
    # e.g. a CJK character or emoji has no sane single-key ASCII equivalent
    assert sanitize_for_keyboard("hello中 world") == "hello  world"


def test_output_length_always_equals_input_length():
    # the invariant every other book-offset computation in this codebase depends on
    samples = [
        "plain ascii",
        "“curly quotes’ and — dashes… mixed in中text",
        "",
    ]
    for text in samples:
        assert len(sanitize_for_keyboard(text)) == len(text)


def test_unknown_layout_falls_back_to_en_us_qwerty_behavior():
    text = "“Hello”"
    assert sanitize_for_keyboard(text, layout="klingon") == sanitize_for_keyboard(text, layout="en-us-qwerty")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_keyboard_sanitize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'typingapp.engine.keyboard_sanitize'`

- [ ] **Step 3: Write the implementation**

```python
# typingapp/engine/keyboard_sanitize.py
from __future__ import annotations

# US-QWERTY-typeable ASCII: printable 0x20-0x7E plus common whitespace.
TYPEABLE_ASCII = frozenset(chr(c) for c in range(0x20, 0x7F)) | {"\n", "\t"}

# Each entry maps one non-typeable character to exactly one typeable replacement
# character. Every value here MUST be a single character — this file's sanitize
# function assumes a strict 1:1 character correspondence between input and output
# so that book-offset math elsewhere in the app (chunk_from_offset, page_info,
# LessonScreen._book_raw_offset) is never broken by sanitizing lesson text.
_EN_US_QWERTY_REPLACEMENTS: dict[str, str] = {
    "‘": "'",  # left single quotation mark
    "’": "'",  # right single quotation mark / apostrophe
    "‚": ",",  # single low-9 quotation mark
    "‛": "'",  # single high-reversed-9 quotation mark
    "“": '"',  # left double quotation mark
    "”": '"',  # right double quotation mark
    "„": '"',  # double low-9 quotation mark
    "‟": '"',  # double high-reversed-9 quotation mark
    "–": "-",  # en dash
    "—": "-",  # em dash
    "−": "-",  # minus sign
    "…": ".",  # horizontal ellipsis (single character) -> single period
    " ": " ",  # non-breaking space
    " ": " ",  # en space
    " ": " ",  # em space
    " ": " ",  # thin space
    "​": " ",  # zero-width space
    "﻿": " ",  # BOM / zero-width no-break space
}

_LAYOUTS = {
    "en-us-qwerty": _EN_US_QWERTY_REPLACEMENTS,
}
_DEFAULT_LAYOUT = "en-us-qwerty"


def sanitize_for_keyboard(text: str, layout: str = "en-us-qwerty") -> str:
    """Replace every character not typeable on `layout` with a single-character
    ASCII equivalent, or a single space if there's no reasonable equivalent.
    Guarantees len(output) == len(input) always, so callers that track character
    offsets into the original text (book progress/page percent) stay correct."""
    replacements = _LAYOUTS.get(layout, _LAYOUTS[_DEFAULT_LAYOUT])
    out_chars = []
    for ch in text:
        if ch in TYPEABLE_ASCII:
            out_chars.append(ch)
        elif ch in replacements:
            out_chars.append(replacements[ch])
        else:
            out_chars.append(" ")
    return "".join(out_chars)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_keyboard_sanitize.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/keyboard_sanitize.py tests/test_keyboard_sanitize.py
git commit -m "feat: add sanitize_for_keyboard to strip non-QWERTY-typeable characters"
```

---

### Task 2: Wire sanitization into `LessonScreen`

**Files:**
- Modify: `typingapp/screens/lesson.py:45-66` (`_load_lesson_text`), `typingapp/screens/lesson.py:176-237` (`_maybe_extend_text`)
- Test: `tests/test_lesson_screen_sanitization.py`

**Interfaces:**
- Consumes: `sanitize_for_keyboard(text: str, layout: str = "en-us-qwerty") -> str` from Task 1.
- Produces: `LessonScreen._load_lesson_text()` and the `more_text` variable inside `_maybe_extend_text()` now always return/hold already-sanitized text — every downstream consumer (`strip_heading_markup`, `Scorer`) continues to work unmodified since sanitization preserves both length and paragraph/heading markup (the `"# "` prefix and blank-line separators used by `strip_heading_markup` are themselves already ASCII/typeable, so they pass through `sanitize_for_keyboard` unchanged).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lesson_screen_sanitization.py
import asyncio
import datetime
from pathlib import Path
from textual.app import App

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen

UNTYPEABLE_BOOK_TEXT = (
    "# Chapter One\n\n"
    "“Wait—no,” she said… ‘Really?’ A pause of 100 km followed.\n\n"
    "Second paragraph with normal ascii text."
)


def _make_app(storage, book_id="gutenberg:1"):
    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = AppConfig(content_type="literature", selected_book_id=book_id,
                                     session_duration=600, key_sounds=False)
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LessonScreen())

    return TestApp()


def test_book_mode_target_contains_no_untypeable_characters(tmp_path):
    from typingapp.engine.keyboard_sanitize import TYPEABLE_ASCII

    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=UNTYPEABLE_BOOK_TEXT, cached_at="2026-07-27T10:00:00")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            target = app.screen._scorer.target
            for ch in target:
                assert ch in TYPEABLE_ASCII, f"untypeable character {ch!r} reached the Scorer target"

    asyncio.run(run())
    storage.close()


def test_sanitization_preserves_book_offset_arithmetic(tmp_path):
    # regression: sanitizing must never change character COUNT, or book_progress offsets
    # (measured against the original, unsanitized full_text) would drift from what was
    # actually typed.
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=UNTYPEABLE_BOOK_TEXT, cached_at="2026-07-27T10:00:00")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            target = screen._scorer.target
            while not screen._scorer.is_complete:
                ch = target[screen._scorer.position]
                await pilot.press(ch if ch != " " else "space")
            await pilot.pause()

    asyncio.run(run())

    assert storage.fetch_book_progress("gutenberg:1") == len(UNTYPEABLE_BOOK_TEXT)
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_sanitization.py -v`
Expected: FAIL — `test_book_mode_target_contains_no_untypeable_characters` fails because the raw curly quotes/dashes/ellipsis/nbsp from `UNTYPEABLE_BOOK_TEXT` are still present in `screen._scorer.target` (sanitization not wired in yet).

- [ ] **Step 3: Wire sanitization into `_load_lesson_text`**

In `typingapp/screens/lesson.py`, add the import near the top (alongside the existing `book_text` import):

```python
from typingapp.engine.book_text import page_info, strip_heading_markup
from typingapp.engine.keyboard_sanitize import sanitize_for_keyboard
```

Change `_load_lesson_text` (currently lines 45-66) from:

```python
    def _load_lesson_text(self) -> str:
        app = self.app      # type: ignore[attr-defined]
        cfg = app.config
        adaptive: AdaptiveEngine = app.adaptive
        storage = app.storage
        bigrams = storage.fetch_bigram_heatmap(limit=5)
        weak = [b["bigram"] for b in bigrams]
        recent_wpms = storage.fetch_last_n_wpm(n=5)
        recent_wpm = sum(recent_wpms) / len(recent_wpms) if recent_wpms else 0
        difficulty = cfg.difficulty if cfg.manual_difficulty else adaptive.current_level
        return app.lesson_engine.get_lesson(
            content_type=cfg.content_type,
            difficulty=difficulty,
            custom_text=self._custom_text,
            weak_bigrams=weak,
            language=cfg.language,
            storage=storage,
            recent_wpm=recent_wpm,
            session_duration=cfg.session_duration,
            word_count_override=cfg.word_count_override,
            selected_book_id=cfg.selected_book_id,
        )
```

to:

```python
    def _load_lesson_text(self) -> str:
        app = self.app      # type: ignore[attr-defined]
        cfg = app.config
        adaptive: AdaptiveEngine = app.adaptive
        storage = app.storage
        bigrams = storage.fetch_bigram_heatmap(limit=5)
        weak = [b["bigram"] for b in bigrams]
        recent_wpms = storage.fetch_last_n_wpm(n=5)
        recent_wpm = sum(recent_wpms) / len(recent_wpms) if recent_wpms else 0
        difficulty = cfg.difficulty if cfg.manual_difficulty else adaptive.current_level
        text = app.lesson_engine.get_lesson(
            content_type=cfg.content_type,
            difficulty=difficulty,
            custom_text=self._custom_text,
            weak_bigrams=weak,
            language=cfg.language,
            storage=storage,
            recent_wpm=recent_wpm,
            session_duration=cfg.session_duration,
            word_count_override=cfg.word_count_override,
            selected_book_id=cfg.selected_book_id,
        )
        if text == BOOK_COMPLETE_SENTINEL:
            return text
        return sanitize_for_keyboard(text)
```

(The `BOOK_COMPLETE_SENTINEL` check is required because that sentinel is a control string, `"\x00__BOOK_COMPLETE__\x00"`, not real lesson text — sanitizing it would corrupt the sentinel value that `_start_lesson` checks for immediately after calling `_load_lesson_text()`.)

- [ ] **Step 4: Wire sanitization into `_maybe_extend_text`**

In `typingapp/screens/lesson.py`, inside `_maybe_extend_text` (currently lines 176-237), find this block:

```python
        try:
            more_text = app.lesson_engine.get_lesson(
                content_type=cfg.content_type,
                difficulty=app.adaptive.current_level,
                language=cfg.language,
                storage=app.storage,
                recent_wpm=s.wpm,
                session_duration=time_budget,
                selected_book_id=cfg.selected_book_id,
            )
        except Exception:
            more_text = ""
        reason = app.lesson_engine.last_fallback_reason
        if reason:
            self.query_one("#hint-bar", Label).update(f"⚠ {reason}")
        if more_text == BOOK_COMPLETE_SENTINEL:
            self.query_one("#hint-bar", Label).update("🎉 You've reached the end of this book!")
            return
```

Change it to sanitize `more_text` right after the sentinel check (the sentinel must be checked against the *raw* return value first, same reasoning as Step 3):

```python
        try:
            more_text = app.lesson_engine.get_lesson(
                content_type=cfg.content_type,
                difficulty=app.adaptive.current_level,
                language=cfg.language,
                storage=app.storage,
                recent_wpm=s.wpm,
                session_duration=time_budget,
                selected_book_id=cfg.selected_book_id,
            )
        except Exception:
            more_text = ""
        reason = app.lesson_engine.last_fallback_reason
        if reason:
            self.query_one("#hint-bar", Label).update(f"⚠ {reason}")
        if more_text == BOOK_COMPLETE_SENTINEL:
            self.query_one("#hint-bar", Label).update("🎉 You've reached the end of this book!")
            return
        if more_text:
            more_text = sanitize_for_keyboard(more_text)
```

(The rest of the function, the `if more_text:` block that calls `strip_heading_markup`/`s.extend`, stays exactly as-is below this — it already only runs `if more_text:` truthy, so this new sanitization line simply reassigns `more_text` in place before that existing block runs.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_sanitization.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass (155+ previously passing tests, plus the new ones from this plan)

- [ ] **Step 7: Commit**

```bash
git add typingapp/screens/lesson.py tests/test_lesson_screen_sanitization.py
git commit -m "fix: sanitize lesson text so no untypeable character can block a session"
```

---

### Task 3: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only).

- [ ] **Step 1: Add a new bullet to the Architecture section**, alongside the existing `engine/` module list (find the line describing `typingapp/engine/book_text.py` and add a new line immediately after it):

```markdown
- `typingapp/engine/keyboard_sanitize.py` — `sanitize_for_keyboard(text, layout="en-us-qwerty")` replaces every character not typeable on the given keyboard layout with a single-character ASCII equivalent (curly quotes → straight quotes, em/en-dash → hyphen, ellipsis → period, non-breaking space → space, etc.), or a single space if there's no reasonable equivalent. Guarantees `len(output) == len(input)` always — this is load-bearing, not incidental, since book-offset tracking (`book_text.chunk_from_offset`, `LessonScreen._book_raw_offset`) assumes a strict 1:1 character correspondence between the original book text and what the user actually types.
```

- [ ] **Step 2: Add a new Key Invariant**, appended at the end of the Key Invariants section:

```markdown
- **All lesson text is sanitized for the keyboard before it becomes a `Scorer` target.** `LessonScreen._load_lesson_text` and `_maybe_extend_text` both call `keyboard_sanitize.sanitize_for_keyboard` on whatever `LessonEngine.get_lesson` returns (except the `BOOK_COMPLETE_SENTINEL` control string, which is checked and returned/handled *before* sanitization so the sentinel itself is never corrupted). This exists because real Gutenberg/EPUB book text commonly contains curly quotes, em/en-dashes, ellipsis characters, and non-breaking spaces that a US-QWERTY keyboard cannot physically type — without this, a session could get permanently stuck on a character the user has no way to enter. Local `words.txt`/`sentences.txt` corpora (including the es/fr variants) are already pure ASCII and don't strictly need this, but nothing prevents it from running on them too — it's a no-op there.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document keyboard sanitization in CLAUDE.md"
```

## Self-Review Notes

- **Spec coverage:** covers Stage A in full (items #3 and #11 from the original feedback batch) — character sanitization applied at both text-entry points in `LessonScreen`, with the length-preservation invariant explicitly tested since it's the one property every downstream offset calculation depends on.
- **Placeholder scan:** none — every step has real, complete code.
- **Type consistency:** `sanitize_for_keyboard(text: str, layout: str = "en-us-qwerty") -> str` is defined once in Task 1 and used identically (no args beyond `text`, default layout) in Task 2 — no drift.
