# Design: Chunk Navigation (Ctrl+Up/Down) + Inline Dictionary Panel

Date: 2026-08-01

## Motivation

Two usability gaps in book-reading session mode:

1. There's no way to jump to the start/end of the currently-loaded chunk of text
   without leaving the chunk entirely (existing Ctrl+Left/Right/Home jump across
   `CHARS_PER_PAGE`-sized book pages, which is a coarser, offset-based operation).
2. The dictionary lookup (Ctrl+D) opens a `ModalScreen` popup that must be
   dismissed before typing can resume, and has no way to browse a long definition
   (no scrolling) or read it side-by-side while continuing to type.

## A. Chunk navigation: Ctrl+Up / Ctrl+Down

Book-mode-only (no-op when `self._book_id` is empty), same gating pattern as the
existing `action_next_page`/`action_previous_page`/`action_book_home`.

- **`Ctrl+Up` → `action_jump_chunk_start`**: sets `self._scorer.position = 0`,
  re-renders, and rescrolls to the top of the currently loaded chunk.
- **`Ctrl+Down` → `action_jump_chunk_end`**: sets
  `self._scorer.position = len(self._scorer.target)`, re-renders, and rescrolls
  to the bottom of the currently loaded chunk.

Both are **within-chunk, skip-without-scoring** operations — the same mechanic
the existing page-jump invariant already documents for Ctrl+Left/Right (the
skipped span is never added to `Scorer.keystrokes`/`error_count`), just scoped
to the chunk currently held in memory rather than to an absolute book offset.
Consequences of this scoping:

- No new `Scorer` is constructed (unlike Ctrl+Left/Right/Home, which rebuild via
  `_start_lesson()`). This is purely a `position` change on the existing `Scorer`.
- No `storage.update_book_progress` call — chunk-internal navigation doesn't
  change the book's persisted reading offset. (Whichever of `_current_book_offset`'s
  two inputs is behind will naturally catch up: `_persist_book_progress` still
  fires on quit/menu-nav/periodic tick and computes from the live cursor.)
- `action_jump_chunk_end` naturally makes `Scorer.is_complete` true. This already
  means exactly what it means when the user types to the end of a chunk normally:
  the existing `_tick()` → `_maybe_extend_text()` flow fetches more text on the
  next tick. No new branch is needed for this — it falls out of existing behavior.
- Neither action is available outside book mode; `_footer_hint_text()`'s book-mode
  string gains `Ctrl+↑/↓ chunk start/end`.

## B. Inline dictionary panel (replaces the popup)

`typingapp/screens/dictionary_popup.py` (`DictionaryPopupScreen`, a `ModalScreen`)
is deleted. Dictionary lookups now render inline within `LessonScreen` itself, in
**every** content type (words/sentences/custom/literature/book mode) — this is not
a book-mode-specific feature; only the chunk-navigation shortcuts in section A are
book-mode-gated.

### Layout

A new focusable `VerticalScroll` widget, `#dictionary-panel`, wrapping a
`Static#dictionary-panel-content`, inserted in `compose()` between `#text-scroll`
and `#hint-bar`. Collapsed (zero/near-zero height, no visible border) when there
is no active definition; expands to show content once a lookup succeeds or fails.

### State (persists across `_start_lesson()` rebuilds)

Two new `LessonScreen` instance attributes, initialized once in `__init__` (NOT
reset in `_start_lesson()`, unlike `_dictionary_lookup_in_progress`):

- `self._dictionary_word: str = ""` — the normalized word the panel currently
  shows a definition for (empty means panel is empty/collapsed).
- `self._dictionary_definition_markup: str = ""` — the rendered markup content
  to show (definition text, "No definition found.", or the non-English
  unavailable-reason message).

Because these survive `_start_lesson()`, a page jump / chunk extension / restart
does not clear an open definition — only `Ctrl+Shift+D` or leaving the lesson
(quit/menu/finish) does. `_start_lesson()` must re-render the panel from this
persisted state after building the new `Scorer` (so the panel doesn't blank out
on every chunk rebuild even though its content is still valid).

### `Ctrl+D` — `action_show_definition`

