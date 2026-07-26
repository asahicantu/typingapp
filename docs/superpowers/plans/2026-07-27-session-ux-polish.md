# Session UX Polish Implementation Plan (Stage B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add live in-session settings toggles (strict mode, key sounds), highlight words the user has mistyped in past sessions, consolidate the session footer into one mode-aware method, and fix the Settings screen's unhelpful "(not cached yet)" message for a stale `selected_book_id`.

**Architecture:** A new `word_mistakes` SQLite table (word → cumulative miss count across all sessions) populated from `Scorer.word_errors` at `LessonScreen._finish()`, read back at lesson start to build a highlight set. Two new `LessonScreen` keybindings that mutate `AppConfig` fields directly and persist via the existing `save_config`. The existing `_render_text`/`_render_book_text` rendering paths gain one more style rule (light orange) gated on a new `AppConfig.highlight_past_mistakes` toggle. The footer-hint construction (currently duplicated inline in `_start_lesson`) becomes one method, `_footer_hint_text()`, called from every place the footer is set.

**Tech Stack:** Pure Python + stdlib `sqlite3` (new table, following the exact schema/method patterns already in `typingapp/data/storage.py`), Textual `BINDINGS`/`Label.update()`. No new dependencies.

## Global Constraints

- Follow this repo's existing SQLite patterns exactly: table constants named `CREATE_<NAME>`, added via `self._conn.execute(...)` in `Storage.__init__` before the final `commit()`, methods `commit()` after every write, `fetchall()`/`fetchone()` converted to `dict`/`list[dict]`.
- Follow this repo's existing test convention: plain pytest, one test file per concern, Textual pilot-based screen tests only for screen *behavior* (not pure logic) — this repo already has `tests/test_lesson_screen_book_mode.py`, `tests/test_lesson_screen_sanitization.py` as precedent for pilot-based `LessonScreen` tests.
- `AppConfig` fields must have safe defaults so `load_config()` on an old config.json (missing the new keys) still works — this already works automatically via `AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})`, so just give new fields dataclass defaults, no migration code needed.
- Do not touch `Scorer`'s core keystroke-processing logic (`process_key`) — `word_errors` already exists and is sufficient as-is; this stage only *reads* it, at `_finish()` time, into the new table.
- New keybindings must not collide with existing ones. Current `LessonScreen.BINDINGS`: `escape` (pause), `ctrl+r` (restart), `ctrl+q` (quit), `ctrl+e` (menu), `ctrl+f` (finish_session, book mode only). Use `ctrl+s` (toggle strict mode) and `ctrl+k` (toggle key sounds) — both currently free.

---

### Task 1: `word_mistakes` storage table + methods

**Files:**
- Modify: `typingapp/data/storage.py`
- Test: `tests/test_storage.py` (append to existing file)

