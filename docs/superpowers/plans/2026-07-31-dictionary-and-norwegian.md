# Stage E Implementation Plan: Dictionary Popup + Norwegian Bokmål

Source design: `docs/superpowers/specs/2026-07-27-typing-coach-and-book-nav-design.md`, Stage E (items #7, #8, #9).

## Global Constraints

- Follow every existing invariant in `CLAUDE.md`. In particular:
  - `engine/` stays pure Python, no Textual dependency.
  - Network code (`engine/gutenberg.py` precedent) never raises — always returns `None`/`[]` on any failure, uses a `USER_AGENT` header, and a short timeout.
  - `LessonScreen`'s existing pattern for background network calls is a `@work(exclusive=True, thread=True, group=...)` worker posting back via `self.app.call_from_thread(...)` (see `BookSearchScreen._search_gutenberg`) — the dictionary lookup must follow the same pattern, since it's a real blocking HTTP call and must never freeze the UI.
  - Tests that mock network calls must patch at the **call site's** import path, not the definition's module (e.g. `patch("typingapp.screens.lesson.fetch_definition", ...)` if `lesson.py` does `from typingapp.engine.dictionary import fetch_definition`) — this bit the project before with `search_books` (see CLAUDE.md's "Testing gotcha" invariant).
  - Run `pytest -q` after every task; all existing tests must keep passing.
- Work happens in an isolated git worktree (`.claude/worktrees/dictionary-and-norwegian`, branch `worktree-dictionary-and-norwegian`), same as Stages C/D. Implementer subagents must verify they're on that branch before committing, and must never touch `master` directly.
- Confirmed from the design doc (already independently verified by a prior direct test against `dictionaryapi.dev`): the API only serves English definitions — 404 for every non-English `language` tried. This is a **confirmed limitation of the third-party API**, not something to "fix" by looking harder for a multi-language endpoint.

## Task 1 — `engine/dictionary.py` (pure, network, never-raises)

**New file** `typingapp/engine/dictionary.py`, modeled directly on `typingapp/engine/gutenberg.py`'s structure:

```python
from __future__ import annotations
import json
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError

DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"
TIMEOUT_SECONDS = 3
USER_AGENT = "Mozilla/5.0 (compatible; typingapp/1.0; +https://github.com/)"


def _get(url: str, timeout: float):
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def fetch_definition(word: str, language: str = "en") -> str | None:
    """Look up a short definition for `word`. dictionaryapi.dev only serves English
    definitions (confirmed: every non-English language tried 404s) -- short-circuit
    to None for any other language before making a network call, rather than making
    a request that's guaranteed to fail. Never raises; returns None on any failure
    (unreachable, 404, malformed response, empty word)."""
    word = word.strip()
    if not word or language != "en":
        return None
    url = f"{DICTIONARY_API_URL}/{quote(word)}"
    try:
        with _get(url, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError, OSError):
        return None
    try:
        entry = payload[0]
        meaning = entry["meanings"][0]
        part_of_speech = meaning.get("partOfSpeech", "")
        definition = meaning["definitions"][0]["definition"]
    except (KeyError, IndexError, TypeError):
        return None
    if part_of_speech:
        return f"({part_of_speech}) {definition}"
    return definition
```

Adjust field extraction if the real API response shape differs once tested — the response shape above matches dictionaryapi.dev's documented format (`[{"word": ..., "meanings": [{"partOfSpeech": ..., "definitions": [{"definition": ...}]}]}]`).

**New test file** `tests/test_dictionary.py`, mirroring `tests/test_gutenberg.py`'s `_mock_urlopen_returning` helper pattern:
- `test_fetch_definition_returns_formatted_string_on_success` — mock a realistic dictionaryapi.dev payload, assert the returned string contains the part of speech and definition text.
- `test_fetch_definition_returns_none_for_non_english_language` — call with `language="es"`, assert result is `None`, and assert `urlopen` was **never called** (via `MagicMock` call-count assertion) — this proves the short-circuit happens before any network attempt, not just that it happens to return None after a failed call.
- `test_fetch_definition_returns_none_on_network_error` — mock `urlopen` to raise `URLError`, assert `None`, no exception propagates.
- `test_fetch_definition_returns_none_on_404_style_empty_response` — mock a response body of `{"title": "No Definitions Found", ...}` (dictionaryapi.dev's actual 404 JSON shape) or malformed/empty JSON, assert `None`.
- `test_fetch_definition_returns_none_for_empty_word` — `fetch_definition("", "en")` and `fetch_definition("   ", "en")` both return `None` without attempting a network call.

Run `pytest tests/test_dictionary.py -v` before proceeding — this task has no Textual dependency and must be fully green in isolation.

## Task 2 — `Ctrl+D` dictionary popup in `LessonScreen`

**New file** `typingapp/screens/dictionary_popup.py`:

```python
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button
from textual.containers import Vertical
from textual.binding import Binding


class DictionaryPopupScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_popup", "Close"), Binding("enter", "dismiss_popup", "Close")]

    def __init__(self, word: str, definition: str | None) -> None:
        super().__init__()
        self._word = word
        self._definition = definition

    def compose(self) -> ComposeResult:
        with Vertical(id="dictionary-popup-body"):
            yield Static(f"📖  {self._word}", classes="menu-title")
            if self._definition:
                yield Static(self._definition, id="dictionary-definition")
            else:
                yield Static("No definition found.", id="dictionary-definition")
            yield Button("Close", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_dismiss_popup(self) -> None:
        self.dismiss()
```

Add minimal CSS to `typingapp/app.tcss` for `#dictionary-popup-body` (centered, bordered box — match the visual weight of other modal-ish elements already in the stylesheet, e.g. reuse `.menu-title`/existing card border patterns already defined there rather than inventing new colors).

**Edits to `typingapp/screens/lesson.py`:**
- Import: `from textual import work`, `from typingapp.engine.dictionary import fetch_definition`, `from typingapp.screens.dictionary_popup import DictionaryPopupScreen`.
- New `BINDINGS` entry: `("ctrl+d", "show_definition", "Dictionary")`.
- New method:
  ```python
  def action_show_definition(self) -> None:
      s = self._scorer
      if s is None or s.is_complete:
          return
      app = self.app      # type: ignore[attr-defined]
      language = app.config.language
      if language != "en":
          self.app.push_screen(DictionaryPopupScreen("", None))
          # DictionaryPopupScreen with definition=None already renders "No definition
          # found." -- but for the wrong-language case specifically, show a clearer
          # message instead. See note below: pass an explicit reason string instead.
          return
      word = current_word_at(s.target, s.position)
      if not word:
          lookahead = s.position
          while lookahead < len(s.target) and s.target[lookahead].isspace():
              lookahead += 1
          word = current_word_at(s.target, lookahead)
      if not word:
          return
      self._lookup_definition(word, language)

  @work(exclusive=True, thread=True, group="dictionary-lookup")
  def _lookup_definition(self, word: str, language: str) -> None:
      definition = fetch_definition(word, language)
      self.app.call_from_thread(self._show_definition_popup, word, definition)

  def _show_definition_popup(self, word: str, definition: str | None) -> None:
      self.app.push_screen(DictionaryPopupScreen(word, definition))
  ```
  **Refine the non-English short-circuit** before implementing: rather than pushing a popup with a made-up empty word, give `DictionaryPopupScreen` a third optional constructor param (or a dedicated `reason` string shown in place of "No definition found.") so the non-English case reads "Dictionary not available for this language yet" instead of a blank/odd word header. Simplest correct shape:
  ```python
  class DictionaryPopupScreen(ModalScreen):
      def __init__(self, word: str, definition: str | None, unavailable_reason: str = "") -> None:
          ...
      def compose(self) -> ComposeResult:
          ...
          if self._unavailable_reason:
              yield Static(self._unavailable_reason, id="dictionary-definition")
          elif self._definition:
              yield Static(self._definition, id="dictionary-definition")
          else:
              yield Static("No definition found.", id="dictionary-definition")
  ```
  And `action_show_definition`'s non-English branch becomes:
  ```python
  if language != "en":
      self.app.push_screen(DictionaryPopupScreen(word="", definition=None,
          unavailable_reason="Dictionary not available for this language yet"))
      return
  ```
  (Still needs `word = current_word_at(...)` computed first if you want the popup title to show the actual word even in the unavailable-language case — reasonable UX improvement, use judgement on ordering: compute `word` once up top before the language branch, so the title is populated either way.)
- Update `_footer_hint_text()` to add `Ctrl+D dictionary` to both the base and book-mode strings, in the same `·`-separated style as the existing entries.

**New test file** `tests/test_lesson_screen_dictionary.py`, following the pattern in `tests/test_lesson_screen_finger_hint.py` (same `_make_app` helper shape, Textual `App.run_test()` pilot):
- `test_ctrl_d_opens_popup_with_definition` — patch `typingapp.screens.lesson.fetch_definition` (**call-site path**, per the Global Constraints note) to return a fixed string, press `ctrl+d`, assert a `DictionaryPopupScreen` is now `app.screen` and the definition text appears.
- `test_ctrl_d_shows_no_definition_found_message` — patch `fetch_definition` to return `None`, press `ctrl+d`, assert the "No definition found." message appears.
- `test_ctrl_d_shows_unavailable_message_for_non_english_language` — config with `language="es"`, press `ctrl+d`, assert the popup shows "Dictionary not available for this language yet" **and** assert `fetch_definition`/the mocked network call was never invoked (mirrors Task 1's non-English short-circuit test, but at the screen layer).
- `test_escape_closes_dictionary_popup` — open the popup, press `escape`, assert `app.screen` is `LessonScreen` again (popped back).
- `test_ctrl_d_is_a_no_op_when_lesson_is_complete` — complete the lesson (existing pattern from `test_finger_hint_is_empty_when_lesson_is_complete`), press `ctrl+d`, assert no popup screen was pushed.

Because `_lookup_definition` is a `@work(thread=True)` worker, tests need `await pilot.pause()` after `ctrl+d` (possibly more than one, or a short poll) to let the worker thread complete and `call_from_thread` land before asserting — match whatever wait pattern `tests/test_book_search_screen.py` already uses for its worker-based assertions (reuse that exact idiom, don't invent a new one).

## Task 3 — Norwegian Bokmål (`"no"`)

- `typingapp/engine/lesson.py`: add `"no"` to `SUPPORTED_LANGUAGES = {"en", "es", "fr", "no"}`.
- New files `typingapp/engine/content/words_no.txt` and `typingapp/engine/content/sentences_no.txt` — **original content**, matching the existing es/fr precedent (not copied from any copyrighted source). Same rough size/format as `words_es.txt`/`sentences_es.txt` (check their line counts first with a quick `wc -l` and match the order of magnitude — likely a few hundred common Norwegian Bokmål words, and a comparable number of short original sentences). Content must be plain ASCII-safe for typing where possible; Norwegian's `æ`, `ø`, `å` are real letters (not decorative Unicode) and are **not** in `keyboard_sanitize`'s replacement table currently — check `typingapp/engine/keyboard_sanitize.py`'s translation table before writing the corpus:
  - If `æ`/`ø`/`å` are absent from its typeable-set/translation table, either (a) add them to the "typeable" allowlist (most correct — these are standard characters typeable via extended/Nordic keyboard layouts, and replacing them with ASCII lookalikes would produce non-Norwegian text), or (b) confirm with a quick check whether `sanitize_for_keyboard`'s default `layout="en-us-qwerty"` already passes through any character it doesn't recognize as needing replacement (i.e. only replaces characters it has an explicit rule for) — read the function before assuming either way, since this directly determines whether Norwegian text survives sanitization intact or gets mangled into spaces.
  - This check matters: if `sanitize_for_keyboard` currently treats "any non-ASCII character" as needing replacement (rather than "any character in an explicit disallow-list"), Norwegian text would get its æ/ø/å silently replaced with spaces on every lesson, which is a real functional bug for this feature, not a hypothetical.
- `typingapp/screens/settings.py`: add `("Norsk", "no")` to the `#sel-language` `Select` options list (line ~78).
- `typingapp/config.py`: no change needed — `language: str` is already a free-form string field with no validation/enum.

**New test file** `tests/test_lesson_engine_norwegian.py` (or extend an existing language-parametrized test file if one already covers es/fr symmetrically — check for e.g. `tests/test_lesson_engine.py` first and follow its existing structure/parametrization instead of duplicating):
- `test_norwegian_words_lesson_returns_words_from_corpus` — `LessonEngine().get_lesson(content_type="words", language="no", ...)` returns non-empty text built from `words_no.txt`.
- `test_norwegian_sentences_lesson_returns_sentences_from_corpus` — same for `content_type="sentences"`.
- `test_norwegian_falls_back_to_english_for_unknown_language_unaffected` — regression: confirm the existing `"xx" not in SUPPORTED_LANGUAGES -> falls back to en` behavior in `_content_filename` still works (unchanged logic, but worth a one-line assert since `SUPPORTED_LANGUAGES` was edited).
- If Norwegian corpus text contains æ/ø/å: `test_norwegian_special_characters_survive_sanitization` — call `sanitize_for_keyboard` directly on a string containing "æøå", assert those characters are unchanged (not replaced with spaces) — this is the regression test for the keyboard_sanitize check above, and must be written regardless of which resolution (a) or (b) was taken, since either way the *behavior* being locked in is "Norwegian special characters survive."

## Task 4 — CLAUDE.md documentation

Add new "Key Invariants" bullet points (append, don't reorder existing ones), covering:
- `engine/dictionary.py`'s never-raise/English-only-short-circuit contract, cross-referencing the existing Gutenberg-network-limitation invariant style already in the file.
- The `Ctrl+D` popup's `@work(thread=True)` pattern, explicitly noting it's the same pattern as `BookSearchScreen._search_gutenberg` (third use of this pattern in the codebase after Gutenberg search).
- `DictionaryPopupScreen` being the first `ModalScreen` use in this codebase, and why (tooltip-style overlay vs. the push/pop full-screen navigation used everywhere else).
- Norwegian's addition to `SUPPORTED_LANGUAGES`, and whatever resolution Task 3 reached for æ/ø/å in `keyboard_sanitize` (state which of (a)/(b) was true and why, so a future reader doesn't have to re-derive it).

## Self-Review Notes (things to double check before calling Stage E done)

- Confirm the actual JSON shape of a real `dictionaryapi.dev` response before finalizing `fetch_definition`'s parsing — the plan's field paths (`meanings[0].partOfSpeech`, `meanings[0].definitions[0].definition`) are from the documented API format but should be sanity-checked against a real response if network access is available in the dev/review environment; if not (matching this repo's known sandboxed-network limitation for gutendex.com), keep the parsing defensive (`try/except (KeyError, IndexError, TypeError)` around all field access, already in the plan above) so a shape mismatch degrades to `None` rather than crashing.
- The `keyboard_sanitize.py` æ/ø/å question in Task 3 is the one place this plan has a genuine open branch depending on existing code behavior not yet re-verified in this session — implementer must read that file first, not guess.
- Verify `_footer_hint_text()`'s two strings don't get too long for the footer widget's typical terminal width (already noted as a minor cosmetic finding, not blocking, in Stage D's final review) — Ctrl+D adds ~18 more characters; if it looks cramped, that's an acceptable, non-blocking cosmetic note to carry forward, not a blocker for this stage.
- Whole-branch final review (per established project pattern) should specifically check: does `action_show_definition` handle the book-mode case correctly (word lookup via `current_word_at` should work identically in book mode and non-book mode since both use the same `Scorer.target`/`position` — but confirm no book-specific interaction, e.g. popup appearing over/under the book progress bar, causes a layout issue).
