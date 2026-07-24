# Gamification, Accurate Feedback & Challenge Mode — Design Spec

**Date:** 2026-07-24
**Builds on:** `docs/superpowers/specs/2026-07-16-typing-tutor-design.md`

---

## Overview

This spec covers a set of improvements to the existing typing tutor:

1. Bug fixes that undermine accurate feedback (dead `session_duration` setting, wrong mistake-bigram data on the Results screen, noise-sensitive plateau detection).
2. A gamification layer: XP/levels (separate from the existing 1–10 adaptive difficulty), achievement badges, daily streaks, and a live combo/momentum meter.
3. A new **Challenge** section: a timed test tuned to the level above the user's current one — scoring ≥80% accuracy immediately unlocks that next level.
4. Per-key sound effects (distinct tones for correct vs. incorrect keystrokes), toggleable in Settings.
5. Richer, more colorful, more responsive UI to support the above.

Goal throughout: every piece of feedback shown to the user must be *accurate* (reflect what actually happened in that session) and should nudge practice toward the user's actual weak points — not just be decorative.

---

## 1. Bug Fixes

### 1.1 `session_duration` is dead
`AppConfig.session_duration` is set in Settings but never read. Fix: `LessonScreen` ends a lesson when **either** the text is fully typed **or** `session_duration` seconds have elapsed, whichever comes first. On timeout, `_finish()` scores whatever was typed up to that point (partial completion is valid — WPM/accuracy are already computed from keystrokes typed so far, not from full-text completion).

### 1.2 Results screen shows the wrong mistakes
`ResultsScreen.compose()` currently calls `storage.fetch_bigram_heatmap()` (global, cross-session cumulative data) and labels it "TOP MISTAKE BIGRAMS" right after a single lesson — misleading. Fix: compute mistake bigrams from `self._scorer.keystrokes` (this session only). The global heatmap remains correctly scoped to the History screen.

### 1.3 Recommender plateau detection is noise-sensitive
`Recommender.recommend()` currently compares only `wpms[0]` vs `wpms[-1]` of the last 7 sessions to detect a plateau — a single lucky or unlucky session skews the verdict. Fix: compare the average of the first half of the window vs. the average of the second half (e.g. first 3 vs. last 3, dropping the middle for odd counts, or a simple linear regression slope — first-half/second-half average is sufficient and easy to reason about). Threshold stays effectively the same (<5% relative improvement).

---

## 2. Data Model

New tables in `typingapp/data/storage.py`:

```sql
CREATE TABLE IF NOT EXISTS gamification (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    xp INTEGER NOT NULL DEFAULT 0,
    gamer_level INTEGER NOT NULL DEFAULT 1,
    current_streak_days INTEGER NOT NULL DEFAULT 0,
    longest_streak_days INTEGER NOT NULL DEFAULT 0,
    last_practice_date TEXT
);

CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    earned_at TEXT NOT NULL
);
```

`gamification` is a singleton row (`id=1`), inserted on first `Storage` init if absent.

`sessions` gains three columns (added via `ALTER TABLE` guarded by a `PRAGMA table_info(sessions)` check in `Storage.__init__`, so existing databases upgrade in place):

- `xp_earned INTEGER NOT NULL DEFAULT 0`
- `max_combo INTEGER NOT NULL DEFAULT 0`
- `is_challenge INTEGER NOT NULL DEFAULT 0`

Badge *definitions* (code, name, description, predicate) live in `engine/gamification.py`, not the DB — the DB only records which codes were earned and when. This keeps badge logic testable as pure Python and avoids a badge-definitions migration path.

### XP formula

```
accuracy_multiplier = clamp(0.3 + (accuracy - 50) / 50 * 1.2, 0.3, 1.5)   # 50%acc->0.3, 100%acc->1.5
base_xp             = correct_keys * accuracy_multiplier
threshold_bonus      = 20 if wpm >= LEVEL_WPM_THRESHOLDS[adaptive_level] else 0
combo_bonus          = min(max_combo, 50)   # capped, avoids runaway on long custom texts
xp_gained            = round(base_xp + threshold_bonus + combo_bonus)
```

