# Chunk Navigation + Inline Dictionary Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Ctrl+Up/Ctrl+Down within-chunk navigation to book-reading mode, and replace the modal dictionary popup with an inline, focusable, scrollable panel available in every content type.

**Architecture:** Two independent additions to `typingapp/screens/lesson.py`. (A) Ctrl+Up/Down set `Scorer.position` directly to `0`/`len(target)` with no new `Scorer`, no storage write — reusing the existing render/scroll pipeline. (B) A new always-present `#dictionary-panel` (`VerticalScroll` + `Static`) replaces `DictionaryPopupScreen` entirely; its content persists across `_start_lesson()` rebuilds via two new `LessonScreen` instance attributes, and focus moves in/out of it via existing Textual focus APIs (`self.focused`, `widget.has_focus`, `self.set_focus`).

**Tech Stack:** Python, Textual (stdlib `sqlite3` for storage, unrelated to this change).

## Global Constraints

- Follow `CLAUDE.md`'s existing invariants for this codebase, in particular:
  - `engine/` stays pure Python, no Textual dependency (this plan touches no `engine/` files).
  - Dictionary lookups keep their `@work(exclusive=True, thread=True, group="dictionary-lookup")` worker pattern, `_dictionary_lookup_in_progress` guard, and never-let-`fetch_definition`-exceptions-crash-the-worker behavior (wrap in `try/except Exception` before calling `self.app.call_from_thread`) — unchanged from today's code.
  - Tests that mock `fetch_definition` must patch `typingapp.screens.lesson.fetch_definition` (the call site's import), not `typingapp.engine.dictionary.fetch_definition` — this bit the project before (see CLAUDE.md's "Testing gotcha" invariant).
  - Ctrl+Up/Down (chunk nav) must be book-mode-gated no-ops (`if not self._book_id: return`), exactly like the existing `action_next_page`/`action_previous_page`/`action_book_home`.
  - Run `pytest -q` after every task; all existing tests must keep passing (247 pass as of the start of this plan).
- Design spec: `docs/superpowers/specs/2026-08-01-book-nav-and-inline-dictionary-design.md`. This plan implements that spec exactly; consult it for the "why" behind any decision below.
- Work happens directly on `master` in this session (no worktree requested for this task).

---

## Task 1: Ctrl+Up/Ctrl+Down chunk-start/chunk-end navigation

**Files:**
- Modify: `typingapp/screens/lesson.py` (`BINDINGS` list at line 31, new methods near `action_book_home` at line ~565)
- Test: `tests/test_lesson_screen_book_page_nav.py`

**Interfaces:**
- Produces: `LessonScreen.action_jump_chunk_start(self) -> None`, `LessonScreen.action_jump_chunk_end(self) -> None` — both book-mode-gated no-ops (`if not self._book_id: return`), otherwise set `self._scorer.position` and call `self._render_text()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lesson_screen_book_page_nav.py` (it already has `_make_app`/`_make_storage_with_book`/`BOOK_ID` helpers at the top — reuse them, do not duplicate):

```python
def test_ctrl_up_jumps_to_start_of_current_chunk_without_scoring(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            s = screen._scorer
            # move partway into the chunk without typing (position is a plain attribute)
            s.position = 20
            stored_before = storage.fetch_book_progress(BOOK_ID)

            screen.action_jump_chunk_start()
            await pilot.pause()

            assert screen._scorer.position == 0
            # no keystrokes/errors recorded, no new Scorer built (same instance)
            assert screen._scorer is s
            assert screen._scorer.keystrokes == []
            assert screen._scorer.error_count == 0
            # chunk-internal navigation does not touch the persisted book offset
            assert storage.fetch_book_progress(BOOK_ID) == stored_before

    asyncio.run(run())
    storage.close()


def test_ctrl_down_jumps_to_end_of_current_chunk_without_scoring(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            s = screen._scorer
            chunk_len = len(s.target)

            screen.action_jump_chunk_end()
            await pilot.pause()

            assert screen._scorer.position == chunk_len
            assert screen._scorer is s
            assert screen._scorer.keystrokes == []
            assert screen._scorer.error_count == 0
            assert screen._scorer.is_complete

    asyncio.run(run())
    storage.close()


def test_ctrl_down_then_tick_extends_text_like_normal_completion(tmp_path):
    # action_jump_chunk_end makes Scorer.is_complete true, exactly like typing to the
    # end of a chunk normally would -- the existing _tick()/_maybe_extend_text flow
    # must pick this up and fetch more text on the next tick with no special-casing.
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            chunk_len_before = len(screen._scorer.target)

            screen.action_jump_chunk_end()
            screen._tick()
            await pilot.pause()

            assert len(screen._scorer.target) > chunk_len_before

    asyncio.run(run())
    storage.close()


def test_chunk_nav_is_a_no_op_outside_book_mode(tmp_path):
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
            pos_before = screen._scorer.position

            screen.action_jump_chunk_start()
            await pilot.pause()
            screen.action_jump_chunk_end()
            await pilot.pause()

            assert screen._scorer.position == pos_before

    asyncio.run(run())
    storage.close()


def test_ctrl_up_down_keybindings_invoke_the_actions(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            chunk_len = len(screen._scorer.target)

            await pilot.press("ctrl+down")
            await pilot.pause()
            assert screen._scorer.position == chunk_len

            await pilot.press("ctrl+up")
            await pilot.pause()
            assert screen._scorer.position == 0

    asyncio.run(run())
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_book_page_nav.py -k "chunk" -v`
Expected: FAIL with `AttributeError: 'LessonScreen' object has no attribute 'action_jump_chunk_start'` (and similarly for `action_jump_chunk_end`), and the keybinding test fails because `ctrl+up`/`ctrl+down` aren't bound.

