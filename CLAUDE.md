# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install textual pytest

# Run the app
python -m typingapp

# Run all tests
pytest

# Run a single test file
pytest tests/test_scorer.py -v
```

## Architecture

Python CLI typing tutor using the **Textual** framework. Key layers:

- `typingapp/engine/` — pure Python, no Textual dependency. `scorer.py` tracks keystrokes in real-time; `adaptive.py` manages difficulty levels 1–10; `lesson.py` selects lesson text (words/sentences/code/custom); `recommender.py` generates rules-based suggestions from DB stats; `sound.py` generates and plays short click/error tones via stdlib `winsound` (Windows only — silently disables itself elsewhere, never raises). `engine/content/` holds `words.txt`, `sentences.txt`, and `code_snippets.py` (the raw lesson corpora).
- `typingapp/data/storage.py` — SQLite via stdlib `sqlite3`. Stores `sessions` and `keystrokes` tables (schema in-file, created on connect via `CREATE TABLE IF NOT EXISTS`). DB at `~/.typingapp/history.db`.
- `typingapp/config.py` — `AppConfig` dataclass, JSON at `~/.typingapp/config.json`. Key setting: `strict_mode` (bool) blocks typing on error when True. `difficulty: 0` means "auto/unset" — `TypingApp.__init__` falls back to level 1 in that case. `key_sounds` (bool) toggles `SoundPlayer` playback in `LessonScreen`.
- `typingapp/screens/` — one Textual `Screen` per view (`menu`, `lesson`, `results`, `history`, `settings`, `custom_text`). Screens access shared state via `self.app.config`, `self.app.storage`, `self.app.adaptive`, `self.app.lesson_engine` — there is no other state container. Navigation is push/pop-based: Menu pushes Lesson (or Custom Text, which then pushes Lesson); Lesson `switch_screen`s to Results on completion; Results/History/Menu push each other via their own bindings.
- `typingapp/app.tcss` — global Textual CSS.

## Key Invariants

- `Scorer` is stateful per-lesson; create a new one each lesson (see `LessonScreen._start_lesson`).
- `AdaptiveEngine.current_level` persists on `app.adaptive` across lessons; it's written into `app.config.difficulty` only in `LessonScreen._finish()`, so `AppConfig.difficulty` on disk reflects the level as of the *last completed* lesson, not mid-lesson state.
- All DB writes happen in `LessonScreen._finish()` — a session row is inserted, then its keystroke rows referencing that `session_id`.
- Level transitions (`AdaptiveEngine.update_level`, `engine/adaptive.py`): level up requires `wpm >= LEVEL_WPM_THRESHOLDS[level]` AND `accuracy >= 95.0`; level down triggers on `accuracy < 80.0`; otherwise the level is unchanged. Levels clamp to 1–10.
- Weak-bigram detection (`AdaptiveEngine.detect_weak_bigrams`) flags any bigram with error rate ≥ 15% within a session; `LessonScreen` also queries `storage.fetch_bigram_heatmap()` (cross-session history) to bias word selection toward the user's weak spots.
- `SoundPlayer` (`engine/sound.py`) builds tones as in-memory WAV byte strings and plays them via `winsound.PlaySound(..., SND_MEMORY | SND_ASYNC)` — async so keystroke handling never blocks on audio. A prior attempt using the third-party `simpleaudio` package caused a native access-violation crash under rapid repeated playback (confirmed via testing), which is why this uses stdlib `winsound` instead — don't reintroduce a threaded/native audio library without re-testing rapid-fire playback first.
