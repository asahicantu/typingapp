# Finger-Hint Typing Coach Implementation Plan (Stage C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the user, at all times during a session, which word they're currently typing and which finger (on a standard US-QWERTY touch-typing layout) they should use for the very next key — an always-visible coaching aid, not a toggle.

**Architecture:** A new pure module `engine/keyboard_map.py` maps every US-QWERTY key to a `(hand, finger)` pair via a static dict, with a `finger_for_char(char)` lookup function. A new pure helper `current_word_at(text, position)` (placed in `engine/scorer.py` alongside the existing `Scorer._word_at`, since it's the same word-boundary concept generalized into a standalone function) finds the word containing a given character offset. `LessonScreen` gets one new always-visible `Label` row (below the stats bar, above the progress bar) showing `Next word: <word> · next key '<char>' → <Hand> <finger>`, updated every `_tick()` — no new timer needed, reusing the existing 0.25s interval.

**Tech Stack:** Pure Python (static dict + regex-based word lookup), Textual `Label.update()`. No new dependencies.

## Global Constraints

- US-QWERTY layout only, per the confirmed design scope — no other layouts, no configurability.
- The finger-hint bar is always visible, not gated by any `AppConfig` toggle (per your explicit choice in the design phase) — every session shows it, book mode and non-book mode alike.
- Follow this repo's existing test convention: plain pytest, one test file per concern; Textual pilot-based screen tests only for screen *behavior* (this repo has `tests/test_lesson_screen_footer_hint.py` etc. as direct precedent for testing a `Label`'s content via pilot).
- Do not touch `Scorer.process_key`, `Scorer.word_errors`, or the mistake-highlighting code from Stage B — this stage only *reads* `Scorer.target`/`Scorer.position`, it doesn't change how keystrokes are scored.
- The finger-hint text must update on every tick, but must not error or show garbage when the lesson is complete (`position >= len(target)`) or when there's no current word (e.g. position sits exactly on a space) — handle these as "no hint to show" (empty string), not a crash.

---

### Task 1: `engine/keyboard_map.py` — US-QWERTY finger mapping

**Files:**
- Create: `typingapp/engine/keyboard_map.py`
- Test: `tests/test_keyboard_map.py`

**Interfaces:**
- Produces: `finger_for_char(char: str) -> tuple[str, str] | None` — used by Task 3 (`LessonScreen`). Returns `(hand, finger)` where `hand` is `"Left"`/`"Right"` and `finger` is `"pinky"`/`"ring"`/`"middle"`/`"index"`/`"thumb"`, or `None` if the character has no defined home-row mapping (e.g. characters outside the mapped set).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_keyboard_map.py
from typingapp.engine.keyboard_map import finger_for_char


def test_left_pinky_keys():
    for ch in ("q", "a", "z", "1"):
        assert finger_for_char(ch) == ("Left", "pinky")


def test_left_ring_keys():
    for ch in ("w", "s", "x", "2"):
        assert finger_for_char(ch) == ("Left", "ring")


def test_left_middle_keys():
    for ch in ("e", "d", "c", "3"):
        assert finger_for_char(ch) == ("Left", "middle")


def test_left_index_keys_including_reach_column():
    # standard touch-typing charts give the index finger both its home column
    # and the adjacent reach column (f/r/v/g/t/b on the left hand)
    for ch in ("f", "r", "v", "g", "t", "b", "4", "5"):
        assert finger_for_char(ch) == ("Left", "index")


def test_right_index_keys_including_reach_column():
    for ch in ("j", "u", "m", "h", "y", "n", "6", "7"):
        assert finger_for_char(ch) == ("Right", "index")


def test_right_middle_keys():
    for ch in ("k", "i", ",", "8"):
        assert finger_for_char(ch) == ("Right", "middle")


def test_right_ring_keys():
    for ch in ("l", "o", ".", "9"):
        assert finger_for_char(ch) == ("Right", "ring")


def test_right_pinky_keys():
    for ch in ("p", ";", "/", "0", "'", "[", "]", "-", "="):
        assert finger_for_char(ch) == ("Right", "pinky")


def test_space_uses_thumb():
    result = finger_for_char(" ")
    assert result is not None
    assert result[1] == "thumb"


def test_uppercase_letters_map_to_same_finger_as_lowercase():
    assert finger_for_char("Q") == finger_for_char("q")
    assert finger_for_char("A") == finger_for_char("a")


def test_unmapped_character_returns_none():
    assert finger_for_char("€") is None
    assert finger_for_char("\n") is None


