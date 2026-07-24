# Literature Text, Contextual Random Words & Rich Landscape UI — Design Spec

**Date:** 2026-07-24
**Builds on:** `docs/superpowers/specs/2026-07-16-typing-tutor-design.md`, `docs/superpowers/specs/2026-07-24-gamification-and-accuracy-design.md`

---

## Overview

This spec covers four related additions:

1. **Literature-mode lessons** sourced from Project Gutenberg's public-domain catalog (via the Gutendex API + Gutenberg's static text mirror), sized dynamically to the user's WPM and session duration, and extended live if the user finishes early.
2. **Contextual random-word generation** — a Markov-chain sentence generator as an alternative to pure word shuffling, producing human-readable (if not always grammatical) text instead of a word salad.
3. **Language selection** (English / Spanish / French) in Settings, affecting both Gutenberg source filtering and the local word/sentence corpora.
4. **A landscape-oriented, visually richer UI**: wide-terminal-first layouts for Settings and Results, teleprompter-style auto-scroll for long-form lesson text, and expanded keyboard navigation.

### Content sourcing & copyright boundary

Project Gutenberg exists specifically to distribute public-domain works — using its catalog for rotating typing-practice excerpts is exactly the kind of use it's built for. To stay clearly on the right side of that:

- **Fetched, not bundled.** Book excerpts are fetched live per session from Gutendex/Gutenberg and cached locally only as small, bounded slices (a few hundred words per cached entry, not full books), tagged with title/author/Gutenberg ID for attribution. Nothing is committed to the repository as permanent app content.
- **Original corpora.** The Spanish/French (and any refreshed English) word lists and seed sentences are original content written for this app, in the same spirit as the existing `words.txt`/`sentences.txt` — not copied from any source.
- **Markov generation is transformative.** Chains are built at runtime from the cached excerpt pool plus the original seed corpus, and sampled to produce new recombined sentences — not verbatim reproduction.

---

## 1. Literature Mode (Project Gutenberg)

### New module: `typingapp/engine/gutenberg.py`

Pure Python, isolated network I/O (uses stdlib `urllib.request`, no new HTTP dependency needed for simple GET+JSON):

- `search_books(language: str, limit: int = 20) -> list[BookMeta]` — queries `https://gutendex.com/books?languages={lang}&mime_type=text/plain` (short timeout, e.g. 3s), returns lightweight metadata (`gutenberg_id`, `title`, `author`, `text_url`).
- `fetch_excerpt(book: BookMeta, min_words: int, max_words: int) -> str | None` — downloads the book's plain-text file, strips the standard Gutenberg header/footer boilerplate (delimited by well-known `*** START OF ... ***` / `*** END OF ... ***` markers), picks a random contiguous slice within the requested word-count range from the body, and returns it. Returns `None` on any failure (timeout, 404, malformed text) — callers always have a fallback path.
- Both functions raise nothing to callers; internally catch `URLError`/`TimeoutError`/etc. and return empty/`None`.

### Caching: `gutenberg_cache` table (new, in `storage.py`)

```sql
CREATE TABLE IF NOT EXISTS gutenberg_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gutenberg_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    language TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    fetched_at TEXT NOT NULL
)
```

- `Storage.cache_excerpt(...)` / `Storage.fetch_cached_excerpts(language, limit)` / `Storage.prune_old_excerpts(keep_per_language=20)`.
- Pool refresh policy: on literature-mode lesson start, if the cached pool for the current language has fewer than a threshold (e.g. 5) entries, or the oldest entry is >24h old, attempt a background-style refresh (fetch 1–3 new excerpts synchronously with a short timeout budget before falling back — see error handling). Otherwise, serve instantly from cache and pick a random cached excerpt.
- This keeps most lesson starts instant and mostly offline-capable after first successful use, per the caching decision.

### Dynamic length calculation

In `LessonEngine` (or a new helper `engine/text_sizing.py`):

```
estimated_words = max(recent_avg_wpm, MIN_WPM_FLOOR) * (session_duration_seconds / 60) * SLACK_FACTOR
```