### Gamer-level curve

```
xp_required_for_level(n) = round(100 * n ** 1.3)   # level 2 needs 100xp total, level 5 needs ~758, etc.
```

`GamificationEngine.level_for_xp(total_xp)` walks the curve to find current level; `xp_progress(total_xp)` returns `(xp_into_current_level, xp_needed_for_next_level)` for progress-bar rendering.

---

## 3. Engine Layer

### `typingapp/engine/gamification.py` (new, pure Python, no Textual dependency)

- `GamificationEngine`:
  - `award_xp(wpm, accuracy, correct_keys, max_combo, adaptive_level) -> int`
  - `level_for_xp(xp: int) -> int`
  - `xp_progress(xp: int) -> tuple[int, int]`
- `BADGES: dict[str, BadgeDef]` — static predicates evaluated after each session, e.g.:
  - `zero_errors` — session had `error_count == 0` and `len(keystrokes) > 0`
  - `wpm_100` — session `wpm >= 100`
  - `streak_7` / `streak_30` — `current_streak_days >= 7 / 30`
  - `first_challenge_pass` — first session with `is_challenge=1` and `accuracy >= 80`
- `StreakTracker.update_streak(last_practice_date: str | None, today: date) -> tuple[int, int]`:
  - same day as last practice → streak unchanged
  - exactly one day after last practice → `current += 1`
  - gap > 1 day (or no prior date) → `current = 1`
  - `longest = max(longest, current)` always returned alongside `current`

`today` is passed in by the caller (screen code), not computed inside — keeps the engine pure/testable without monkeypatching `date.today()`.

### `typingapp/engine/scorer.py`

Add `combo: int` and `max_combo: int` fields (both `init=False`, default 0). `process_key`: increment `combo` on correct, reset to `0` on incorrect; update `max_combo = max(max_combo, combo)` after every keystroke. Purely additive — no existing field or method signature changes.

### `typingapp/engine/lesson.py`

Add `get_challenge_lesson(current_level: int, weak_bigrams: list[str] | None = None, content_type: str = "words") -> tuple[str, int]`:
- Computes `target_level = min(current_level + 1, 10)`.
- Reuses existing `_build_word_lesson` / sentence / code selection at `target_level`, but for words specifically increases `WORD_COUNTS[target_level]` by 1.3× (rounded) so the challenge is a genuine stretch, not just "next level's normal lesson."
- Returns `(text, target_level)` so the caller knows which level is actually being contested (needed since Challenge always targets current+1, never a user-chosen level, per design decision).

### `typingapp/engine/sound.py` (new)

Thin wrapper (`SoundPlayer`) around a real cross-platform audio dependency (added to `pip install` line in commands — see Dependencies below). `play_correct()` / `play_error()` play short, distinct pre-generated tones (correct = short high click; error = short low buzz), reinforcing accuracy audibly during practice. Initialization failures (no audio device, missing backend, headless CI) are caught in `__init__`; a `self._enabled` flag is set `False` and all `play_*` calls become no-ops. Never raises into UI code.

---

## 4. Screens & UI

- **Menu (`menu.py`)**: new "🔥 Challenge" button between Start Lesson and History. Header gains an XP bar + gamer level + streak readout, e.g. `Lv.4 ▓▓▓▓▓▓░░░░ 320/500 XP   🔥 5-day streak`, populated from `storage` gamification row in `on_mount`.
- **`screens/challenge.py`** (new, `ChallengeScreen`): subclasses/reuses the live-typing behavior currently in `LessonScreen` (stats bar compose, `on_key` handling, render, timer tick) via a shared base — see Architecture Note below. Adds an intro state ("Score 80%+ to unlock Level {target}") before typing starts, and a distinct pass/fail outcome view:
  - **Pass** (`accuracy >= 80.0`): "🎉 Challenge Passed — Level {target} unlocked!", immediately sets `app.adaptive.current_level = target` (clamped ≤10) and persists to config; awards XP + `first_challenge_pass` badge check.
  - **Fail**: "Not quite — {accuracy:.1f}%, need 80%. Keep practicing!" with Retry/Menu buttons; no level change.
  - Either outcome writes a `sessions` row with `is_challenge=1` so Challenge attempts appear in History.