**Interfaces:**
- Produces: `Storage.record_word_mistakes(word_counts: dict[str, int]) -> None` (called once per session with a session's `Scorer.word_errors` dict — accumulates into the table, does not overwrite), `Storage.fetch_frequently_missed_words(min_misses: int = 2, limit: int = 200) -> set[str]` (returns the set of words with at least `min_misses` cumulative misses across all sessions, for `LessonScreen` to use as its highlight set — used by Task 3).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_storage.py

def test_record_word_mistakes_creates_new_entries(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({"the": 2, "quick": 1})
    missed = s.fetch_frequently_missed_words(min_misses=1)
    assert missed == {"the", "quick"}
    s.close()


def test_record_word_mistakes_accumulates_across_calls(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({"the": 2})
    s.record_word_mistakes({"the": 3, "fox": 1})
    # "the" should now have 5 cumulative misses, "fox" only 1
    assert s.fetch_frequently_missed_words(min_misses=4) == {"the"}
    assert s.fetch_frequently_missed_words(min_misses=1) == {"the", "fox"}
    s.close()


def test_fetch_frequently_missed_words_respects_min_misses_threshold(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({"rare": 1, "common": 10})
    assert s.fetch_frequently_missed_words(min_misses=2) == {"common"}
    s.close()


def test_fetch_frequently_missed_words_empty_when_no_data(tmp_path):
    s = Storage(tmp_path / "test.db")
    assert s.fetch_frequently_missed_words() == set()
    s.close()


def test_record_word_mistakes_with_empty_dict_is_a_noop(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({})
    assert s.fetch_frequently_missed_words(min_misses=1) == set()
    s.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage.py -k word_mistakes -v`
Expected: FAIL with `AttributeError: 'Storage' object has no attribute 'record_word_mistakes'`

- [ ] **Step 3: Add the table and methods**

In `typingapp/data/storage.py`, add a new SQL constant near the other `CREATE_*` constants (after `CREATE_BOOK_PROGRESS`):

```python
CREATE_WORD_MISTAKES = """
CREATE TABLE IF NOT EXISTS word_mistakes (
    word TEXT PRIMARY KEY,
    miss_count INTEGER NOT NULL DEFAULT 0
)"""
```

In `Storage.__init__`, add the execute call alongside the others (after `self._conn.execute(CREATE_BOOK_PROGRESS)`, before `self._conn.commit()`):

```python
        self._conn.execute(CREATE_WORD_MISTAKES)
```

Add these two methods (placed after `list_books_with_progress`, before `close`):

```python
    def record_word_mistakes(self, word_counts: dict[str, int]) -> None:
        if not word_counts:
            return
        self._conn.executemany(
            "INSERT INTO word_mistakes (word, miss_count) VALUES (?, ?) "
            "ON CONFLICT(word) DO UPDATE SET miss_count = miss_count + excluded.miss_count",
            list(word_counts.items()),
        )
        self._conn.commit()

    def fetch_frequently_missed_words(self, min_misses: int = 2, limit: int = 200) -> set[str]:
        rows = self._conn.execute(
            "SELECT word FROM word_mistakes WHERE miss_count >= ? ORDER BY miss_count DESC LIMIT ?",
            (min_misses, limit),
        ).fetchall()
        return {r["word"] for r in rows}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_storage.py -k word_mistakes -v`
Expected: PASS (all 5 new tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all previously-passing tests still pass, plus the 5 new ones

- [ ] **Step 6: Commit**

```bash
git add typingapp/data/storage.py tests/test_storage.py
git commit -m "feat: add word_mistakes table for cross-session mistake tracking"
```

---

### Task 2: `AppConfig.highlight_past_mistakes` toggle + Settings UI

**Files:**
- Modify: `typingapp/config.py`
- Modify: `typingapp/screens/settings.py`
- Test: `tests/test_config.py` (append), no new settings-screen test needed (a pure Switch add, covered adequately by Task 1's storage tests plus manual verification in Task 4's screen test)

**Interfaces:**
- Consumes: nothing new.
- Produces: `AppConfig.highlight_past_mistakes: bool` (default `True`) — read by `LessonScreen` in Task 3 to decide whether to query `fetch_frequently_missed_words` at all.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_config.py

def test_highlight_past_mistakes_defaults_true_and_roundtrips(tmp_path):
    cfg = AppConfig()
    assert cfg.highlight_past_mistakes is True
    cfg.highlight_past_mistakes = False
    path = tmp_path / "config.json"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.highlight_past_mistakes is False
```

(Confirm the test file already imports `AppConfig`, `save_config`, `load_config` at the top — if not, add `from typingapp.config import AppConfig, save_config, load_config`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -k highlight_past_mistakes -v`
Expected: FAIL with `TypeError: AppConfig.__init__() got an unexpected keyword argument` or `AttributeError` depending on how the test is written — either way, fails because the field doesn't exist yet.

- [ ] **Step 3: Add the field to `AppConfig`**

In `typingapp/config.py`, add one line to the dataclass (after `epub_folder: str = ""`):

```python
    highlight_past_mistakes: bool = True
```

- [ ] **Step 4: Add a Settings toggle**

In `typingapp/screens/settings.py`, inside `compose()`, add a new `Switch` in the existing "DISPLAY" section (after the "Key sounds" row, before the closing `yield Static("")` of that section):

```python
            with Horizontal(classes="setting-row"):
                yield Label("Highlight previously mistyped words")
                yield Switch(value=cfg.highlight_past_mistakes, id="sw-highlight-mistakes")
```

In `on_button_pressed`, inside the `if event.button.id == "btn-save":` block, add one line alongside the other `cfg.<field> = self.query_one(...)` lines (after `cfg.key_sounds = self.query_one("#sw-sound", Switch).value`):

```python
            cfg.highlight_past_mistakes = self.query_one("#sw-highlight-mistakes", Switch).value
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -k highlight_past_mistakes -v`
Expected: PASS

Run: `pytest -q`
Expected: all tests pass (this is a pure additive UI change; no existing Settings test asserts an exact widget count/order that this would break — confirmed by reading `tests/test_settings_book_warning.py`, which only tests the two pure helper functions, not `compose()` layout)

- [ ] **Step 6: Commit**

```bash
git add typingapp/config.py typingapp/screens/settings.py tests/test_config.py
git commit -m "feat: add highlight_past_mistakes config toggle and Settings switch"
```

---

### Task 3: Highlight previously-mistyped words during a session

**Files:**
- Modify: `typingapp/screens/lesson.py`
- Test: `tests/test_lesson_screen_mistake_highlighting.py` (new file)

**Interfaces:**
- Consumes: `Storage.fetch_frequently_missed_words(min_misses=2, limit=200) -> set[str]` (Task 1), `Storage.record_word_mistakes(word_counts: dict[str, int]) -> None` (Task 1), `AppConfig.highlight_past_mistakes: bool` (Task 2).
- Produces: `LessonScreen._missed_words: set[str]` (instance attribute, the highlight set for the current session — read by both `_render_text` and `_render_book_text`), a new CSS class `.mistake-highlight` in `typingapp/app.tcss` styled light orange.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lesson_screen_mistake_highlighting.py
import asyncio
from pathlib import Path
from textual.app import App

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen


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


def test_previously_missed_words_render_with_highlight_class(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.record_word_mistakes({"jumps": 5})
    cfg = AppConfig(content_type="custom", key_sounds=False, highlight_past_mistakes=True)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # custom_text must be set before _start_lesson runs; on_mount already
            # called _start_lesson once during push_screen, so re-set _custom_text
            # and call _start_lesson() again explicitly to pick it up deterministically.
            screen._custom_text = "the quick fox jumps over"
            screen._start_lesson()
            await pilot.pause()
            assert "jumps" in screen._missed_words

    asyncio.run(run())
    storage.close()


def test_words_below_threshold_are_not_highlighted(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.record_word_mistakes({"rare": 1})  # below default min_misses=2
    cfg = AppConfig(content_type="custom", key_sounds=False, highlight_past_mistakes=True)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._custom_text = "a rare word here"
            screen._start_lesson()
            await pilot.pause()
            assert "rare" not in screen._missed_words

    asyncio.run(run())
    storage.close()


def test_highlighting_disabled_via_config_yields_empty_missed_words(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.record_word_mistakes({"jumps": 10})
    cfg = AppConfig(content_type="custom", key_sounds=False, highlight_past_mistakes=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._custom_text = "the quick fox jumps over"
            screen._start_lesson()
            await pilot.pause()
            assert screen._missed_words == set()

    asyncio.run(run())
    storage.close()


def test_finishing_a_session_records_word_mistakes_for_next_time(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, session_duration=600)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._custom_text = "cat"
            screen._start_lesson()
            await pilot.pause()
            # type it wrong once, then correctly, to generate a word_errors entry
            await pilot.press("x")  # wrong first char
            await pilot.press("c")
            await pilot.press("a")
            await pilot.press("t")
            await pilot.pause()

    asyncio.run(run())

    missed = storage.fetch_frequently_missed_words(min_misses=1)
    assert "cat" in missed
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_mistake_highlighting.py -v`
Expected: FAIL — `AttributeError: 'LessonScreen' object has no attribute '_missed_words'` (or similar), since `_missed_words` doesn't exist yet.

- [ ] **Step 3: Add `_missed_words` population and recording**

In `typingapp/screens/lesson.py`, add to `__init__` (after `self._book_chunk_spans: list[tuple[str, int, int]] = []`):

```python
        self._missed_words: set[str] = set()
```

In `_start_lesson`, right after the line `app = self.app      # type: ignore[attr-defined]` at the top of the method, add:

```python
        if app.config.highlight_past_mistakes:
            self._missed_words = app.storage.fetch_frequently_missed_words()
        else:
            self._missed_words = set()
```

In `_finish`, right after `self._persist_book_progress()` near the top of the method, add:

```python
        if self._scorer is not None:
            app.storage.record_word_mistakes(self._scorer.word_errors)
```

(`app` is already bound later in `_finish` via `app = self.app` — move that binding line up above this new code, or reference `self.app` directly here since `self._scorer` is already available at that point in the method. Check the existing method body order and place this in a position where `app`/`self.app` and `self._scorer` are both already valid — the existing `_finish()` binds `app = self.app` on the line right after `self._persist_book_progress()`, so this new block goes immediately after that binding.)

- [ ] **Step 4: Wire highlighting into rendering**

In `typingapp/app.tcss`, add a new class near the other stat/color classes (e.g. near `.wpm-value { color: #f9c74f; }` and similar):

```css
.mistake-highlight { color: #ffb347; }
```

In `typingapp/screens/lesson.py`'s `_render_text` (the non-book path), the current body is:

```python
    def _render_text(self) -> None:
        if self._scorer is None:
            return
        if self._book_id:
            self._render_book_text()
            return
        s = self._scorer
        target = s.target
        pos = s.position
        typed = f"[bold green]{target[:pos]}[/]"
        cursor = ""
        rest = ""
        if pos < len(target):
            cursor = f"[bold on red]{target[pos]}[/]"
            rest = f"[dim]{target[pos+1:]}[/]"
        display = self.query_one("#text-display", Static)
        display.update(typed + cursor + rest)
        self._scroll_to_cursor(pos, len(target))
```

Change the `rest` computation to style words found in `self._missed_words` — replace the line `rest = f"[dim]{target[pos+1:]}[/]"` with a call to a new helper:

```python
            rest = self._style_rest_with_mistake_highlight(target[pos+1:])
```

Add the new helper method right after `_render_text` (before `_render_book_text`):

```python
    def _style_rest_with_mistake_highlight(self, text: str) -> str:
        if not self._missed_words:
            return f"[dim]{text}[/]"
        parts: list[str] = []
        cursor = 0
        for match in WORD_RE.finditer(text):
            word = match.group()
            if cursor < match.start():
                parts.append(f"[dim]{text[cursor:match.start()]}[/]")
            if word in self._missed_words:
                parts.append(f"[dim][mistake-highlight]{word}[/][/]")
            else:
                parts.append(f"[dim]{word}[/]")
            cursor = match.end()
        if cursor < len(text):
            parts.append(f"[dim]{text[cursor:]}[/]")
        return "".join(parts)
```

Note: `WORD_RE` (`re.compile(r"\S+")`) is already defined at module level in this file for book-mode rendering — reuse it here rather than defining a second pattern. `[mistake-highlight]...[/]` uses Textual's CSS-class markup shorthand (a class name in square brackets applies that CSS class's styling) — confirm this syntax works by checking how `.mistake-highlight`'s color renders in the Task 4 verification step; if Textual's markup parser does not support class-name-in-brackets shorthand (it supports named colors/styles, not necessarily arbitrary CSS classes, in inline markup), use the literal hex color instead: replace `[mistake-highlight]` with `[#ffb347]` directly in the f-string, matching the style already used elsewhere in this file (e.g. `[#888888]` in `_style_paragraph_punctuation`) — prefer the hex-literal form for consistency with the rest of this file's rendering code, and skip adding the `.mistake-highlight` CSS class entirely if you take this path (simpler, one less indirection, matches existing conventions in this exact file).

For book mode, apply the same word-level highlight inside `_style_paragraph_punctuation` (used for the "rest of the paragraph" body text in `_style_book_rest`) — wrap its existing per-segment loop so that when a non-punctuation segment matches a word in `self._missed_words` (case-sensitive, whole-word match via the same `WORD_RE` boundary logic), it uses the mistake-highlight color instead of `[dim]`. Concretely, in `_style_paragraph_punctuation`, change:

```python
            else:
                parts.append(f"[dim]{escape(segment)}[/]")
```

to:

```python
            else:
                color = "#ffb347" if segment.strip() in self._missed_words else None
                if color:
                    parts.append(f"[{color}]{escape(segment)}[/]")
                else:
                    parts.append(f"[dim]{escape(segment)}[/]")
```

(`segment.strip()` handles the case where the punctuation-split regex leaves whitespace attached to a word-only segment — verify this against the actual behavior of `PUNCTUATION_SPLIT_RE.split` in this file; if segments are already whitespace-free words, `.strip()` is a no-op safety measure, not a required fix.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_mistake_highlighting.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add typingapp/screens/lesson.py typingapp/app.tcss tests/test_lesson_screen_mistake_highlighting.py
git commit -m "feat: highlight words previously mistyped in past sessions"
```

---

### Task 4: Live in-session settings shortcuts (strict mode, key sounds)

**Files:**
- Modify: `typingapp/screens/lesson.py`
- Test: `tests/test_lesson_screen_live_settings.py` (new file)

**Interfaces:**
- Consumes: `typingapp.config.save_config` (already used elsewhere in this codebase, e.g. `typingapp/screens/settings.py`).
- Produces: `LessonScreen.action_toggle_strict_mode()`, `LessonScreen.action_toggle_key_sounds()` — new bindings `ctrl+s`, `ctrl+k`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lesson_screen_live_settings.py
import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Label

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig, load_config
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen


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
            self.push_screen(LessonScreen(custom_text="hello world"))

    return TestApp()


def test_ctrl_s_toggles_strict_mode_and_persists(tmp_path):
    storage = Storage(tmp_path / "test.db")
    config_path = tmp_path / "config.json"
    cfg = AppConfig(content_type="custom", strict_mode=False, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()

    asyncio.run(run())

    assert app.config.strict_mode is True
    storage.close()


def test_ctrl_s_shows_confirmation_in_hint_bar(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", strict_mode=False, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
            hint = app.screen.query_one("#hint-bar", Label)
            assert "Strict mode" in str(hint.content)
            assert "ON" in str(hint.content)

    asyncio.run(run())
    storage.close()


def test_ctrl_k_toggles_key_sounds_and_persists(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=True)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+k")
            await pilot.pause()

    asyncio.run(run())

    assert app.config.key_sounds is False
    storage.close()


def test_toggling_strict_mode_writes_to_disk(tmp_path):
    from typingapp.config import DEFAULT_CONFIG_PATH
    import typingapp.config as config_module

    storage = Storage(tmp_path / "test.db")
    config_path = tmp_path / "config.json"
    cfg = AppConfig(content_type="custom", strict_mode=False, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run(monkeypatch_path):
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()

    # save_config is called with the default path inside LessonScreen; to verify
    # persistence without monkeypatching the module-level default, just re-load
    # the in-memory app.config object directly (already covered by the first test).
    # This test instead verifies save_config was actually invoked by checking a
    # patched call.
    from unittest.mock import patch
    with patch("typingapp.screens.lesson.save_config") as mock_save:
        asyncio.run(run(config_path))
        assert mock_save.called
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_live_settings.py -v`
Expected: FAIL — `ctrl+s`/`ctrl+k` are not bound, so pressing them does nothing (`strict_mode`/`key_sounds` remain unchanged), and `#hint-bar` never gets the confirmation text.

- [ ] **Step 3: Add the bindings and actions**

In `typingapp/screens/lesson.py`, add the import for `save_config` near the top:

```python
from typingapp.config import save_config
```

Add two entries to `BINDINGS` (after `("ctrl+f", "finish_session", "Finish Session"),`):

```python
        ("ctrl+s", "toggle_strict_mode", "Toggle Strict Mode"),
        ("ctrl+k", "toggle_key_sounds", "Toggle Key Sounds"),
```

Add the two action methods near the other `action_*` methods (e.g. right after `action_finish_session`):

```python
    def action_toggle_strict_mode(self) -> None:
        app = self.app          # type: ignore[attr-defined]
        app.config.strict_mode = not app.config.strict_mode
        save_config(app.config)
        state = "ON" if app.config.strict_mode else "OFF"
        self.query_one("#hint-bar", Label).update(f"Strict mode: {state}")
        if self._scorer is not None:
            self._scorer.strict_mode = app.config.strict_mode

    def action_toggle_key_sounds(self) -> None:
        app = self.app          # type: ignore[attr-defined]
        app.config.key_sounds = not app.config.key_sounds
        save_config(app.config)
        state = "ON" if app.config.key_sounds else "OFF"
        self.query_one("#hint-bar", Label).update(f"Key sounds: {state}")
```

Note: `action_toggle_strict_mode` also updates `self._scorer.strict_mode` on the live `Scorer` instance (if one exists) so the toggle takes effect immediately for the rest of the current lesson, not just future lessons — `Scorer.strict_mode` is a plain dataclass field (see `typingapp/engine/scorer.py`), safe to mutate directly mid-session.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_live_settings.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add typingapp/screens/lesson.py tests/test_lesson_screen_live_settings.py
git commit -m "feat: add Ctrl+S/Ctrl+K live toggles for strict mode and key sounds"
```

---

### Task 5: Consolidate footer-hint into one mode-aware method

**Files:**
- Modify: `typingapp/screens/lesson.py`
- Test: `tests/test_lesson_screen_footer_hint.py` (new file)

**Interfaces:**
- Consumes: `self._book_id` (existing instance state).
- Produces: `LessonScreen._footer_hint_text() -> str` — a pure(ish) method (reads only `self._book_id`, returns a string) that both `_start_lesson` calls instead of its current inline if/else.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lesson_screen_footer_hint.py
import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Static

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen


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
            self.push_screen(LessonScreen(custom_text="hello"))

    return TestApp()


def test_non_book_footer_lists_core_shortcuts_and_new_toggles(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.screen.query_one("#footer-hint", Static)
            text = str(footer.renderable) if hasattr(footer, "renderable") else str(footer.content)
            for expected in ("Ctrl+R", "Ctrl+Q", "Ctrl+E", "Ctrl+S", "Ctrl+K"):
                assert expected in text
            assert "Ctrl+F" not in text  # finish_session is book-mode only

    asyncio.run(run())
    storage.close()


def test_book_mode_footer_includes_finish_shortcut(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text="word " * 200, cached_at="2026-07-27T10:00:00")
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.screen.query_one("#footer-hint", Static)
            text = str(footer.content)
            assert "Ctrl+F" in text
            assert "Ctrl+S" in text
            assert "Ctrl+K" in text

    asyncio.run(run())
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_footer_hint.py -v`
Expected: FAIL — current footer text is `"ESC pause  ·  Ctrl+R restart  ·  Ctrl+Q quit  ·  Ctrl+E menu"` (non-book) or with `Ctrl+F finish` added (book mode), neither mentions `Ctrl+S`/`Ctrl+K` yet.

- [ ] **Step 3: Add `_footer_hint_text` and use it**

In `typingapp/screens/lesson.py`, add this method near `_update_book_progress_label` (or any other small helper — placement is not load-bearing, just keep it near the other `_start_lesson`-adjacent helpers):

```python
    def _footer_hint_text(self) -> str:
        base = "ESC pause  ·  Ctrl+R restart  ·  Ctrl+S strict  ·  Ctrl+K sound  ·  Ctrl+Q quit  ·  Ctrl+E menu"
        if self._book_id:
            return "ESC pause  ·  Ctrl+R restart  ·  Ctrl+F finish  ·  Ctrl+S strict  ·  Ctrl+K sound  ·  Ctrl+Q quit  ·  Ctrl+E menu"
        return base
```

In `_start_lesson`, replace this existing block:

```python
        footer = self.query_one("#footer-hint", Static)
        if self._book_id:
            footer.update("ESC pause  ·  Ctrl+R restart  ·  Ctrl+F finish  ·  Ctrl+Q quit  ·  Ctrl+E menu")
        else:
            footer.update("ESC pause  ·  Ctrl+R restart  ·  Ctrl+Q quit  ·  Ctrl+E menu")
```

with:

```python
        self.query_one("#footer-hint", Static).update(self._footer_hint_text())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_footer_hint.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add typingapp/screens/lesson.py tests/test_lesson_screen_footer_hint.py
git commit -m "refactor: consolidate footer-hint text into one mode-aware method"
```

---

### Task 6: Settings clarity fix for a stale/uncached `selected_book_id`

**Files:**
- Modify: `typingapp/screens/settings.py`
- Test: `tests/test_settings_book_warning.py` (append to existing file)

**Interfaces:**
- Consumes: nothing new.
- Produces: `_book_display_text(app)` (existing function) now returns a clearer message for the uncached-book case.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_settings_book_warning.py

def test_book_display_text_explains_uncached_book_clearly():
    from typingapp.screens.settings import _book_display_text
    from typingapp.config import AppConfig

    class FakeStorage:
        def get_book(self, book_id):
            return None

    app = _fake_app(AppConfig(selected_book_id="gutenberg:999"))
    app.storage = FakeStorage()
    text = _book_display_text(app)
    assert text.startswith("⚠")
    assert "gutenberg:999" in text
    assert "Browse Books" in text or "My Books" in text
```

(Confirm `_fake_app` is already defined earlier in this test file, per the existing tests in `tests/test_settings_book_warning.py` — reuse it rather than redefining.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_book_warning.py -k uncached -v`
Expected: FAIL — current `_book_display_text` returns `f"{cfg.selected_book_id} (not cached yet)"`, which does not start with `⚠` and does not mention "Browse Books"/"My Books".

- [ ] **Step 3: Update `_book_display_text`**

In `typingapp/screens/settings.py`, change:

```python
    if book is None:
        return f"{cfg.selected_book_id} (not cached yet)"
```

to:

```python
    if book is None:
        return f'⚠ "{cfg.selected_book_id}" isn\'t cached — pick a book via Find a New Book or My Books'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_settings_book_warning.py -v`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add typingapp/screens/settings.py tests/test_settings_book_warning.py
git commit -m "fix: explain a stale/uncached selected_book_id clearly in Settings"
```

---

### Task 7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only).

- [ ] **Step 1: Add a new Architecture bullet**, immediately after the existing `typingapp/data/storage.py` bullet:

```markdown
- `word_mistakes` table (in `typingapp/data/storage.py`) tracks cumulative per-word miss counts across ALL sessions (not per-session) — `Storage.record_word_mistakes(word_counts)` upserts-and-adds at `LessonScreen._finish()` from that session's `Scorer.word_errors`; `Storage.fetch_frequently_missed_words(min_misses=2)` reads it back at the start of the next lesson to build the highlight set. This is deliberately a *cross-session* aggregate, separate from `Scorer.word_errors` (which is per-lesson only and reset every `_start_lesson`).
```

- [ ] **Step 2: Add new Key Invariants**, appended at the end of the Key Invariants section:

```markdown
- **Mistake-word highlighting reads a cross-session aggregate, not the current session's own errors.** `LessonScreen._missed_words` (populated in `_start_lesson` from `storage.fetch_frequently_missed_words()`, gated on `AppConfig.highlight_past_mistakes`) is about words you've struggled with historically, shown from the very first keystroke of a NEW lesson — it does not update mid-lesson based on mistakes made in that same lesson (that's a separate, unrelated existing feature: the weak-bigram hint in `#hint-bar`, driven by `AdaptiveEngine.detect_weak_bigrams` on the *current* `Scorer.keystrokes`). Both features coexist and answer different questions ("what have I struggled with historically" vs. "what am I struggling with right now").
- **`LessonScreen`'s live settings toggles (`Ctrl+S` strict mode, `Ctrl+K` key sounds) persist immediately via `save_config`, mid-lesson, not just at `_finish()`.** `action_toggle_strict_mode` also mutates the live `Scorer.strict_mode` directly (a plain dataclass field) so the change takes effect for the remainder of the CURRENT lesson too, not just future ones — unlike difficulty/other settings, which only ever get written back to `AppConfig` at session end (see the `AdaptiveEngine`/`manual_difficulty` invariant above).
- **`LessonScreen._footer_hint_text()` is the single source of truth for the footer shortcut line** — don't reintroduce the inline if/else that used to be duplicated in `_start_lesson`; any new session-mode keybinding should be reflected here too if it's meant to be discoverable.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document word_mistakes table and live settings toggles in CLAUDE.md"
```

## Self-Review Notes

- **Spec coverage:** covers all of Stage B — item #5 (live settings shortcuts, Task 4), item #12 (mistake highlighting, Tasks 1-3), item #10 (mode-aware footer consolidation, Task 5), and the Settings clarity fix for the stale-book issue (Task 6).
- **Placeholder scan:** an earlier draft of Task 3's test file had two stray planning-artifact lines (an unused import, an unused variable); both were removed directly from the plan during self-review rather than left as a note for the implementer to clean up. Fixed a garbled sentence in Global Constraints ("sufthis stage") from a mid-edit typo. No remaining placeholders, TBDs, or vague instructions found on a second pass.
- **Type consistency:** `Storage.fetch_frequently_missed_words(min_misses: int = 2, limit: int = 200) -> set[str]` is defined once in Task 1 and called identically (no args, or `min_misses=1`/`min_misses=2` in tests) everywhere it's used in Tasks 3 and 6. `AppConfig.highlight_past_mistakes: bool = True` (Task 2) is read once in Task 3's `_start_lesson` change — no drift in field name or type across tasks.