`recent_avg_wpm` comes from `storage.fetch_last_n_wpm(n=5)` averaged (falls back to a level-based estimate if no history). `SLACK_FACTOR` (~1.3) sizes the excerpt a bit longer than the literal estimate so most users don't run out of text before time's up, while dynamic extension (below) handles the rest.

### Dynamic extension mid-session

`LessonScreen` tracks remaining session time (already has `session_duration` wired from a prior round). When `Scorer.position` comes within a configurable trailing window (e.g. last 15% of `target`) **and** there's meaningful time left in the session, `LessonScreen` requests more text from `LessonEngine`/`gutenberg.py` (same source/book if literature mode, so it reads as continuous) and appends it to `Scorer.target` in place — `Scorer` gets a small `extend(more_text: str)` method that appends to `target` without resetting `position`/stats. If literature mode can't fetch more (offline mid-session), extension falls back to appending local sentence-corpus or Markov-generated text so the session never dead-ends.

---

## 2. Contextual Random Word Generation (Markov Chains)

### New module: `typingapp/engine/markov.py`

- `build_chain(corpus_sentences: list[str], order: int = 2) -> MarkovChain` — trains an n-gram (default trigram, order=2 means 2-word prefix → next-word) model from a list of sentences. Pure stdlib (`collections.defaultdict`).
- `MarkovChain.generate(word_count: int) -> str` — walks the chain from a random valid start state, sampling next-words weighted by observed frequency, stopping at or near `word_count` (rounds out to the next sentence-ending punctuation if the chain produces one, for a cleaner cutoff).
- Training corpus per lesson: the original local `sentences.txt` (per selected language) **plus** any cached Gutenberg excerpts for that language, if available — more source variety produces less repetitive/robotic output. If only the small local corpus is available (offline, empty cache), the chain still works, just with less variety.
- This becomes a new `content_type` option: `"random_sentences"` (name distinct from the existing `"words"` pure-shuffle mode and `"sentences"` fixed-corpus mode) — see Settings changes below.

---

## 3. Language Selection

