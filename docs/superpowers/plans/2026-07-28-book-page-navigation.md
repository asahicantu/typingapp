# Book Page Navigation Implementation Plan (Stage D)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user in sequential book-reading mode jump around the book directly — skip forward a page, go back a page, or jump straight to the start — without those skipped pages ever being scored as typed text. This satisfies item #6 from the original feedback batch: "if a page is skipped, still track book progress, but do not count the words."

**Architecture:** Three new book-mode-only keybindings on `LessonScreen`: `Ctrl+Right` (next page), `Ctrl+Left` (previous page), `Ctrl+Home` (jump to book start). Each new action writes the new offset directly to `storage.update_book_progress(...)` (the same call `_persist_book_progress`/`_maybe_extend_text` already use) and then calls the existing `_start_lesson()` to rebuild the lesson from scratch at that offset. `_start_lesson()` already reads the book's current progress via `LessonEngine._build_sequential_book_lesson` → `storage.fetch_book_progress`, constructs a brand-new `Scorer` over the freshly-fetched chunk, and re-renders — so a page jump is "persist the new offset, then do what restarting the lesson already does," not a new fetch/render code path. Since a fresh `Scorer` never sees the skipped span, no keystrokes are recorded for it and the existing accuracy calculation (`Scorer._total_keys`/`_correct_keys`, already exactly "correct vs incorrect among characters actually typed") needs no changes — this stage only needs a regression test confirming that invariant explicitly once page-skip exists.

Page size reuses the already-defined `CHARS_PER_PAGE = 1200` constant in `engine/book_text.py` (same constant `page_info` already uses for page-number display) — no new page-size constant.

**Tech Stack:** Pure Python (offset arithmetic + existing storage/lesson-engine plumbing), Textual `Screen.BINDINGS` + `action_*` methods. No new dependencies.

## Global Constraints