def test_newline_and_tab_return_none_not_crash():
    assert finger_for_char("\t") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_keyboard_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'typingapp.engine.keyboard_map'`

- [ ] **Step 3: Write the implementation**

```python
# typingapp/engine/keyboard_map.py
from __future__ import annotations

# Standard US-QWERTY touch-typing finger assignments. Each entry maps a
# lowercase key to (hand, finger); shifted/uppercase variants and digit-row
# punctuation share the same finger as their unshifted key on a real keyboard,
# handled by normalizing the input character before lookup.
_KEY_TO_FINGER: dict[str, tuple[str, str]] = {
    # number row
    "1": ("Left", "pinky"), "2": ("Left", "ring"), "3": ("Left", "middle"),
    "4": ("Left", "index"), "5": ("Left", "index"),
    "6": ("Right", "index"), "7": ("Right", "index"),
    "8": ("Right", "middle"), "9": ("Right", "ring"), "0": ("Right", "pinky"),
    "-": ("Right", "pinky"), "=": ("Right", "pinky"),
    # top row
    "q": ("Left", "pinky"), "w": ("Left", "ring"), "e": ("Left", "middle"),
    "r": ("Left", "index"), "t": ("Left", "index"),
    "y": ("Right", "index"), "u": ("Right", "index"),
    "i": ("Right", "middle"), "o": ("Right", "ring"), "p": ("Right", "pinky"),
    "[": ("Right", "pinky"), "]": ("Right", "pinky"),
    # home row
    "a": ("Left", "pinky"), "s": ("Left", "ring"), "d": ("Left", "middle"),
    "f": ("Left", "index"), "g": ("Left", "index"),
    "h": ("Right", "index"), "j": ("Right", "index"),
    "k": ("Right", "middle"), "l": ("Right", "ring"), ";": ("Right", "pinky"),
    "'": ("Right", "pinky"),
    # bottom row
    "z": ("Left", "pinky"), "x": ("Left", "ring"), "c": ("Left", "middle"),
    "v": ("Left", "index"), "b": ("Left", "index"),
    "n": ("Right", "index"), "m": ("Right", "index"),
    ",": ("Right", "middle"), ".": ("Right", "ring"), "/": ("Right", "pinky"),
    # space
    " ": ("Left", "thumb"),
}


def finger_for_char(char: str) -> tuple[str, str] | None:
    """Return (hand, finger) for the given character on a standard US-QWERTY
    touch-typing layout, or None if the character has no defined home. Case-
    insensitive: uppercase letters map to the same finger as their lowercase
    form (a real keyboard's Shift key is a separate finger concern this app
    doesn't model)."""
    if len(char) != 1:
        return None
    return _KEY_TO_FINGER.get(char.lower())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_keyboard_map.py -v`
Expected: PASS (all 12 tests)

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/keyboard_map.py tests/test_keyboard_map.py
git commit -m "feat: add US-QWERTY finger mapping for typing coach hints"
```

---

### Task 2: `current_word_at` helper in `engine/scorer.py`

**Files:**
- Modify: `typingapp/engine/scorer.py`
- Test: `tests/test_scorer.py` (append to existing file)