- `AppConfig` gains `language: str = "en"` (values: `"en"`, `"es"`, `"fr"`).
- `engine/content/` gains `words_es.txt`, `sentences_es.txt`, `words_fr.txt`, `sentences_fr.txt` — original content I write, sized similarly to the existing English files (~150-300 words, ~15-20 sentences each).
- `LessonEngine._load_words()`/`_load_sentences()` take a `language` parameter and select the right file set (falls back to English if a requested language's files are somehow missing, as a defensive default rather than a crash).
- Gutendex queries use `languages={cfg.language}`.
- Settings screen gets a new "Language" `Select` (English / Español / Français) in the existing "Lesson Defaults" group.

---

## 4. UI: Landscape Layout & Visual Richness

### Settings screen
Per-row change only (not a card grid): widen the row layout so label and control sit further apart using the full terminal width, tighten vertical spacing between rows so more fits without scrolling on a typical wide terminal. New "Content type" options list gains `"random_sentences"` (Markov) and `"literature"` (Gutenberg) alongside existing `words`/`sentences`/`code`/`custom`. New "Language" selector row added to Lesson Defaults.

### Lesson screen — teleprompter auto-scroll
`#text-display` currently renders the full target text in one `Static` with no scroll handling — fine for short word/sentence lessons, but literature excerpts can be hundreds of words. Changes:
- Wrap `#text-display` in a `VerticalScroll` container with a bounded height (e.g. `max-height: 40%` of screen) instead of `height: auto`.
- After each `_render_text()`, if the current cursor position's rendered line is outside the visible scroll window, scroll the container so the cursor line sits roughly 1/3 from the top (a teleprompter convention — keeps upcoming text visible without the cursor pinned to the very top or bottom).
- Stats bar, progress bar, and hint bar stay fixed above/below the scrolling text region so the "always visible" chrome doesn't scroll away.

### Results screen — card layout + richer color coding
- Restructure Performance/Bigrams/Words sections into side-by-side bordered panels using Textual's grid layout (`grid-columns` via CSS), falling back to stacked layout automatically on narrow terminals (Textual CSS media-query-style width checks, or a simple runtime check of `self.size.width` swapping a CSS class).
- Accuracy bar color shifts by value (red <80%, yellow 80–95%, green ≥95%) instead of a fixed green, giving at-a-glance quality signal.
- Existing P/B/W jump shortcuts remain. New: **Left/Right arrow keys move focus between cards**; **Up/Down scrolls within the focused card** if its content overflows. Implemented via Textual's native focus chain (cards become focusable containers) plus explicit `action_focus_next_card`/`action_focus_previous_card` bound to arrow keys.

### "Fit on one screen, else scroll" principle
No new global mechanism needed — this is the existing `ScrollableContainer` pattern already used on Settings/History/Results, kept consistent: content that fits, fits; content that doesn't, scrolls. The card layout changes above are what reduce the common case to fitting in one view on a wide terminal, rather than a new constraint mechanism.

---

## 5. Data Model Summary

New/changed in `storage.py`:
- `gutenberg_cache` table (new, described above).
- No changes to `sessions`/`keystrokes`/`gamification`/`badges` schemas from prior specs.

New in `config.py`:
- `language: str = "en"`
- `content_type` gains two new valid values: `"random_sentences"`, `"literature"` (existing field, no schema change, just new accepted values validated at the UI layer).

---

## 6. Error Handling

- All Gutenberg/Gutendex network calls: short timeout (3s), caught exceptions, `None`/empty-list return — never raise into UI code.
- Literature-mode lesson with an empty cache and a failed live fetch: falls back to `random_sentences` (Markov) mode for that lesson, with a small non-blocking notice in the hint bar ("📡 Offline — using local text"), not a blocking error screen.
- Mid-session dynamic extension failure: falls back the same way, silently, without interrupting the typing flow.
- Markov chain trained on an empty/too-small corpus (e.g. a language's local sentence file somehow empty): `MarkovChain.generate()` falls back to plain word-shuffle output (reusing existing `_build_word_lesson` logic) rather than raising or returning empty text.
- Missing language-specific content files at runtime: defensive fallback to English, logged (not user-facing error).

---

## 7. Testing

Following the existing per-module `pytest` convention:

- `tests/test_gutenberg.py` — `search_books`/`fetch_excerpt` tested with mocked `urllib` responses (success, timeout, malformed JSON, missing boilerplate markers); no real network calls in the test suite.
- `tests/test_markov.py` — chain training determinism given a fixed seed, generation respects approximate word-count target, handles tiny/empty corpus gracefully, sentence-ending cutoff behavior.
- `tests/test_text_sizing.py` — WPM/duration → word-count formula boundary cases (zero history, very high/low WPM).
- `tests/test_storage.py` — extend with `gutenberg_cache` CRUD, pruning behavior.
- `tests/test_scorer.py` — extend with `Scorer.extend()`: appends to target without resetting position/stats, `is_complete` recalculates correctly against the new longer target.
- `tests/test_config.py` — extend for `language` field default/round-trip.
- Screen-level behavior (auto-scroll, card focus navigation, layout) verified via manual Textual test-pilot probes, consistent with how prior UI work in this project has been verified (no existing screen-level automated tests in this codebase).

---

## 8. Dependencies

No new third-party dependencies — `urllib.request` (stdlib) is sufficient for the simple GET+JSON/GET+text calls Gutendex and the Gutenberg mirror require. `README.md`/`CLAUDE.md` updated to note the app makes outbound network calls in literature mode (with the offline-fallback behavior documented so it's clear network access is optional, not required).

---

## 9. Out of Scope

- Languages beyond English/Spanish/French.
- User-submitted/custom Gutenberg book selection (always randomized from search results, matching "choose them randomly" from the request).
- Persisting full book texts locally (only bounded cached excerpts, per the copyright-boundary note above).
- Offline bundling of Gutenberg content at install time — the cache is populated lazily at runtime, not pre-seeded.