- [ ] **Step 3: Add the bindings and implement the actions**

In `typingapp/screens/lesson.py`, add two entries to `BINDINGS` (after the existing `ctrl+home` entry, before `ctrl+d`, at line 41):

```python
        ("ctrl+home", "book_home", "Book Start"),
        ("ctrl+up", "jump_chunk_start", "Chunk Start"),
        ("ctrl+down", "jump_chunk_end", "Chunk End"),
        ("ctrl+d", "show_definition", "Dictionary"),
```

Add the two new action methods immediately after `action_book_home` (currently ending at line 568):

```python
    def action_jump_chunk_start(self) -> None:
        if not self._book_id or self._scorer is None:
            return
        self._scorer.position = 0
        self._render_text()

    def action_jump_chunk_end(self) -> None:
        if not self._book_id or self._scorer is None:
            return
        self._scorer.position = len(self._scorer.target)
        self._render_text()
```

`_render_text()` already calls `_scroll_to_cursor(pos, len(target))` internally (both the book-mode and non-book branches do this — see line 312 and line 344), and `_scroll_to_cursor` already special-cases `position == 0` to scroll straight to the top (from the earlier page-jump scroll fix) — so no separate scroll call is needed here for the start case. For the end case, the ratio-based scroll math in `_scroll_to_cursor` naturally computes `progress_ratio = 1.0`, landing near the bottom of the rendered content.

- [ ] **Step 4: Update the footer hint text**

In `_footer_hint_text()` (line 158), add the new shortcut to the book-mode string only (non-book mode has no chunk concept exposed to the user):

```python
    def _footer_hint_text(self) -> str:
        base = ("ESC pause  ·  Ctrl+R restart  ·  Ctrl+S strict  ·  Ctrl+K sound  ·  "
                "Ctrl+D dictionary  ·  Ctrl+Q quit  ·  Ctrl+E menu")
        if self._book_id:
            return ("ESC pause  ·  Ctrl+R restart  ·  Ctrl+F finish  ·  "
                    "Ctrl+←/→ page  ·  Ctrl+↑/↓ chunk start/end  ·  Ctrl+Home start  ·  "
                    "Ctrl+S strict  ·  Ctrl+K sound  ·  Ctrl+D dictionary  ·  "
                    "Ctrl+Q quit  ·  Ctrl+E menu")
        return base
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_book_page_nav.py -v`
Expected: all pass, including the 5 new tests.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: all 252 tests pass (247 existing + 5 new).

- [ ] **Step 7: Commit**

```bash
git add typingapp/screens/lesson.py tests/test_lesson_screen_book_page_nav.py
git commit -m "$(cat <<'EOF'
feat: add Ctrl+Up/Down chunk-start/end navigation in book mode

Jumps the cursor to the start/end of the currently-loaded chunk without
building a new Scorer or touching the persisted book offset -- a
finer-grained sibling to the existing Ctrl+Left/Right page jump, scoped
to in-memory chunk bounds rather than absolute book offsets. Same
skip-without-scoring mechanics: the skipped span is never added to
keystrokes/error_count. Ctrl+Down naturally makes Scorer.is_complete
true, which the existing tick/extension flow already handles with no
new branching.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Inline dictionary panel widget + persisted panel state

**Files:**
- Modify: `typingapp/screens/lesson.py` (`compose()` at line 85, `__init__` at line 45, `_start_lesson()` at line 107)
- Modify: `typingapp/app.tcss` (replace the `DictionaryPopupScreen`/`#dictionary-popup-body` rules at lines 129-149)
- Test: `tests/test_lesson_screen_dictionary.py` (this task only adds panel-existence/persistence tests; Task 3 rewrites the lookup-behavior tests)