**Interfaces:**
- Produces: `current_word_at(text: str, position: int) -> str` — a module-level function (not a `Scorer` method, so it can be called by `LessonScreen` without needing a `Scorer` instance's other state) that returns the word containing `text[position]`, or `""` if `position` is out of bounds or sits on whitespace. Used by Task 3.

**Note:** `Scorer._word_at` already exists and does almost this, but it (a) is a private instance method requiring a full `Scorer`, (b) always returns a *normalized* (punctuation-stripped, lowercased) word via `normalize_mistake_word`, which is correct for its mistake-tracking purpose but wrong for a coaching display (the user wants to see the word exactly as it appears in the text, punctuation and case intact, so they know what they're about to type). This task adds a separate, display-oriented function rather than changing `_word_at`'s behavior — do not modify `_word_at` or `normalize_mistake_word`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_scorer.py

def test_current_word_at_returns_the_word_containing_position():
    from typingapp.engine.scorer import current_word_at
    text = "the quick brown fox"
    # position 4 is the 'q' in "quick"
    assert current_word_at(text, 4) == "quick"


def test_current_word_at_preserves_original_case_and_punctuation():
    from typingapp.engine.scorer import current_word_at
    text = "Hello, World!"
    assert current_word_at(text, 0) == "Hello,"


def test_current_word_at_at_start_of_text():
    from typingapp.engine.scorer import current_word_at
    text = "start of text"
    assert current_word_at(text, 0) == "start"


def test_current_word_at_at_last_word():
    from typingapp.engine.scorer import current_word_at
    text = "the last word"
    assert current_word_at(text, len(text) - 1) == "word"


def test_current_word_at_on_whitespace_returns_empty():
    from typingapp.engine.scorer import current_word_at
    text = "two  words"  # double space at index 3-4
    assert current_word_at(text, 3) == ""


def test_current_word_at_out_of_bounds_returns_empty():
    from typingapp.engine.scorer import current_word_at
    text = "short"
    assert current_word_at(text, len(text)) == ""
    assert current_word_at(text, -1) == ""
    assert current_word_at(text, 999) == ""


def test_current_word_at_empty_text_returns_empty():
    from typingapp.engine.scorer import current_word_at
    assert current_word_at("", 0) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -k current_word_at -v`
Expected: FAIL with `ImportError: cannot import name 'current_word_at'`

- [ ] **Step 3: Add `current_word_at`**

In `typingapp/engine/scorer.py`, add this function after `normalize_mistake_word` and before the `Scorer` dataclass:

```python
def current_word_at(text: str, position: int) -> str:
    """Return the word (original case/punctuation, unlike normalize_mistake_word)
    containing text[position], or "" if position is out of bounds or lands on
    whitespace. Used for display purposes (e.g. the finger-hint coaching bar),
    not for mistake-tracking lookups."""
    if not text or position < 0 or position >= len(text):
        return ""
    if text[position].isspace():
        return ""
    start = text.rfind(" ", 0, position) + 1
    end = text.find(" ", position)
    if end == -1:
        end = len(text)
    return text[start:end]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorer.py -k current_word_at -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all previously-passing tests still pass, plus the 7 new ones

- [ ] **Step 6: Commit**

```bash
git add typingapp/engine/scorer.py tests/test_scorer.py
git commit -m "feat: add current_word_at display helper alongside Scorer"
```

---

### Task 3: Wire the finger-hint bar into `LessonScreen`

**Files:**
- Modify: `typingapp/screens/lesson.py`
- Modify: `typingapp/app.tcss`
- Test: `tests/test_lesson_screen_finger_hint.py` (new file)

**Interfaces:**
- Consumes: `finger_for_char(char: str) -> tuple[str, str] | None` (Task 1), `current_word_at(text: str, position: int) -> str` (Task 2).
- Produces: a new `Label(id="finger-hint-val")` row in `LessonScreen.compose()`, updated by a new `_update_finger_hint_label()` method called from `_tick()` (and once from `_start_lesson()` right after the initial render, so the hint shows immediately rather than waiting up to 0.25s for the first tick).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lesson_screen_finger_hint.py
import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Label

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
            self.push_screen(LessonScreen(custom_text="the quick fox"))

    return TestApp()


def test_finger_hint_shows_immediately_on_lesson_start(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "the" in text
            assert "next key" in text.lower()

    asyncio.run(run())
    storage.close()


def test_finger_hint_names_the_correct_finger_for_the_next_key(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            # target text is "the quick fox" — first char 't' is Left index
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "Left" in text
            assert "index" in text

    asyncio.run(run())
    storage.close()


def test_finger_hint_updates_as_the_user_types(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.press("h")
            await pilot.press("e")
            await pilot.press("space")
            await pilot.pause()
            # after typing "the ", the current word is "quick", next key is 'q' -> Left pinky
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "quick" in text
            assert "Left" in text
            assert "pinky" in text

    asyncio.run(run())
    storage.close()


def test_finger_hint_is_empty_when_lesson_is_complete(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            target = screen._scorer.target
            for ch in target:
                await pilot.press(ch if ch != " " else "space")
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            assert str(hint.content) == ""

    asyncio.run(run())
    storage.close()


def test_finger_hint_shown_in_book_mode_too(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text="word " * 200, cached_at="2026-07-27T10:00:00")
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "word" in text
            assert "next key" in text.lower()

    asyncio.run(run())
    storage.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lesson_screen_finger_hint.py -v`
Expected: FAIL — `#finger-hint-val` doesn't exist yet (`query_one` raises `NoMatches`).

- [ ] **Step 3: Add the CSS class**

In `typingapp/app.tcss`, add a new rule near the other `.stat-*` classes (e.g. right after `.err-value { color: #c77dff; }` or near `.wpm-value`/`.acc-value`):

```css
.finger-hint-value { color: #43b0f1; text-style: italic; }
```

- [ ] **Step 4: Add the import, the compose() row, and the update logic**

In `typingapp/screens/lesson.py`, add the import near the top (alongside the existing `typingapp.engine.scorer` import):

```python
from typingapp.engine.scorer import Scorer, normalize_mistake_word, current_word_at
from typingapp.engine.keyboard_map import finger_for_char
```

In `compose()`, add a new `Label` row right after the stats bar `Horizontal` block and before `yield ProgressBar(...)`:

```python
            yield Label("", id="finger-hint-val", classes="stat-label finger-hint-value")
```

(Full context — the existing block this goes after/before, for exact placement:)
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
```

Add a new method `_update_finger_hint_label` right after `_update_book_progress_label` (matching that method's placement style):

```python
    def _update_finger_hint_label(self) -> None:
        label = self.query_one("#finger-hint-val", Label)
        s = self._scorer
        if s is None or s.is_complete:
            label.update("")
            return
        word = current_word_at(s.target, s.position)
        next_char = s.target[s.position]
        finger = finger_for_char(next_char)
        if not word or finger is None:
            label.update("")
            return
        hand, digit = finger
        label.update(f"Next word: {word}  ·  next key {next_char!r} → {hand} {digit}")
```

Call this from `_start_lesson` (right after `self._render_text()`, so the hint appears immediately, before the first tick) and from `_tick()` (alongside the other per-tick label updates). In `_start_lesson`, change:

```python
        self._scorer = Scorer(text, strict_mode=app.config.strict_mode)
        self._scorer.start()
        self._render_text()
        self._timer = self.set_interval(0.25, self._tick)
```

to:

```python
        self._scorer = Scorer(text, strict_mode=app.config.strict_mode)
        self._scorer.start()
        self._render_text()
        self._update_finger_hint_label()
        self._timer = self.set_interval(0.25, self._tick)
```

In `_tick()`, add the call anywhere among the other label updates (e.g. right after the `#err-val` update, before `self._maybe_extend_text()`):

```python
        self.query_one("#err-val", Label).update(str(s.error_count))
        self._update_finger_hint_label()
        pct = int((s.position / max(len(s.target), 1)) * 100)
```

Also call it from `on_key`, right after `self._render_text()`, so the hint updates immediately on every keystroke rather than waiting up to 0.25s for the next tick (typing feels responsive; the tick-based update alone would introduce a visible lag between pressing a key and the hint catching up):

```python
        correct = self._scorer.process_key(key)
        self._render_text()
        self._update_finger_hint_label()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_lesson_screen_finger_hint.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `pytest -q`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add typingapp/screens/lesson.py typingapp/app.tcss tests/test_lesson_screen_finger_hint.py
git commit -m "feat: show current word and next-key finger hint during typing"
```

---

### Task 4: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing (documentation only).

- [ ] **Step 1: Add a new Architecture bullet**, immediately after the existing `typingapp/engine/keyboard_sanitize.py` bullet:

```markdown
- `typingapp/engine/keyboard_map.py` — `finger_for_char(char)` maps a character to `(hand, finger)` on a standard US-QWERTY touch-typing layout (e.g. `"q"` → `("Left", "pinky")`), or `None` for characters with no defined home (case-insensitive; uppercase maps to the same finger as lowercase). Used only for the finger-hint coaching display — has no bearing on scoring/correctness, which remains a pure character-equality check in `Scorer.process_key`.
```

- [ ] **Step 2: Add a new Key Invariant**, appended at the end of the Key Invariants section:

```markdown
- **The finger-hint bar (`#finger-hint-val`) is always visible, not gated by any `AppConfig` toggle** — unlike `highlight_past_mistakes` or `show_hints`, there is no setting to turn it off; it shows in both book mode and non-book mode. `LessonScreen._update_finger_hint_label` is called from three places to keep latency low: once in `_start_lesson` (so it's populated before the first tick), once per `_tick()` (~4x/second), and once per keystroke in `on_key` (so it updates instantly rather than waiting for the next tick). It reads `current_word_at` (in `engine/scorer.py`, display-oriented: preserves original case/punctuation) rather than `Scorer._word_at`/`normalize_mistake_word` (mistake-tracking-oriented: strips punctuation and lowercases) — these are deliberately two different word-extraction functions for two different purposes over the same underlying text, not a duplicate that should be consolidated.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document keyboard_map and the finger-hint coaching bar"
```

## Self-Review Notes

- **Spec coverage:** covers all of Stage C (item #4 from the original feedback batch) — a US-QWERTY finger map, a display-oriented current-word helper distinct from the existing mistake-tracking word helper, and the always-visible coaching bar wired into both rendering modes with three update call sites for low latency.
- **Placeholder scan:** none — every step has complete, ready-to-use code.
- **Type consistency:** `finger_for_char(char: str) -> tuple[str, str] | None` (Task 1) and `current_word_at(text: str, position: int) -> str` (Task 2) are each defined once and used with identical signatures in Task 3's `_update_finger_hint_label`. No naming drift between tasks.