Reworked from "always trigger a fresh lookup and push a popup" to a two-mode
action depending on whether the word under the cursor matches what's already
shown:

1. Compute `word` under the cursor exactly as today (via `current_word_at` with
   the existing whitespace-lookahead fallback), then `lookup_word =
   normalize_mistake_word(word)`.
2. **If `lookup_word != self._dictionary_word`** (including the panel being
   empty): this is a new word — proceed with the existing lookup flow (worker
   thread via `@work(exclusive=True, thread=True, group="dictionary-lookup")`,
   same `fetch_definition`/non-English short-circuit logic as today), then
   populate `_dictionary_word`/`_dictionary_definition_markup` and update the
   panel. Focus remains on the typing area — the user can keep typing while the
   definition is visible.
3. **If `lookup_word == self._dictionary_word`** (i.e. a second Ctrl+D press
   without the cursor having moved to a different word in between): no network
   call — instead, move focus into `#dictionary-panel` so the user can scroll it
   with arrow keys (Textual's `VerticalScroll` is natively focusable/scrollable;
   no custom key handling needed for the scrolling itself).
4. Existing guards carry over unchanged: no-op if `s is None or s.is_complete`;
   no-op if a lookup is already `_dictionary_lookup_in_progress`; non-English
   `language` still short-circuits to a fixed unavailable-reason message with no
   network call, populated via the same word-differs/word-same branching above
   (so a second Ctrl+D on an unavailable-language word still just focuses the
   panel rather than re-showing the same message).

### `Escape` — focus-dependent

- If `#dictionary-panel` currently has focus: a new `action_defocus_panel`
  returns focus to the typing area. Does **not** pause the session and does
  **not** clear the panel's content.
- If the typing area has focus (the panel is unfocused, regardless of whether it
  has content): unchanged existing behavior, `action_pause`.

This requires checking `self.focused` (or equivalent) in the `escape` binding's
handler to decide which of the two actions applies, since Textual's binding
resolution is otherwise a single static action per key.

### `Ctrl+Shift+D` — `action_clear_definition`

New binding. Clears `_dictionary_word`/`_dictionary_definition_markup` back to
empty, collapses the panel, and — if the panel currently has focus — returns
focus to the typing area. Works in any content type, whether or not the panel
currently has focus.

### Footer hint text

`_footer_hint_text()` gains dictionary-related entries reflecting the new
bindings (`Ctrl+D dictionary`, already present, stays; no separate footer entry
is needed for focus-in since it's the same key, but `Ctrl+Shift+D clear` is
added) in both the base and book-mode strings.

## Testing

- `tests/test_lesson_screen_book_page_nav.py` (or a new
  `test_lesson_screen_chunk_nav.py`): Ctrl+Up/Down move `position` to
  `0`/`len(target)` without touching `keystrokes`/`error_count`/persisted book
  offset; no-op outside book mode; `is_complete` after Ctrl+Down triggers the
  existing extension path on the next tick.
- `tests/test_lesson_screen_dictionary.py` (rewritten from popup-based to
  inline-panel-based assertions): first Ctrl+D populates the panel and leaves
  focus on the typing area; second Ctrl+D on the same word moves focus to the
  panel; Ctrl+D on a different (moved-to) word re-triggers a lookup instead of
  focusing; Escape while panel-focused returns focus without pausing; Escape
  while typing-focused still pauses; Ctrl+Shift+D clears content and collapses
  the panel from both focus states; non-English short-circuit still shows the
  unavailable-reason message inline with no network call; panel content survives
  a page jump (`action_next_page`) in book mode.
- Delete `tests/test_lesson_screen_dictionary.py`'s now-obsolete
  `DictionaryPopupScreen`-specific assertions (screen-push/pop, `app.screen`
  identity checks) along with the deleted module.

## Out of scope

- No changes to `fetch_definition`/`engine/dictionary.py` itself — the network
  contract, English-only short-circuit, and never-raise guarantee are unchanged.
- No changes to non-book literature/random-sentences extension behavior.
- No new CSS design system — the panel reuses the existing dark-bordered-box
  visual language already established by `#text-scroll` and the (now deleted)
  `#dictionary-popup-body`.