- These three bindings are book-mode only (`self._book_id` non-empty) — a no-op outside book mode, following the exact pattern `action_finish_session` already uses (bound unconditionally in `BINDINGS`, but the `action_*` method checks `self._book_id` and returns immediately if empty). Do not gate visibility of the binding itself on book mode; gate the *behavior*.
- Do not modify `Scorer`, `Scorer.process_key`, or any accuracy/WPM calculation — the "skipped pages don't count" requirement falls out for free from never constructing a `Scorer` over the skipped span, not from any new scoring logic.
- Clamp offsets to `[0, total_chars]` — jumping "back" from page 1 must land on offset 0, not go negative; jumping "forward" past the last page must land on `total_chars` (which `_build_sequential_book_lesson` already treats as "book complete," returning `BOOK_COMPLETE_SENTINEL` — reuse that path rather than inventing a new end-of-book state).
- After a page jump, `_book_tick_counter` must reset to 0 (mirroring what `_start_lesson` already does implicitly by being the method that's re-invoked) so the periodic persist-tick timing doesn't carry over stale state from before the jump.
- Reuse `_start_lesson()` as-is for rebuilding the chunk/Scorer/render after a jump — do not duplicate its chunk-fetch-and-render logic in the new action methods.
- Follow this repo's existing test convention: plain pytest, Textual pilot-based screen tests for screen *behavior* (this repo has `tests/test_lesson_screen_finger_hint.py` as direct precedent for pilot-driving a `LessonScreen` instance and asserting on its state/labels).

---

### Task 1: Page-jump actions on `LessonScreen`

**Files:**
- Modify: `typingapp/screens/lesson.py`
- Test: `tests/test_lesson_screen_book_page_nav.py` (new file)

**Interfaces:**
- Consumes: `typingapp.engine.book_text.CHARS_PER_PAGE` (existing constant), `storage.update_book_progress(book_id, current_offset, updated_at)` (existing method), `storage.get_book(book_id)` (existing method, for `total_chars`), `self._start_lesson()` (existing method).
- Produces: `action_next_page()`, `action_previous_page()`, `action_book_home()` on `LessonScreen`, plus three new `BINDINGS` entries (`ctrl+right`, `ctrl+left`, `ctrl+home`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lesson_screen_book_page_nav.py
import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Label

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.book_text import CHARS_PER_PAGE
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen

BOOK_ID = "gutenberg:1"


def _make_app(storage, config):
    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = config
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LessonScreen())

    return TestApp()


def _make_storage_with_book(tmp_path, total_words=2000):
    storage = Storage(tmp_path / "test.db")
    # plenty of words so total_chars comfortably exceeds several pages
    full_text = " ".join(f"word{i}" for i in range(total_words))
    storage.upsert_book(
        book_id=BOOK_ID, source="gutenberg", title="T", author="A",
        language="en", full_text=full_text, cached_at="2026-07-28T10:00:00",
    )
    return storage


def test_next_page_advances_progress_by_one_page_without_scoring_skipped_text(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            start_offset = screen._book_raw_offset(0)
            assert start_offset == 0

            screen.action_next_page()
            await pilot.pause()

            new_offset = storage.fetch_book_progress(BOOK_ID)
            assert new_offset == start_offset + CHARS_PER_PAGE
            # a fresh Scorer was built for the new chunk -- no keystrokes recorded
            assert screen._scorer is not None
            assert screen._scorer.keystrokes == []
            assert screen._scorer.error_count == 0

    asyncio.run(run())
    storage.close()


def test_previous_page_moves_progress_back_by_one_page(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # jump forward two pages first so there's room to go back
            screen.action_next_page()
            await pilot.pause()
            screen.action_next_page()
            await pilot.pause()
            offset_after_two = storage.fetch_book_progress(BOOK_ID)

            screen.action_previous_page()
            await pilot.pause()

            offset_after_back = storage.fetch_book_progress(BOOK_ID)
            assert offset_after_back == offset_after_two - CHARS_PER_PAGE

    asyncio.run(run())
    storage.close()


def test_previous_page_clamps_at_zero_not_negative(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_previous_page()
            await pilot.pause()

            assert storage.fetch_book_progress(BOOK_ID) == 0

    asyncio.run(run())
    storage.close()


def test_book_home_jumps_to_offset_zero(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_next_page()
            await pilot.pause()
            screen.action_next_page()
            await pilot.pause()
            assert storage.fetch_book_progress(BOOK_ID) > 0

            screen.action_book_home()
            await pilot.pause()

            assert storage.fetch_book_progress(BOOK_ID) == 0

    asyncio.run(run())
    storage.close()


def test_next_page_past_end_of_book_shows_book_complete(tmp_path):
    storage = _make_storage_with_book(tmp_path, total_words=50)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            book = storage.get_book(BOOK_ID)
            total_chars = book["total_chars"]

            # jump repeatedly until we've gone past the end
            for _ in range(20):
                screen.action_next_page()
                await pilot.pause()
                if storage.fetch_book_progress(BOOK_ID) >= total_chars:
                    break

            assert storage.fetch_book_progress(BOOK_ID) >= total_chars
            assert screen._scorer is None

    asyncio.run(run())
    storage.close()


def test_page_nav_is_a_no_op_outside_book_mode(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)

    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = cfg
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LessonScreen(custom_text="hello world"))

    app = TestApp()

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            target_before = screen._scorer.target
            pos_before = screen._scorer.position

            screen.action_next_page()
            await pilot.pause()
            screen.action_previous_page()
            await pilot.pause()
            screen.action_book_home()
            await pilot.pause()

            # unchanged -- these actions must no-op when there's no book_id
            assert screen._scorer.target == target_before
            assert screen._scorer.position == pos_before

    asyncio.run(run())
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_book_page_nav.py -v`
Expected: FAIL — `AttributeError: 'LessonScreen' object has no attribute 'action_next_page'` (and similarly for the other two actions).

- [ ] **Step 3: Add the import and new bindings**

In `typingapp/screens/lesson.py`, add the import near the other `engine.book_text` import:

```python
from typingapp.engine.book_text import page_info, strip_heading_markup, CHARS_PER_PAGE
```

Add three new entries to `BINDINGS`, alongside the existing `ctrl+f`/`ctrl+s`/`ctrl+k` entries:

```python
    BINDINGS = [
        ("escape", "pause", "Pause"),
        ("ctrl+r", "restart", "Restart"),
        ("ctrl+q", "quit_lesson", "Quit"),
        ("ctrl+e", "go_menu", "Main Menu"),
        ("ctrl+f", "finish_session", "Finish Session"),
        ("ctrl+s", "toggle_strict_mode", "Toggle Strict Mode"),
        ("ctrl+k", "toggle_key_sounds", "Toggle Key Sounds"),
        ("ctrl+right", "next_page", "Next Page"),
        ("ctrl+left", "previous_page", "Previous Page"),
        ("ctrl+home", "book_home", "Book Start"),
    ]
```

- [ ] **Step 4: Add the three action methods**

Add these right after `action_finish_session` (matching that method's book-mode-gating style):

```python
    def _jump_to_book_offset(self, new_offset: int) -> None:
        app = self.app          # type: ignore[attr-defined]
        book = app.storage.get_book(self._book_id)
        total_chars = book["total_chars"] if book else 0
        clamped_offset = max(0, min(new_offset, total_chars))
        app.storage.update_book_progress(
            self._book_id, clamped_offset, datetime.datetime.now().isoformat()
        )
        if self._timer:
            self._timer.stop()
        self._book_tick_counter = 0
        self._start_lesson()

    def action_next_page(self) -> None:
        if not self._book_id:
            return
        current_offset = self._book_raw_offset(self._scorer.position if self._scorer else 0)
        self._jump_to_book_offset(current_offset + CHARS_PER_PAGE)

    def action_previous_page(self) -> None:
        if not self._book_id:
            return
        current_offset = self._book_raw_offset(self._scorer.position if self._scorer else 0)
        self._jump_to_book_offset(current_offset - CHARS_PER_PAGE)

    def action_book_home(self) -> None:
        if not self._book_id:
            return
        self._jump_to_book_offset(0)
```

**Note on `_book_raw_offset` when `self._scorer is None`:** this happens when the screen is already showing the "you've finished this book!" state (`BOOK_COMPLETE_SENTINEL`). In that case `self._book_chunk_start_offset` already equals `total_chars` (set by `_start_lesson`'s `BOOK_COMPLETE_SENTINEL` branch) and `_book_raw_offset(0)` correctly returns that same value, so `action_previous_page` still works sensibly (steps back one page from the end) even from the completed state. No special-casing needed.

- [ ] **Step 5: Update the footer hint text**

In `_footer_hint_text()`, add the new shortcuts to the book-mode line only (non-book mode has no use for them):

```python
    def _footer_hint_text(self) -> str:
        base = "ESC pause  ·  Ctrl+R restart  ·  Ctrl+S strict  ·  Ctrl+K sound  ·  Ctrl+Q quit  ·  Ctrl+E menu"
        if self._book_id:
            return ("ESC pause  ·  Ctrl+R restart  ·  Ctrl+F finish  ·  "
                    "Ctrl+←/→ page  ·  Ctrl+Home start  ·  "
                    "Ctrl+S strict  ·  Ctrl+K sound  ·  Ctrl+Q quit  ·  Ctrl+E menu")
        return base
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_book_page_nav.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 7: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add typingapp/screens/lesson.py tests/test_lesson_screen_book_page_nav.py
git commit -m "feat: add Ctrl+Left/Right/Home page navigation in book mode"
```

---

### Task 2: Regression test confirming skipped pages never affect accuracy

**Files:**
- Test: `tests/test_lesson_screen_book_page_nav.py` (append to the file from Task 1)

**Interfaces:**
- Consumes: nothing new — this task is purely a regression test using the actions built in Task 1, confirming the "skip a page, type some more, accuracy reflects only the typed portion" invariant called out explicitly in the design doc as a risk worth testing directly rather than just trusting by inspection.

- [ ] **Step 1: Write the test**

```python
# append to tests/test_lesson_screen_book_page_nav.py

def test_accuracy_after_page_skip_reflects_only_typed_text(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen

            # skip a page before typing anything
            screen.action_next_page()
            await pilot.pause()

            target = screen._scorer.target
            # type the first few characters correctly
            for ch in target[:5]:
                await pilot.press(ch if ch != " " else "space")
            await pilot.pause()

            assert screen._scorer.error_count == 0
            assert screen._scorer.accuracy == 100.0
            assert len(screen._scorer.keystrokes) == 5

    asyncio.run(run())
    storage.close()
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `pytest tests/test_lesson_screen_book_page_nav.py -k accuracy_after_page_skip -v`
Expected: PASS — confirms `Scorer` for the post-skip chunk starts completely fresh (0 keystrokes, 100% accuracy before any typing error), i.e. the skipped span was never scored.

- [ ] **Step 3: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_lesson_screen_book_page_nav.py
git commit -m "test: confirm page-skip never affects typing accuracy"
```

---

### Task 3: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only).

- [ ] **Step 1: Add a new Key Invariant**, appended at the end of the Key Invariants section:

```markdown
- **Book page navigation (`Ctrl+Right`/`Ctrl+Left`/`Ctrl+Home`, book mode only) jumps the reading offset without ever scoring the skipped span.** `LessonScreen.action_next_page`/`action_previous_page`/`action_book_home` compute a new absolute offset (±`book_text.CHARS_PER_PAGE`, or `0` for Home), clamp it to `[0, total_chars]` via `_jump_to_book_offset`, persist it with `storage.update_book_progress`, then call the existing `_start_lesson()` — which already knows how to fetch-a-chunk-from-offset and build a fresh `Scorer` around it. Because `_start_lesson()` always constructs a brand-new `Scorer`, the skipped span never appears in `Scorer.keystrokes`/`_total_keys`, so accuracy/WPM naturally reflect only text actually typed — no changes to `Scorer` itself were needed for "skipped pages don't count." A forward jump landing at or past `total_chars` reuses the existing `BOOK_COMPLETE_SENTINEL` path (same as reading to the natural end of the book) rather than a separate end-of-book state. These three bindings are declared unconditionally in `LessonScreen.BINDINGS` (same as `Ctrl+F`/`action_finish_session`) but no-op when `self._book_id` is empty — gating is in the `action_*` method, not the binding's visibility.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document book page navigation and its skip-doesn't-score invariant"
```

## Self-Review Notes

- **Spec coverage:** covers all of Stage D (item #6 from the original feedback batch) — forward/backward page jump, jump-to-start, and the "skipped pages update progress but aren't scored" requirement, reusing `CHARS_PER_PAGE`/`book_text.py`/`_start_lesson()` infrastructure exactly as the design doc specified rather than building a parallel fetch/render path.
- **Placeholder scan:** none — every step has complete, ready-to-use code.
- **Type consistency:** `_jump_to_book_offset(new_offset: int) -> None` is the single new private helper; all three public actions funnel through it, so offset-clamping logic exists in exactly one place.
- **Risk called out explicitly and tested:** the design doc flagged "confirm the accuracy invariant holds once page-skip exists" as a regression risk — Task 2 is a dedicated test for exactly that, not left as an assumption.
