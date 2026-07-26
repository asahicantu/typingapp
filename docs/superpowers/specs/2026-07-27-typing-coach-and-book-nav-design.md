# Typing Coach, Book Navigation & Dictionary — Design

## Context

A batch of 12 feedback items came in at once, ranging from data-consistency bugs to large new subsystems (finger-hint typing coach, an in-session word dictionary, book page navigation with split accuracy tracking, a new language, and character sanitization). This doc decomposes the batch into independently shippable sub-projects, each with its own scope boundary, so each can be planned and implemented as its own increment rather than one giant change.

Items #1 and #2 (stale `selected_book_id`, "always starts random") were root-caused as a single data-consistency bug: the user's saved config pointed at a book (`gutenberg:1`) never actually cached in the `books` table (traced to leftover state from earlier debugging sessions writing directly to the real config file). Already fixed by repointing the config at an actually-cached book. The remaining code gap — Settings showing an unhelpful "(not cached yet)" instead of clearly explaining *why* and how to recover — is folded into Stage B below since it's a small, related UI fix.

## Decomposition into stages

Each stage is independently buildable, testable, and reviewable. Order reflects: safety issues that block typing entirely first, then small UX wins, then the larger new subsystems, with the dictionary/language work last since it depends on nothing else being unfinished.

### Stage A — Character sanitization (items #3, #11)
**Problem:** real book text contains Unicode punctuation not reachable on a US-QWERTY keyboard (curly quotes `“ ”`, em/en-dashes `— –`, ellipsis `…`, etc.) — a user hits these characters and can never physically type them, permanently stalling the session (or endlessly erroring in non-strict mode).

**Design:** a new pure function in `engine/`, e.g. `engine/keyboard_sanitize.py`:
- `sanitize_for_keyboard(text: str, layout: str = "en-us-qwerty") -> str` — walks the text and replaces every character not on the given layout's typeable set with its closest ASCII equivalent via a translation table (curly quotes → `'`/`"`, en/em-dash → `-`, ellipsis → `...`, non-breaking space → normal space, etc.), and any character with no reasonable equivalent gets replaced with a single space (never removed outright, to keep character offsets/counts stable for book-progress tracking).
- Applied once, at the point book/random-sentence text is chunked for typing (`LessonEngine`/`book_text.chunk_from_offset` output, and the local `words.txt`/`sentences.txt` corpora as a defensive pass too, though those are already ASCII-only by construction).
- Keeping offsets stable (never deleting a character) matters because book progress (`current_offset`) is measured in raw characters of the *original* full_text — sanitization must happen on the chunk right before constructing `Scorer`, not on the stored `full_text`, so `book_progress`/page-percent math (already built) stays correct without needing to change.

**Testable in complete isolation** — pure text-in-text-out function, no Textual/network/DB involvement. Ships first, fixes the actual "can't type past this character" complaint immediately.

### Stage B — In-session UX polish (items #5, #10, #12, + the Settings clarity fix for #1)
- **#5 Live settings shortcuts in session mode:** new keybindings in `LessonScreen` (e.g. `Ctrl+S` toggle strict mode, `Ctrl+K` toggle key sounds) that flip `app.config.*` and persist immediately via `save_config`, with a brief on-screen confirmation ("Strict mode: ON").
- **#12 Mistake-word highlighting:** `Scorer.word_errors` already tracks per-word miss counts across the *current* session; extending this to color words the user has mistyped in *any* prior session requires a small new read from `storage` (a `fetch_frequently_missed_words()`-style query over `keystrokes`, or reusing the existing bigram-heatmap idea at word grain) — words appearing there render in light orange in `_render_text`/`_render_book_text`. New `AppConfig.highlight_past_mistakes: bool = True` toggle in Settings.
- **#10 Mode-aware session UI:** once Stage C's finger-hint bar and Stage D's book-nav shortcuts exist, revisit `LessonScreen.compose()`'s footer-hint construction (already partially mode-aware — see the book-mode-only Ctrl+F line from the previous round) to show the right shortcut set for Text mode vs. Literature mode in one consistent place, rather than several independent conditionals.
- **Settings clarity fix:** `_book_display_text` shows `⚠ "{id}" isn't cached — pick a book via Browse Books or My Books` instead of the bare "(not cached yet)", so this exact stale-state situation is self-explanatory if it ever recurs.