**Interfaces:**
- Consumes: nothing new from Task 1.
- Produces: `#dictionary-panel` (a `VerticalScroll`, `can_focus=True` by Textual default) containing `Static#dictionary-panel-content`, present in `compose()` for every `LessonScreen` instance (not book-mode-gated — used by all content types per the design spec). `LessonScreen._dictionary_word: str` and `LessonScreen._dictionary_definition_markup: str`, both initialized to `""` in `__init__` and **not** reset inside `_start_lesson()`. New method `LessonScreen._render_dictionary_panel(self) -> None` that writes `self._dictionary_definition_markup` into `#dictionary-panel-content` (or clears it) based on whether `self._dictionary_word` is empty, called once at the end of `_start_lesson()` and (in Task 3) after every panel-content change.

- [ ] **Step 1: Write the failing test**

Add a new test to `tests/test_lesson_screen_dictionary.py`. First, since this file currently imports `DictionaryPopupScreen` (which Task 3 will delete), leave the existing imports/tests untouched in this task — just append:

```python
def test_dictionary_panel_exists_and_starts_empty(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            panel = screen.query_one("#dictionary-panel")
            content = screen.query_one("#dictionary-panel-content", Static)
            assert panel is not None
            assert str(content.content) == ""

    asyncio.run(run())
    storage.close()


def test_dictionary_panel_content_survives_start_lesson_rebuild(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # simulate an already-populated panel (Task 3 wires the real lookup flow;
            # here we just verify _start_lesson()'s rebuild doesn't blank persisted state)
            screen._dictionary_word = "fox"
            screen._dictionary_definition_markup = "(noun) a fast animal"
            screen._render_dictionary_panel()
            await pilot.pause()

            screen._start_lesson()
            await pilot.pause()

            assert screen._dictionary_word == "fox"
            content = screen.query_one("#dictionary-panel-content", Static)
            assert "fast animal" in str(content.content)

    asyncio.run(run())
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_dictionary.py -k "panel" -v`
Expected: FAIL — `#dictionary-panel`/`#dictionary-panel-content` don't exist yet (`NoMatches` from `query_one`), and `_render_dictionary_panel`/`_dictionary_word`/`_dictionary_definition_markup` don't exist.

- [ ] **Step 3: Add the panel to `compose()`**

In `typingapp/screens/lesson.py`, modify `compose()` (currently lines 85-102) to insert the new panel between `#text-scroll` and `#hint-bar`:

```python
    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="stats-bar"):
                yield Label("⚡ WPM: ", classes="stat-label")
                yield Label("0", id="wpm-val", classes="stat-value wpm-value")
                yield Label("  ✓ ACC: ", classes="stat-label")
                yield Label("100%", id="acc-val", classes="stat-value acc-value")
                yield Label("  ⏱ TIME: ", classes="stat-label")
                yield Label("0:00", id="time-val", classes="stat-value time-value")
                yield Label("  ✗ ERR: ", classes="stat-label")
                yield Label("0", id="err-val", classes="stat-value err-value")
            yield Label("", id="finger-hint-val", classes="stat-label finger-hint-value")
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            yield Label("", id="book-progress-val", classes="stat-label")
            with VerticalScroll(id="text-scroll"):
                yield Static("", id="text-display")
            with VerticalScroll(id="dictionary-panel"):
                yield Static("", id="dictionary-panel-content")
            yield Label("", id="hint-bar", classes="hint-bar")
            yield Static("ESC pause  ·  Ctrl+R restart  ·  Ctrl+Q quit  ·  Ctrl+E menu", id="footer-hint", classes="stat-label")
```

- [ ] **Step 4: Add persisted panel state and the render helper**

In `__init__` (currently lines 45-57), add the two new attributes at the end:

```python
    def __init__(self, custom_text: str = "") -> None:
        super().__init__()
        self._custom_text = custom_text
        self._scorer: Scorer | None = None
        self._timer: Timer | None = None
        self._paused = False
        self._book_id = ""
        self._book_chunk_start_offset = 0
        self._book_total_chars = 0
        self._book_tick_counter = 0
        self._book_chunk_spans: list[tuple[str, int, int]] = []
        self._missed_words: set[str] = set()
        self._dictionary_lookup_in_progress = False
        self._dictionary_word = ""
        self._dictionary_definition_markup = ""
```

