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

- `typingapp/engine/` — pure Python, no Textual dependency. `scorer.py` tracks keystrokes in real-time; `adaptive.py` manages difficulty levels 1–10; `lesson.py` selects lesson text; `recommender.py` generates rules-based suggestions from DB stats.
- `typingapp/data/storage.py` — SQLite via stdlib `sqlite3`. Stores `sessions` and `keystrokes` tables. DB at `~/.typingapp/history.db`.
- `typingapp/config.py` — `AppConfig` dataclass, JSON at `~/.typingapp/config.json`. Key setting: `strict_mode` (bool) blocks typing on error when True.
- `typingapp/screens/` — one Textual `Screen` per view. Screens access shared state via `self.app.config`, `self.app.storage`, `self.app.adaptive`, `self.app.lesson_engine`.
- `typingapp/app.tcss` — global Textual CSS.

## Key Invariants

- `Scorer` is stateful per-lesson; create a new one each lesson.
- `AdaptiveEngine.current_level` persists on `app.adaptive` across lessons (only saved to config on lesson end).
- All DB writes happen in `LessonScreen._finish()`.