- **Lesson (`lesson.py`)**: stats bar gains a live combo counter (`🔥 Combo: N`); `on_key` calls `SoundPlayer.play_correct()/play_error()` when `cfg.key_sounds` is on; time display switches to a countdown when `session_duration` applies (bug fix 1.1).
- **Results (`results.py`)**: mistake-bigram fix (1.2); adds `+{xp} XP` line, any newly earned badges as a short list, and a level-up banner if `gamer_level` increased this session.
- **History (`history.py`)**: adds badges-earned list, current/longest streak, XP progress bar alongside existing WPM chart/heatmap/recommendation.
- **Settings (`settings.py`)**: new "Key sounds" `Switch` bound to `AppConfig.key_sounds: bool = True`.
- **`app.tcss`**: new style classes for XP bar fill, combo meter (color intensifies with combo size, e.g. gray → yellow → orange as it climbs), badge chips, and challenge pass/fail banners — extends the existing dark palette with more saturated accent states rather than replacing it.

**Architecture note — sharing Lesson/Challenge logic:** rather than duplicating the ~150 lines of stats-bar composition, key handling, and render logic, extract the shared live-typing behavior from `LessonScreen` into a small base class (e.g. `TypingSessionScreen`) that both `LessonScreen` and `ChallengeScreen` subclass. Subclasses parameterize: lesson-text source (`_load_lesson_text` override), completion behavior (`_finish` override), and pass/fail framing. This is a refactor of existing `LessonScreen` code as part of this work, not a net-new pattern.

---

## 5. Error Handling

- Sound backend failures never propagate to the UI — `SoundPlayer` disables itself silently on init failure.
- Challenge level-up is clamped to 10 (existing `AdaptiveEngine` clamp semantics preserved); passing at level 10 still records XP/badges, just no level change.
- Streak gaps >1 day reset `current_streak_days` to `1` (today's session counts), not `0`.
- DB schema migration for existing `~/.typingapp/history.db` files: `Storage.__init__` checks `PRAGMA table_info(sessions)` for the three new columns and `ALTER TABLE ADD COLUMN`s any that are missing; `gamification`/`badges` tables use `CREATE TABLE IF NOT EXISTS`. No data loss on upgrade.

---

## 6. Testing

Following the existing per-module `pytest` convention (`tests/test_<module>.py`):

- `tests/test_gamification.py` (new) — XP formula boundary cases (0% correct, 100% accuracy, combo cap), level curve lookups, badge predicates (including negative cases), streak transitions (same-day, consecutive, gap >1, no prior date).
- `tests/test_scorer.py` — extend: combo increments on correct, resets on error, `max_combo` tracks the peak across a mixed sequence.
- `tests/test_lesson.py` — extend: `get_challenge_lesson` returns `target_level = current + 1` (clamped at 10), word count is measurably longer than the equivalent normal lesson at that level.
- `tests/test_storage.py` — extend: gamification row auto-created on init, badge insert/fetch, `ALTER TABLE` migration path against a pre-existing DB fixture missing the new columns.
- `tests/test_recommender.py` — add a case where a single outlier session (e.g. one bad WPM in the middle of an otherwise flat run) does *not* incorrectly suppress/trigger the plateau message under the old endpoints-only logic.
- `SoundPlayer` — tested only for "never raises, `play_*` no-ops when backend init fails" (no audio hardware in CI, so no tone-correctness testing).

---

## 7. Dependencies

New third-party dependency for cross-platform audio (decision: prioritize consistent behavior across Windows/Mac/Linux over the prior "stdlib + textual only" constraint). Exact package to be finalized during implementation (candidates: `simpleaudio`, `playsound`) based on packaging/wheel availability on Windows. `CLAUDE.md` commands section will be updated to include it in the install line.

---

## 8. Out of Scope

- User-selectable Challenge target level (always current+1, per design decision).
- Multiplayer/leaderboard features.
- Custom/importable sound packs — one built-in correct/error tone pair only.
- Badge editing/configuration UI — badge set is fixed in code for this iteration.