Add a new method anywhere near the other `_update_*_label` helpers (e.g. right after `_update_finger_hint_label`, which currently ends at line 198):

```python
    def _render_dictionary_panel(self) -> None:
        content = self.query_one("#dictionary-panel-content", Static)
        content.update(self._dictionary_definition_markup)
```

Note: this does not toggle visibility/CSS classes yet — that's deferred to Task 3, since a meaningful "collapsed vs expanded" visual only matters once real lookups populate it. For now the panel exists but stays visually empty when `_dictionary_definition_markup` is `""`.

- [ ] **Step 5: Call the render helper from `_start_lesson()`**

In `_start_lesson()` (currently lines 107-148), add a call to `self._render_dictionary_panel()` near the end, right after the existing `self._update_book_progress_label()` call (line 144) — and also on the early-return `BOOK_COMPLETE_SENTINEL` path (after line 129's `self._update_book_progress_label()`), so the panel's persisted content still renders even when a book is finished:

```python
        if text == BOOK_COMPLETE_SENTINEL:
            self._scorer = None
            self._book_chunk_spans = []
            self.query_one("#text-display", Static).update("🎉 You've finished this book!")
            self.query_one("#hint-bar", Label).update("")
            self._update_book_progress_label()
            self._update_finger_hint_label()
            self._render_dictionary_panel()
            return

        # ... (unchanged middle of the method) ...

        self._scorer = Scorer(text, strict_mode=app.config.strict_mode)
        self._scorer.start()
        self._render_text()
        self._update_finger_hint_label()
        self._timer = self.set_interval(0.25, self._tick)
        self._update_book_progress_label()
        self._render_dictionary_panel()
        self.query_one("#footer-hint", Static).update(self._footer_hint_text())
        reason = app.lesson_engine.last_fallback_reason
        if reason:
            self.query_one("#hint-bar", Label).update(f"⚠ {reason}")
```

- [ ] **Step 6: Add minimal CSS for the panel**

In `typingapp/app.tcss`, replace the `DictionaryPopupScreen`/`#dictionary-popup-body`/`#dictionary-definition` rules (lines 129-149) with:

```css
#dictionary-panel {
    border: tall #333333;
    padding: 0 2;
    margin: 0 0 1 0;
    height: auto;
    max-height: 30%;
}

#dictionary-panel:focus {
    border: tall #43b0f1;
}

#dictionary-panel-content {
    color: #ffffff;
    height: auto;
}
```

This is a deliberate leftover from Task 2: the panel always shows its border even when empty. Task 3 (which wires up real show/clear behavior) will note this is acceptable for now since the content is blank either way — but flag it for Step 6 review below.

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_dictionary.py -k "panel" -v`
Expected: both new tests pass. (Do NOT run the full dictionary test file yet — the old popup-based tests still reference `DictionaryPopupScreen` and `action_show_definition`'s old behavior, which Task 3 rewrites. They should still be passing right now since Task 2 hasn't touched `action_show_definition` yet.)

Run: `pytest tests/test_lesson_screen_dictionary.py -v`
Expected: all pass (old popup tests unaffected since `DictionaryPopupScreen`/`action_show_definition` are untouched by this task).

- [ ] **Step 8: Run the full suite**

Run: `pytest -q`
Expected: all 254 tests pass (252 from Task 1 + 2 new).

- [ ] **Step 9: Commit**

```bash
git add typingapp/screens/lesson.py typingapp/app.tcss tests/test_lesson_screen_dictionary.py
git commit -m "$(cat <<'EOF'
feat: add inline dictionary panel widget alongside the existing popup

Adds #dictionary-panel (a focusable, scrollable VerticalScroll) to
LessonScreen's layout, plus persisted _dictionary_word/
_dictionary_definition_markup state that survives _start_lesson()
rebuilds (page jumps, chunk extensions, restarts). The panel exists
and renders its persisted content but nothing populates it yet --
action_show_definition and DictionaryPopupScreen are untouched in this
commit; the next commit rewires the lookup flow onto this panel and
removes the popup.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire Ctrl+D/Escape/Ctrl+Shift+D onto the panel; delete the popup

**Files:**
- Modify: `typingapp/screens/lesson.py` (`BINDINGS`, `action_show_definition` and its helpers at lines 586-624, `action_pause` at line 494)
- Modify: `typingapp/app.tcss` (panel visibility CSS from Task 2 — add a `-hidden` class rule)
- Delete: `typingapp/screens/dictionary_popup.py`
- Rewrite: `tests/test_lesson_screen_dictionary.py` (replace all popup-based assertions with panel-based ones)
- Test: `tests/test_lesson_screen_dictionary.py`

**Interfaces:**
- Consumes: `#dictionary-panel`/`#dictionary-panel-content`, `_render_dictionary_panel()`, `_dictionary_word`, `_dictionary_definition_markup` from Task 2.
- Produces: `LessonScreen.action_clear_definition(self) -> None` (new, bound to `ctrl+shift+d`). `action_show_definition` reworked per the design spec's word-differs/word-same branching. `action_pause` reworked to check panel focus first.

- [ ] **Step 1: Rewrite `tests/test_lesson_screen_dictionary.py` with failing panel-based tests**

Replace the entire file contents:

```python
import asyncio
from pathlib import Path
from unittest.mock import patch
from textual.app import App
from textual.widgets import Static

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen


def _make_app(storage, config, custom_text="the quick fox"):
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
            self.push_screen(LessonScreen(custom_text=custom_text))

    return TestApp()


async def _wait_for_panel_content(pilot, screen, expected_substring, attempts=50):
    for _ in range(attempts):
        await pilot.pause()
        content = screen.query_one("#dictionary-panel-content", Static)
        if expected_substring in str(content.content):
            return True
        await asyncio.sleep(0.05)
    return False


def test_ctrl_d_populates_panel_with_definition_and_keeps_typing_focus(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "fast animal")
                assert found
                assert screen._dictionary_word == "fox"
                # focus stays on the typing area -- panel is NOT focused after a fresh lookup
                panel = screen.query_one("#dictionary-panel")
                assert not panel.has_focus

    asyncio.run(run())
    storage.close()


def test_ctrl_d_shows_no_definition_found_message(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value=None):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "No definition found.")
                assert found

    asyncio.run(run())
    storage.close()


def test_ctrl_d_shows_unavailable_message_for_non_english_language(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, language="es")
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(
                    pilot, screen, "Dictionary not available for this language yet"
                )
                assert found
                mock_fetch.assert_not_called()

    asyncio.run(run())
    storage.close()


def test_second_ctrl_d_on_same_word_focuses_panel_instead_of_relookup(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "fast animal")
                assert found
                mock_fetch.assert_called_once()

                # cursor hasn't moved -- second Ctrl+D on the SAME word focuses the panel
                # instead of re-fetching
                await pilot.press("ctrl+d")
                await pilot.pause()
                panel = screen.query_one("#dictionary-panel")
                assert panel.has_focus
                mock_fetch.assert_called_once()  # still only once -- no re-fetch

    asyncio.run(run())
    storage.close()


def test_ctrl_d_on_different_word_relooksup_instead_of_focusing(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg, custom_text="the quick fox")

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")  # looks up "the" (cursor starts at position 0)
                found = await _wait_for_panel_content(pilot, screen, "a definition")
                assert found
                assert screen._dictionary_word == "the"
                mock_fetch.assert_called_once()

                # move the cursor onto a different word, then Ctrl+D again
                screen._scorer.position = screen._scorer.target.index("quick")
                await pilot.press("ctrl+d")
                await pilot.pause()
                assert screen._dictionary_word == "quick"
                assert mock_fetch.call_count == 2
                panel = screen.query_one("#dictionary-panel")
                assert not panel.has_focus

    asyncio.run(run())
    storage.close()


def test_escape_while_panel_focused_returns_focus_without_pausing(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                await _wait_for_panel_content(pilot, screen, "a definition")
                await pilot.press("ctrl+d")  # second press on same word -> focuses panel
                await pilot.pause()
                panel = screen.query_one("#dictionary-panel")
                assert panel.has_focus

                await pilot.press("escape")
                await pilot.pause()

                assert not panel.has_focus
                assert not screen._paused
                # definition content is untouched
                content = screen.query_one("#dictionary-panel-content", Static)
                assert "a definition" in str(content.content)

    asyncio.run(run())
    storage.close()


def test_escape_while_typing_focused_still_pauses(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert not screen._paused

            await pilot.press("escape")
            await pilot.pause()

            assert screen._paused

    asyncio.run(run())
    storage.close()


def test_ctrl_shift_d_clears_panel_and_returns_focus(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                await _wait_for_panel_content(pilot, screen, "a definition")
                await pilot.press("ctrl+d")  # focus the panel
                await pilot.pause()
                panel = screen.query_one("#dictionary-panel")
                assert panel.has_focus

                await pilot.press("ctrl+shift+d")
                await pilot.pause()

                assert screen._dictionary_word == ""
                content = screen.query_one("#dictionary-panel-content", Static)
                assert str(content.content) == ""
                assert not panel.has_focus

    asyncio.run(run())
    storage.close()


def test_ctrl_d_strips_punctuation_before_lookup(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg, custom_text="times, and wisdom")

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a moment") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "a moment")
                assert found
                mock_fetch.assert_called_once()
                called_word = mock_fetch.call_args[0][0]
                assert called_word == "times"
                # the panel's stored display word keeps the original, unstripped form
                assert screen._dictionary_word == "times,"

    asyncio.run(run())
    storage.close()


def test_ctrl_d_is_a_no_op_when_lesson_is_complete(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                target = screen._scorer.target
                for ch in target:
                    await pilot.press(ch if ch != " " else "space")
                await pilot.pause()
                await pilot.press("ctrl+d")
                await pilot.pause()
                assert screen._dictionary_word == ""
                mock_fetch.assert_not_called()

    asyncio.run(run())
    storage.close()


def test_ctrl_d_survives_fetch_definition_raising_and_resets_in_progress_flag(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            with patch("typingapp.screens.lesson.fetch_definition", side_effect=RuntimeError("boom")):
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "No definition found.")
                assert found
                assert not screen._dictionary_lookup_in_progress

            # move to a different word so this is treated as a fresh lookup, not a focus-toggle
            screen._dictionary_word = ""  # force re-lookup path deterministically
            with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal") as mock_fetch:
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "fast animal")
                assert found
                mock_fetch.assert_called_once()

    asyncio.run(run())
    storage.close()


def test_dictionary_panel_persists_across_book_page_jump(tmp_path):
    from typingapp.engine.book_text import CHARS_PER_PAGE

    BOOK_ID = "gutenberg:1"
    storage = Storage(tmp_path / "test.db")
    words = [f"word{i}." if i % 8 == 7 else f"word{i}" for i in range(2000)]
    storage.upsert_book(
        book_id=BOOK_ID, source="gutenberg", title="T", author="A",
        language="en", full_text=" ".join(words), cached_at="2026-07-28T10:00:00",
    )
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "a definition")
                assert found

                screen.action_next_page()
                await pilot.pause()

                content = screen.query_one("#dictionary-panel-content", Static)
                assert "a definition" in str(content.content)

    asyncio.run(run())
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_dictionary.py -v`
Expected: FAIL across most tests — `action_show_definition` still pushes `DictionaryPopupScreen` (which the test file no longer imports/references), so `#dictionary-panel-content` never gets the definition text.

- [ ] **Step 3: Delete the popup module**

```bash
rm typingapp/screens/dictionary_popup.py
```

- [ ] **Step 4: Rewrite `action_show_definition` and its helpers**

In `typingapp/screens/lesson.py`, remove the import (line 22: `from typingapp.screens.dictionary_popup import DictionaryPopupScreen`).

Replace `action_show_definition`, `_lookup_definition`, and `_show_definition_popup` (currently lines 586-624) with:

```python
    def action_show_definition(self) -> None:
        s = self._scorer
        if s is None or s.is_complete:
            return
        if self._dictionary_lookup_in_progress:
            return
        app = self.app      # type: ignore[attr-defined]
        word = current_word_at(s.target, s.position)
        if not word:
            lookahead = s.position
            while lookahead < len(s.target) and s.target[lookahead].isspace():
                lookahead += 1
            word = current_word_at(s.target, lookahead)
        if not word:
            return
        lookup_word = normalize_mistake_word(word)
        if not lookup_word:
            return

        if lookup_word == self._dictionary_word_key and self._dictionary_word:
            # same word as what's already shown -- focus the panel to scroll it
            # instead of re-fetching.
            self.query_one("#dictionary-panel").focus()
            return

        language = app.config.language
        if language != "en":
            self._dictionary_word = word
            self._dictionary_word_key = lookup_word
            self._dictionary_definition_markup = "Dictionary not available for this language yet"
            self._render_dictionary_panel()
            return

        self._dictionary_lookup_in_progress = True
        self._lookup_definition(word, lookup_word, language)

    @work(exclusive=True, thread=True, group="dictionary-lookup")
    def _lookup_definition(self, display_word: str, lookup_word: str, language: str) -> None:
        try:
            definition = fetch_definition(lookup_word, language)
        except Exception:
            definition = None
        self.app.call_from_thread(self._show_definition_in_panel, display_word, lookup_word, definition)

    def _show_definition_in_panel(self, word: str, lookup_word: str, definition: str | None) -> None:
        self._dictionary_lookup_in_progress = False
        self._dictionary_word = word
        self._dictionary_word_key = lookup_word
        self._dictionary_definition_markup = definition or "No definition found."
        self._render_dictionary_panel()

    def action_clear_definition(self) -> None:
        self._dictionary_word = ""
        self._dictionary_word_key = ""
        self._dictionary_definition_markup = ""
        self._render_dictionary_panel()
        panel = self.query_one("#dictionary-panel")
        if panel.has_focus:
            self.query_one("#text-scroll").focus()
```

Note the new `self._dictionary_word_key` attribute — this is needed because `self._dictionary_word` stores the **display** word (original casing/punctuation, e.g. `"times,"`), but the same-word comparison in `action_show_definition` must compare against the **normalized** lookup form (e.g. `"times"`), matching what `normalize_mistake_word` produces for the cursor's current word. Using the raw display word for comparison would make `"times,"` and `"times"` (if the cursor drifted by one character) look like different words when they're the same lookup. Add this to `__init__` alongside the two attributes from Task 2:

```python
        self._dictionary_word = ""
        self._dictionary_word_key = ""
        self._dictionary_definition_markup = ""
```

- [ ] **Step 5: Add the `ctrl+shift+d` binding**

In `BINDINGS`, add after the `ctrl+d` entry:

```python
        ("ctrl+d", "show_definition", "Dictionary"),
        ("ctrl+shift+d", "clear_definition", "Clear Dictionary"),
```

- [ ] **Step 6: Make `action_pause` check panel focus first**

Replace `action_pause` (currently lines 494-497):

```python
    def action_pause(self) -> None:
        panel = self.query_one("#dictionary-panel")
        if panel.has_focus:
            self.query_one("#text-scroll").focus()
            return
        self._paused = not self._paused
        hint = self.query_one("#hint-bar", Label)
        hint.update("⏸ PAUSED — press ESC to resume" if self._paused else "")
```

- [ ] **Step 7: Update the footer hint text for the clear shortcut**

In `_footer_hint_text()`, add `Ctrl+Shift+D clear` to both strings:

```python
    def _footer_hint_text(self) -> str:
        base = ("ESC pause  ·  Ctrl+R restart  ·  Ctrl+S strict  ·  Ctrl+K sound  ·  "
                "Ctrl+D dictionary  ·  Ctrl+Shift+D clear  ·  Ctrl+Q quit  ·  Ctrl+E menu")
        if self._book_id:
            return ("ESC pause  ·  Ctrl+R restart  ·  Ctrl+F finish  ·  "
                    "Ctrl+←/→ page  ·  Ctrl+↑/↓ chunk start/end  ·  Ctrl+Home start  ·  "
                    "Ctrl+S strict  ·  Ctrl+K sound  ·  Ctrl+D dictionary  ·  Ctrl+Shift+D clear  ·  "
                    "Ctrl+Q quit  ·  Ctrl+E menu")
        return base
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_dictionary.py -v`
Expected: all pass.

- [ ] **Step 9: Check for other references to the deleted popup module**

```bash
grep -rn "dictionary_popup\|DictionaryPopupScreen" typingapp/ tests/ CLAUDE.md
```

Expected: no matches. If `CLAUDE.md` has an invariant bullet mentioning `DictionaryPopupScreen` being "the first `ModalScreen` use in this codebase," update or remove that bullet in Task 4 (documentation task) rather than here — just confirm no *code* references remain.

- [ ] **Step 10: Run the full suite**

Run: `pytest -q`
Expected: all tests pass. Count should be 254 (from Task 2) minus the original 8 popup-based tests in the old `tests/test_lesson_screen_dictionary.py` plus the 12 rewritten tests in this task's replacement file = net addition of 4, so 258 total (adjust expectation if the actual pre-Task-3 count differs — verify by running `pytest -q --collect-only | tail -5` before this step if unsure).

- [ ] **Step 11: Commit**

```bash
git add typingapp/screens/lesson.py tests/test_lesson_screen_dictionary.py
git rm typingapp/screens/dictionary_popup.py
git commit -m "$(cat <<'EOF'
feat: replace modal dictionary popup with inline, focusable panel

Ctrl+D now looks up the word under the cursor and shows it inline in
#dictionary-panel instead of pushing a ModalScreen -- focus stays on
the typing area so the user can keep typing while reading. A second
Ctrl+D on the SAME word (tracked via the new _dictionary_word_key,
compared against the normalized lookup form) focuses the panel instead
of re-fetching, so arrow keys can scroll a long definition; Ctrl+D on a
DIFFERENT word always re-looks-up. Escape returns focus from the panel
to typing without pausing (action_pause now checks panel focus first);
Escape from the typing area still pauses as before. New Ctrl+Shift+D
clears the panel and returns focus if needed. Definition content
persists across _start_lesson() rebuilds (page jumps, restarts) per
the design spec, since it's a small UI convenience state, not lesson
progress. DictionaryPopupScreen is deleted -- this panel now handles
every content type, not just book mode.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Documentation

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing (docs-only task).
- Produces: nothing (docs-only task).

- [ ] **Step 1: Update the `typingapp/screens/` bullet**

Find the line in `CLAUDE.md` describing `typingapp/screens/` (currently includes: `` `typingapp/screens/dictionary_popup.py` (`DictionaryPopupScreen`) is the exception to this push/pop-of-full-screens pattern — see the `ModalScreen` invariant below. ``). Remove that clause since the module no longer exists — screens remain a pure push/pop stack again with no exception.

- [ ] **Step 2: Remove or rewrite invariants that reference the deleted popup**

Search `CLAUDE.md` for `DictionaryPopupScreen`, `ModalScreen`, and `dictionary_popup.py` and either remove those bullets (if fully superseded) or rewrite them to describe the new inline-panel architecture. Add a new invariant bullet documenting:

- `#dictionary-panel`'s content (`_dictionary_word`/`_dictionary_word_key`/`_dictionary_definition_markup`) is deliberately **not** reset in `_start_lesson()`, unlike `_dictionary_lookup_in_progress` (which IS reset every lesson start, since an in-flight lookup from a previous chunk is meaningless after a rebuild) — the definition a user looked up stays visible across page jumps/restarts until they explicitly clear it (`Ctrl+Shift+D`) or leave the lesson.
- `action_show_definition`'s same-word-focuses / different-word-relooks-up branching, and why `_dictionary_word_key` (normalized) is compared rather than `_dictionary_word` (display form with original casing/punctuation).
- `action_pause`'s panel-focus check: Escape is context-dependent (defocus-only when `#dictionary-panel` has focus, pause otherwise) rather than a single static binding, since Textual's `BINDINGS` list can't express "same key, different action depending on which widget has focus" declaratively — the branching lives inside the handler.
- Ctrl+Up/Down (`action_jump_chunk_start`/`action_jump_chunk_end`) are book-mode-only, chunk-scoped (not page/offset-scoped like Ctrl+Left/Right), skip-without-scoring, and never build a new `Scorer` or write to storage — contrast this explicitly with the existing Ctrl+Left/Right/Home invariant bullet already in the file, since the two navigation tiers are easy to conflate.

- [ ] **Step 2: Run the full suite one more time**

Run: `pytest -q`
Expected: all tests still pass (docs-only change, but confirms nothing was accidentally left broken).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: document chunk navigation and the inline dictionary panel

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Whole-branch final review

**Files:** none (review only, fixes go wherever needed)

- [ ] **Step 1: Read the full diff since before Task 1**

```bash
git log --oneline -8
git diff HEAD~5 -- typingapp/screens/lesson.py typingapp/app.tcss
```

- [ ] **Step 2: Manually verify the following, per the design spec's edge cases**

- Ctrl+D immediately after Ctrl+Down (chunk-end jump, `is_complete=True`) is a no-op — confirm the existing `if s is None or s.is_complete: return` guard in `action_show_definition` still covers this correctly (it should, unchanged).
- Non-English language: pressing Ctrl+D twice in a row on the same word shows the unavailable message once, then focuses the panel on the second press (not a re-render loop) — this exercises the `lookup_word == self._dictionary_word_key` branch on the non-English path too, since that check happens before the language check.
- `#dictionary-panel`'s CSS `max-height: 30%` doesn't crowd out `#text-scroll` on a typical terminal size — eyeball this by running the app manually if a terminal is available (`python -m typingapp`), or note as a non-blocking cosmetic follow-up if not.
- Confirm `tests/test_lesson_screen_book_page_nav.py`'s existing page-jump tests (Task 1's siblings, unrelated to this plan) still pass unmodified — chunk nav must not have broken absolute page-offset navigation.

- [ ] **Step 3: Run the full suite one final time**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 4: Report completion**

No commit needed for this task unless Step 2 surfaces a fix — if it does, make the fix, re-run the full suite, and commit it with a `fix:` message before considering the plan complete.