### Stage C — Typing coach: current word + finger-hint preview (item #4)
**Design:** new `engine/keyboard_map.py` — a static dict mapping each US-QWERTY key to `(hand, finger)` (e.g. `"q": ("left", "pinky")`, `"j": ("right", "index")`), covering letters, digits, and common punctuation. A pure function `finger_for_char(char: str) -> tuple[str, str] | None` (None for characters with no fixed home, e.g. space uses either thumb — treated as a special case).

New always-visible label row in `LessonScreen.compose()` (below the stats bar, per your chosen mockup): shows the current word (via `Scorer`'s existing word-boundary logic, refactored into a small reusable `current_word_at(text, position)` helper) and the very next character's required finger, e.g. `Next word: quickly · next key 'q' → Left pinky`. Updates every `_tick()` alongside the other stats labels — cheap, no new timer needed.

### Stage D — Book page navigation + split accuracy (item #6)
**Design:** new `LessonScreen` bindings in book mode only — `Ctrl+Right` (next page) / `Ctrl+Left` (previous page), both currently unbound — to jump the book's reading offset forward/backward by one page (`CHARS_PER_PAGE`, already defined in `book_text.py`), skipping the skipped span without ever constructing a `Scorer` over it — so no keystrokes are recorded for skipped text, but `book_progress.current_offset` still advances (or rewinds) to reflect the new position. This directly satisfies "if page is skipped still track book progress but do not count the words." A third binding, `Ctrl+Home` (jump to page 1 / the very start of the book, for skipping past a prologue/index straight to Chapter 1), also currently unbound.
**Accuracy split:** `Scorer` already accumulates `_total_keys`/`_correct_keys` globally; skipped pages never touch `Scorer` at all under this design, so the existing accuracy calculation is already exactly "correct vs incorrect among words actually typed" — no `Scorer` changes needed, just confirming/testing that invariant explicitly once page-skip exists (a regression risk worth a dedicated test: skip a page, type some more, assert accuracy reflects only the typed portion).

### Stage E — Dictionary popup + Norwegian Bokmål + per-language dictionary wiring (items #7, #8, #9)
**Design:**
- **#7 Dictionary popup:** new `engine/dictionary.py` — `fetch_definition(word: str, language: str) -> str | None` hitting the free `dictionaryapi.dev` REST API (same never-raise, timeout-guarded contract as `gutenberg.py`), called from a new `LessonScreen` keybinding (`Ctrl+D`) that looks up the *current* word (reusing Stage C's `current_word_at` helper) and shows the result in a Textual `ModalScreen` popup (first use of a modal in this codebase — appropriate here since a tooltip-style overlay is exactly what `ModalScreen` is for, unlike the push/pop full-screen navigation used everywhere else). Runs the network call in a `@work(thread=True)` worker (same pattern established for Gutenberg search) so it never freezes typing.
- **#8 Norwegian Bokmål:** add `"no"` to `AppConfig`'s language options and `LessonEngine.SUPPORTED_LANGUAGES`, plus new `words_no.txt`/`sentences_no.txt` corpora (original content, matching the existing es/fr precedent — not copied from a copyrighted source).
- **#9 Per-language dictionary wiring — confirmed gap, resolved:** directly tested `dictionaryapi.dev` against es/fr/no/de words — it only serves English (404 for every non-English language tried, not just missing individual words). Per your direction, Stage E ships **English-only** real definitions; `fetch_definition` still takes a `language` param for future-proofing, but for any non-English `language` it short-circuits to a `None` result before making a network call, and `LessonScreen`'s popup shows "Dictionary not available for this language yet" rather than a silent failure or a misleading empty-looking popup. This is documented as a known, intentional limitation (not a bug) in CLAUDE.md once implemented, alongside the existing Gutenberg-network-limitation note style already established there.

## Staging rationale

Each stage is a fully separate `writing-plans` cycle — A is small and ships alone; B is UI polish touching only existing screens; C and D are new but self-contained subsystems; E is the largest and most externally-dependent (a new network integration + new corpus content), so it goes last and doesn't block anything else.

## Out of scope for now
- Any keyboard layout other than US-QWERTY (explicitly assumed per the original request).
- Bundled/offline dictionary data (deferred per your choice of the free-API approach).
- Reworking `content_type` selection UX beyond what Stage B's Settings clarity fix covers.
