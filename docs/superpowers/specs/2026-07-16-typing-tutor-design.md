# Typing Tutor CLI — Design Spec

**Date:** 2026-07-16
**Platform:** CLI (Terminal)
**Language:** Python 3.10+
**TUI Framework:** Textual

---

## Overview

A terminal-based typing tutor that teaches users to type faster and more accurately. Runs as a Python CLI app using the Textual framework for a vibrant, colorful TUI. Tracks all sessions in a local SQLite database and provides adaptive difficulty, progress charts, mistake heatmaps, and AI-style recommendations.

---

## Architecture

```
typingapp/
  __main__.py              # entry point: python -m typingapp
  app.py                   # Textual App root, screen routing
  screens/
    menu.py                # main menu
    lesson.py              # active typing session
    results.py             # post-session summary
    history.py             # progress dashboard (chart + heatmap + recommendations)
    settings.py            # settings screen
  engine/
    lesson.py              # lesson text selection and difficulty control
    scorer.py              # real-time WPM, accuracy, error tracking
    adaptive.py            # adaptive difficulty algorithm
    recommender.py         # generates recommendations from DB stats
    content/
      words.txt            # top 1000 common English words
      sentences.txt        # prose passages
      code_snippets.py     # Python/JS code samples
  data/
    storage.py             # SQLite read/write via stdlib sqlite3
  config.py                # user settings (loaded from ~/.typingapp/config.json)
```

**Data flow:**
Menu → select content type → Lesson screen (live typing + real-time stats) → Results screen (session summary + mistake heatmap) → saved to DB → optionally navigate to History screen.

---

## Screens

### Main Menu
- Options: Start Lesson, History & Progress, Settings, Quit
- Shows a brief stat summary (last session WPM, current streak)

### Lesson Screen
- **Stats bar** (top): live WPM, accuracy %, elapsed time, error count — updates on every keystroke
- **Progress bar**: percentage through the current lesson text
- **Text display**: correctly typed text (green), current error position (red highlight), remaining text (dimmed)
- **Adaptive hint bar** (bottom): coaching nudge when a problematic bigram is detected (e.g. "You're struggling with 'th' — slow down slightly")
- **Keyboard shortcuts**: ESC pause, Ctrl+R restart, Ctrl+Q quit

### Results Screen
- Final WPM, accuracy, time, total errors
- Top 5 most-missed keys/bigrams for this session
- Options: Retry same lesson, New lesson, View History, Menu

### History & Progress Dashboard
- **WPM trend**: ASCII bar chart of last 14 sessions
- **Summary stats**: best WPM, average accuracy, total sessions
- **Mistake heatmap**: bigrams ranked by cumulative error frequency (color-coded red → white)
- **Recommendations**: locally generated text suggestions based on DB patterns

### Settings Screen
- **Strict mode** (boolean toggle): ON = must fix each error before continuing; OFF = errors are tracked silently and typing continues
- Default content type (Words / Sentences / Code / Custom)
- Session duration (30s / 60s / 120s / custom)
- Starting difficulty (Auto / 1–5)
- Show live WPM (toggle)
- Show adaptive hints (toggle)
- Settings saved to `~/.typingapp/config.json`

---

## Engine

### Lesson & Content
- **Words**: random selection from `words.txt`, weighted toward user's weak spots
- **Sentences**: random passage from `sentences.txt`
- **Code**: random snippet from `code_snippets.py`
- **Custom**: user enters text via a Textual `TextArea` widget on a dedicated "Custom Text" setup screen before the lesson starts

### Adaptive Difficulty
- After each session, the engine scores performance: WPM relative to current level threshold + accuracy
- If WPM ≥ threshold and accuracy ≥ 95%: level up
- If accuracy < 80%: level down
- Levels 1–10 control: word complexity, passage length, code symbol density
- Adaptive hint fires when any bigram error rate exceeds 15% within a session

### Scorer (real-time)
- WPM = (correct characters typed / 5) / elapsed minutes
- Accuracy = correct keystrokes / total keystrokes × 100
- Per-keystroke event logged: character, expected, correct/incorrect, timestamp

### Recommender
- Queries DB for last 30 sessions
- Rules-based logic (no external AI dependency):
  - WPM plateau (< 5% improvement over 7 sessions) → suggest focused bigram drills
  - Accuracy < 90% average → suggest strict mode
  - Content-type gap (e.g. code sessions much slower than word sessions) → suggest more code practice
  - Streak of good sessions → positive reinforcement message

---

## Database

**Location:** `~/.typingapp/history.db` (SQLite via stdlib `sqlite3`)

**Tables:**

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    content_type TEXT NOT NULL,       -- 'words' | 'sentences' | 'code' | 'custom'
    difficulty INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL,
    wpm REAL NOT NULL,
    accuracy REAL NOT NULL,
    error_count INTEGER NOT NULL,
    strict_mode INTEGER NOT NULL      -- 0 or 1
);

CREATE TABLE keystrokes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    expected TEXT NOT NULL,           -- expected character
    actual TEXT NOT NULL,             -- typed character
    correct INTEGER NOT NULL,         -- 0 or 1
    bigram TEXT,                      -- two-char context window
    timestamp_ms INTEGER NOT NULL
);
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `textual` | TUI framework (screens, widgets, layout, keyboard events) |
| `rich` | Colors, tables, styled text (Textual includes this) |

No other third-party dependencies. SQLite and JSON config use Python stdlib only.

---

## Install & Run

```bash
pip install textual
python -m typingapp
```

Or with pipx for isolated install:
```bash
pipx install .
typing
```

---

## File Storage

| Path | Contents |
|------|---------|
| `~/.typingapp/history.db` | SQLite session + keystroke data |
| `~/.typingapp/config.json` | User settings (strict mode, defaults, etc.) |
