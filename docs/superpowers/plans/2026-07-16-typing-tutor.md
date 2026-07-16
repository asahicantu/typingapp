# Typing Tutor CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI typing tutor with adaptive difficulty, real-time stats, SQLite history, and a vibrant Textual TUI.

**Architecture:** Textual App with 5 screens (Menu, Lesson, Results, History, Settings) backed by a pure-Python engine (scorer, adaptive difficulty, recommender) and SQLite via stdlib. Config lives in `~/.typingapp/config.json`, history in `~/.typingapp/history.db`.

**Tech Stack:** Python 3.10+, Textual, Rich (bundled with Textual), sqlite3 (stdlib), json (stdlib)

---

## File Map

| File | Responsibility |
|------|---------------|
| `typingapp/__main__.py` | Entry point — instantiates and runs the App |
| `typingapp/app.py` | Textual App root; installs screens, global CSS |
| `typingapp/config.py` | Load/save `~/.typingapp/config.json`; dataclass for settings |
| `typingapp/data/storage.py` | SQLite init, insert session, insert keystrokes, query helpers |
| `typingapp/engine/scorer.py` | Real-time WPM, accuracy, per-keystroke tracking |
| `typingapp/engine/adaptive.py` | Level-up/down logic; adaptive hint detection |
| `typingapp/engine/lesson.py` | Pick lesson text by content type + difficulty |
| `typingapp/engine/recommender.py` | Rules-based recommendations from DB stats |
| `typingapp/engine/content/words.txt` | Top 1000 common English words (one per line) |
| `typingapp/engine/content/sentences.txt` | Prose passages (one per line) |
| `typingapp/engine/content/code_snippets.py` | List of code snippet strings |
| `typingapp/screens/menu.py` | Main menu screen |
| `typingapp/screens/lesson.py` | Active typing session screen |
| `typingapp/screens/custom_text.py` | TextArea screen for custom content entry |
| `typingapp/screens/results.py` | Post-session results screen |
| `typingapp/screens/history.py` | Progress dashboard (chart, heatmap, recommendations) |
| `typingapp/screens/settings.py` | Settings toggles screen |
| `tests/test_scorer.py` | Unit tests for scorer |
| `tests/test_adaptive.py` | Unit tests for adaptive engine |
| `tests/test_storage.py` | Unit tests for DB storage |
| `tests/test_lesson.py` | Unit tests for lesson text selection |
| `tests/test_recommender.py` | Unit tests for recommender |
| `pyproject.toml` | Package metadata and dependencies |
| `.gitignore` | Ignore `__pycache__`, `.superpowers/`, `*.db` |

---

## Task 1: Project Scaffold & pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `typingapp/__init__.py`
- Create: `typingapp/__main__.py`
- Create: `typingapp/screens/__init__.py`
- Create: `typingapp/engine/__init__.py`
- Create: `typingapp/engine/content/__init__.py`
- Create: `typingapp/data/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "typingapp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["textual>=0.80.0"]

[project.scripts]
typingtutor = "typingapp.__main__:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["typingapp*"]

[tool.setuptools.package-data]
"typingapp.engine.content" = ["*.txt"]
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
*.db
.superpowers/
dist/
*.egg-info/
.venv/
```

- [ ] **Step 3: Create all `__init__.py` files (all empty)**

```bash
mkdir -p typingapp/screens typingapp/engine/content typingapp/data tests
touch typingapp/__init__.py typingapp/screens/__init__.py typingapp/engine/__init__.py typingapp/engine/content/__init__.py typingapp/data/__init__.py tests/__init__.py
```

- [ ] **Step 4: Create `typingapp/__main__.py`**

```python
from typingapp.app import TypingApp


def main():
    app = TypingApp()
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Install dependencies**

```bash
pip install textual pytest
```

- [ ] **Step 6: Commit**

```bash
git init
git add pyproject.toml .gitignore typingapp/ tests/
git commit -m "feat: project scaffold"
```

---

## Task 2: Config

**Files:**
- Create: `typingapp/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import json
import pytest
from pathlib import Path
from typingapp.config import AppConfig, load_config, save_config


def test_default_config():
    cfg = AppConfig()
    assert cfg.strict_mode is False
    assert cfg.content_type == "words"
    assert cfg.session_duration == 60
    assert cfg.difficulty == 0          # 0 = Auto
    assert cfg.show_live_wpm is True
    assert cfg.show_hints is True


def test_save_and_load_roundtrip(tmp_path):
    cfg = AppConfig(strict_mode=True, session_duration=30)
    path = tmp_path / "config.json"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.strict_mode is True
    assert loaded.session_duration == 30


def test_load_missing_file_returns_defaults(tmp_path):
    path = tmp_path / "nonexistent.json"
    cfg = load_config(path)
    assert cfg == AppConfig()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_config.py -v
```
Expected: ImportError — `typingapp.config` not found.

- [ ] **Step 3: Implement `typingapp/config.py`**

```python
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".typingapp" / "config.json"


@dataclass
class AppConfig:
    strict_mode: bool = False
    content_type: str = "words"          # words | sentences | code | custom
    session_duration: int = 60           # seconds
    difficulty: int = 0                  # 0 = Auto, 1-10 explicit
    show_live_wpm: bool = True
    show_hints: bool = True


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()
    with path.open() as f:
        data = json.load(f)
    return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})


def save_config(cfg: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(asdict(cfg), f, indent=2)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_config.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add typingapp/config.py tests/test_config.py
git commit -m "feat: config load/save with AppConfig dataclass"
```

---

## Task 3: Database Storage

**Files:**
- Create: `typingapp/data/storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage.py
import pytest
from typingapp.data.storage import Storage, SessionRecord, KeystrokeRecord


def test_init_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    s = Storage(db_path)
    # Should not raise
    s.close()


def test_insert_and_fetch_session(tmp_path):
    s = Storage(tmp_path / "test.db")
    rec = SessionRecord(
        timestamp="2026-07-16T10:00:00",
        content_type="words",
        difficulty=3,
        duration_seconds=60,
        wpm=65.5,
        accuracy=94.2,
        error_count=5,
        strict_mode=False,
    )
    session_id = s.insert_session(rec)
    assert session_id > 0
    sessions = s.fetch_recent_sessions(limit=10)
    assert len(sessions) == 1
    assert sessions[0]["wpm"] == 65.5
    s.close()


def test_insert_keystrokes(tmp_path):
    s = Storage(tmp_path / "test.db")
    rec = SessionRecord(
        timestamp="2026-07-16T10:00:00",
        content_type="words",
        difficulty=1,
        duration_seconds=30,
        wpm=50.0,
        accuracy=90.0,
        error_count=3,
        strict_mode=True,
    )
    sid = s.insert_session(rec)
    keystrokes = [
        KeystrokeRecord(expected="t", actual="t", correct=True, bigram="th", timestamp_ms=1000),
        KeystrokeRecord(expected="h", actual="j", correct=False, bigram="th", timestamp_ms=1050),
    ]
    s.insert_keystrokes(sid, keystrokes)
    heatmap = s.fetch_bigram_heatmap(limit=10)
    assert heatmap[0]["bigram"] == "th"
    assert heatmap[0]["errors"] == 1
    s.close()


def test_fetch_recent_sessions_limit(tmp_path):
    s = Storage(tmp_path / "test.db")
    for i in range(5):
        s.insert_session(SessionRecord(
            timestamp=f"2026-07-{i+1:02d}T10:00:00",
            content_type="words", difficulty=1,
            duration_seconds=60, wpm=float(50+i),
            accuracy=90.0, error_count=0, strict_mode=False,
        ))
    sessions = s.fetch_recent_sessions(limit=3)
    assert len(sessions) == 3
    s.close()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_storage.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `typingapp/data/storage.py`**

```python
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path.home() / ".typingapp" / "history.db"

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    content_type TEXT NOT NULL,
    difficulty INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL,
    wpm REAL NOT NULL,
    accuracy REAL NOT NULL,
    error_count INTEGER NOT NULL,
    strict_mode INTEGER NOT NULL
)"""

CREATE_KEYSTROKES = """
CREATE TABLE IF NOT EXISTS keystrokes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    expected TEXT NOT NULL,
    actual TEXT NOT NULL,
    correct INTEGER NOT NULL,
    bigram TEXT,
    timestamp_ms INTEGER NOT NULL
)"""


@dataclass
class SessionRecord:
    timestamp: str
    content_type: str
    difficulty: int
    duration_seconds: int
    wpm: float
    accuracy: float
    error_count: int
    strict_mode: bool


@dataclass
class KeystrokeRecord:
    expected: str
    actual: str
    correct: bool
    bigram: str | None
    timestamp_ms: int


class Storage:
    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute(CREATE_SESSIONS)
        self._conn.execute(CREATE_KEYSTROKES)
        self._conn.commit()

    def insert_session(self, rec: SessionRecord) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (timestamp, content_type, difficulty, duration_seconds, "
            "wpm, accuracy, error_count, strict_mode) VALUES (?,?,?,?,?,?,?,?)",
            (rec.timestamp, rec.content_type, rec.difficulty, rec.duration_seconds,
             rec.wpm, rec.accuracy, rec.error_count, int(rec.strict_mode)),
        )
        self._conn.commit()
        return cur.lastrowid

    def insert_keystrokes(self, session_id: int, records: list[KeystrokeRecord]) -> None:
        self._conn.executemany(
            "INSERT INTO keystrokes (session_id, expected, actual, correct, bigram, timestamp_ms) "
            "VALUES (?,?,?,?,?,?)",
            [(session_id, r.expected, r.actual, int(r.correct), r.bigram, r.timestamp_ms)
             for r in records],
        )
        self._conn.commit()

    def fetch_recent_sessions(self, limit: int = 14) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def fetch_bigram_heatmap(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT bigram, COUNT(*) as errors FROM keystrokes "
            "WHERE correct=0 AND bigram IS NOT NULL "
            "GROUP BY bigram ORDER BY errors DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def fetch_last_n_wpm(self, n: int = 30) -> list[float]:
        rows = self._conn.execute(
            "SELECT wpm FROM sessions ORDER BY timestamp DESC LIMIT ?", (n,)
        ).fetchall()
        return [r["wpm"] for r in reversed(rows)]

    def fetch_summary(self) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT MAX(wpm) as best_wpm, AVG(accuracy) as avg_accuracy, COUNT(*) as total "
            "FROM sessions"
        ).fetchone()
        return dict(row) if row else {"best_wpm": 0, "avg_accuracy": 0, "total": 0}

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_storage.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add typingapp/data/storage.py tests/test_storage.py
git commit -m "feat: SQLite storage with sessions and keystrokes tables"
```

---

## Task 4: Scorer

**Files:**
- Create: `typingapp/engine/scorer.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scorer.py
import time
import pytest
from typingapp.engine.scorer import Scorer


def test_initial_state():
    s = Scorer("hello")
    assert s.wpm == 0.0
    assert s.accuracy == 100.0
    assert s.error_count == 0
    assert s.position == 0
    assert not s.is_complete


def test_correct_keystroke_advances():
    s = Scorer("hi")
    s.start()
    result = s.process_key("h")
    assert result is True
    assert s.position == 1


def test_incorrect_keystroke_strict_mode_blocks():
    s = Scorer("hi", strict_mode=True)
    s.start()
    result = s.process_key("x")
    assert result is False
    assert s.position == 0          # did not advance
    assert s.error_count == 1


def test_incorrect_keystroke_lenient_mode_advances():
    s = Scorer("hi", strict_mode=False)
    s.start()
    result = s.process_key("x")
    assert result is False
    assert s.position == 1          # advanced despite error
    assert s.error_count == 1


def test_completion():
    s = Scorer("ab")
    s.start()
    s.process_key("a")
    s.process_key("b")
    assert s.is_complete


def test_accuracy_calculation():
    s = Scorer("abc", strict_mode=False)
    s.start()
    s.process_key("a")   # correct
    s.process_key("x")   # wrong
    s.process_key("c")   # correct
    assert s.accuracy == pytest.approx(66.67, abs=0.1)


def test_bigram_tracking():
    s = Scorer("abc", strict_mode=False)
    s.start()
    s.process_key("a")
    s.process_key("x")  # wrong, bigram="ab"
    assert s.keystrokes[-1].bigram == "ab"


def test_wpm_nonzero_after_typing(monkeypatch):
    s = Scorer("the quick")
    # Fake elapsed time of 0.5 minutes = 30 seconds
    s.start()
    s._start_time -= 30  # rewind start by 30s
    for ch in "the quick":
        s.process_key(ch)
    # 9 chars / 5 = 1.8 words; 1.8 / 0.5 min = 3.6 WPM (rough lower bound)
    assert s.wpm > 0
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_scorer.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `typingapp/engine/scorer.py`**

```python
from __future__ import annotations
import time
from dataclasses import dataclass, field

from typingapp.data.storage import KeystrokeRecord


@dataclass
class Scorer:
    target: str
    strict_mode: bool = False
    position: int = field(default=0, init=False)
    error_count: int = field(default=0, init=False)
    keystrokes: list[KeystrokeRecord] = field(default_factory=list, init=False)
    _start_time: float = field(default=0.0, init=False)
    _total_keys: int = field(default=0, init=False)
    _correct_keys: int = field(default=0, init=False)

    def start(self) -> None:
        self._start_time = time.monotonic()

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time == 0:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def wpm(self) -> float:
        elapsed_min = self.elapsed_seconds / 60
        if elapsed_min == 0:
            return 0.0
        return (self._correct_keys / 5) / elapsed_min

    @property
    def accuracy(self) -> float:
        if self._total_keys == 0:
            return 100.0
        return (self._correct_keys / self._total_keys) * 100

    @property
    def is_complete(self) -> bool:
        return self.position >= len(self.target)

    def process_key(self, char: str) -> bool:
        expected = self.target[self.position]
        correct = char == expected
        bigram = self.target[self.position - 1 : self.position + 1] if self.position > 0 else None
        self.keystrokes.append(KeystrokeRecord(
            expected=expected,
            actual=char,
            correct=correct,
            bigram=bigram,
            timestamp_ms=int(time.monotonic() * 1000),
        ))
        self._total_keys += 1
        if correct:
            self._correct_keys += 1
            self.position += 1
        else:
            self.error_count += 1
            if not self.strict_mode:
                self.position += 1
        return correct
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_scorer.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/scorer.py tests/test_scorer.py
git commit -m "feat: real-time scorer with strict/lenient mode and bigram tracking"
```

---

## Task 5: Content Files

**Files:**
- Create: `typingapp/engine/content/words.txt`
- Create: `typingapp/engine/content/sentences.txt`
- Create: `typingapp/engine/content/code_snippets.py`

- [ ] **Step 1: Create `words.txt`** (top 100 common words — one per line)

```
the
be
to
of
and
a
in
that
have
it
for
not
on
with
he
as
you
do
at
this
but
his
by
from
they
we
say
her
she
or
an
will
my
one
all
would
there
their
what
so
up
out
if
about
who
get
which
go
me
when
make
can
like
time
no
just
him
know
take
people
into
year
your
good
some
could
them
see
other
than
then
now
look
only
come
its
over
think
also
back
after
use
two
how
our
work
first
well
way
even
new
want
because
any
these
give
day
most
us
```

- [ ] **Step 2: Create `sentences.txt`** (one prose sentence per line)

```
The quick brown fox jumps over the lazy dog.
Pack my box with five dozen liquor jugs.
How vexingly quick daft zebras jump.
The five boxing wizards jump quickly.
Sphinx of black quartz, judge my vow.
A fast runner leaps across the wide open field.
Practice makes perfect when you commit to daily repetition.
Strong fingers move swiftly across each familiar key.
Consistency is the secret ingredient behind every skilled typist.
Every keystroke brings you one step closer to mastery.
The sun sets slowly over the quiet mountain town.
She opened the letter and read each word carefully.
He typed the message without looking at the keyboard once.
The forest path wound gently between the ancient oak trees.
Learning to type well is a skill that lasts a lifetime.
```

- [ ] **Step 3: Create `typingapp/engine/content/code_snippets.py`**

```python
SNIPPETS: list[str] = [
    "def greet(name):\n    return f'Hello, {name}!'",
    "for i in range(10):\n    print(i * i)",
    "x = [n for n in range(100) if n % 2 == 0]",
    "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n - 1)",
    "with open('file.txt', 'r') as f:\n    data = f.read()",
    "import json\ndata = json.loads(response.text)",
    "try:\n    result = 10 / 0\nexcept ZeroDivisionError:\n    result = None",
    "class Node:\n    def __init__(self, val):\n        self.val = val\n        self.next = None",
    "nums = [3, 1, 4, 1, 5, 9]\nnums.sort()\nprint(nums)",
    "d = {'a': 1, 'b': 2}\nfor key, val in d.items():\n    print(key, val)",
]
```

- [ ] **Step 4: Commit**

```bash
git add typingapp/engine/content/
git commit -m "feat: add content files (words, sentences, code snippets)"
```

---

## Task 6: Lesson Engine

**Files:**
- Create: `typingapp/engine/lesson.py`
- Create: `tests/test_lesson.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lesson.py
import pytest
from typingapp.engine.lesson import LessonEngine


def test_words_lesson_returns_string():
    eng = LessonEngine()
    text = eng.get_lesson("words", difficulty=1)
    assert isinstance(text, str)
    assert len(text) > 0


def test_sentences_lesson_returns_string():
    eng = LessonEngine()
    text = eng.get_lesson("sentences", difficulty=1)
    assert isinstance(text, str)
    assert text.endswith(".")


def test_code_lesson_returns_string():
    eng = LessonEngine()
    text = eng.get_lesson("code", difficulty=1)
    assert isinstance(text, str)


def test_custom_lesson_returns_input():
    eng = LessonEngine()
    text = eng.get_lesson("custom", difficulty=1, custom_text="Type this exact text.")
    assert text == "Type this exact text."


def test_difficulty_controls_word_count():
    eng = LessonEngine()
    text_easy = eng.get_lesson("words", difficulty=1)
    text_hard = eng.get_lesson("words", difficulty=8)
    assert len(text_hard) > len(text_easy)


def test_weak_bigrams_bias_word_selection():
    eng = LessonEngine()
    text = eng.get_lesson("words", difficulty=1, weak_bigrams=["th"])
    # "the", "that", "this", "with", "other" all contain "th"
    assert any(bg in text for bg in ["th"])
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_lesson.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `typingapp/engine/lesson.py`**

```python
from __future__ import annotations
import random
from importlib import resources
from typingapp.engine.content.code_snippets import SNIPPETS

# words per difficulty level (1-10)
WORD_COUNTS = {1: 10, 2: 15, 3: 20, 4: 25, 5: 30, 6: 40, 7: 50, 8: 60, 9: 80, 10: 100}


def _load_words() -> list[str]:
    pkg = resources.files("typingapp.engine.content")
    return (pkg / "words.txt").read_text(encoding="utf-8").splitlines()


def _load_sentences() -> list[str]:
    pkg = resources.files("typingapp.engine.content")
    return (pkg / "sentences.txt").read_text(encoding="utf-8").splitlines()


class LessonEngine:
    def __init__(self) -> None:
        self._words = _load_words()
        self._sentences = _load_sentences()

    def get_lesson(
        self,
        content_type: str,
        difficulty: int,
        custom_text: str = "",
        weak_bigrams: list[str] | None = None,
    ) -> str:
        if content_type == "custom":
            return custom_text
        if content_type == "sentences":
            return random.choice(self._sentences)
        if content_type == "code":
            return random.choice(SNIPPETS)
        # default: words
        return self._build_word_lesson(difficulty, weak_bigrams or [])

    def _build_word_lesson(self, difficulty: int, weak_bigrams: list[str]) -> str:
        count = WORD_COUNTS.get(max(1, min(difficulty, 10)), 20)
        pool = self._words
        if weak_bigrams:
            biased = [w for w in pool if any(bg in w for bg in weak_bigrams)]
            if biased:
                # 50% biased words, 50% random
                n_biased = count // 2
                chosen = random.choices(biased, k=n_biased) + random.choices(pool, k=count - n_biased)
                random.shuffle(chosen)
                return " ".join(chosen)
        return " ".join(random.choices(pool, k=count))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_lesson.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/lesson.py tests/test_lesson.py
git commit -m "feat: lesson engine with word/sentence/code/custom content types"
```

---

## Task 7: Adaptive Engine

**Files:**
- Create: `typingapp/engine/adaptive.py`
- Create: `tests/test_adaptive.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_adaptive.py
import pytest
from typingapp.engine.adaptive import AdaptiveEngine


def test_level_up_on_high_performance():
    eng = AdaptiveEngine(current_level=3)
    new_level = eng.update_level(wpm=80, accuracy=96.0)
    assert new_level == 4


def test_level_down_on_low_accuracy():
    eng = AdaptiveEngine(current_level=5)
    new_level = eng.update_level(wpm=40, accuracy=75.0)
    assert new_level == 4


def test_level_stays_on_middle_performance():
    eng = AdaptiveEngine(current_level=3)
    new_level = eng.update_level(wpm=50, accuracy=88.0)
    assert new_level == 3


def test_level_clamps_at_minimum():
    eng = AdaptiveEngine(current_level=1)
    new_level = eng.update_level(wpm=10, accuracy=60.0)
    assert new_level == 1


def test_level_clamps_at_maximum():
    eng = AdaptiveEngine(current_level=10)
    new_level = eng.update_level(wpm=200, accuracy=99.0)
    assert new_level == 10


def test_detect_weak_bigrams():
    from typingapp.data.storage import KeystrokeRecord
    eng = AdaptiveEngine(current_level=3)
    keystrokes = (
        [KeystrokeRecord(expected="t", actual="x", correct=False, bigram="th", timestamp_ms=i)
         for i in range(5)]
        + [KeystrokeRecord(expected="h", actual="h", correct=True, bigram="th", timestamp_ms=i+100)
           for i in range(30)]
    )
    weak = eng.detect_weak_bigrams(keystrokes, threshold=0.15)
    assert "th" in weak


def test_no_weak_bigrams_when_accurate():
    from typingapp.data.storage import KeystrokeRecord
    eng = AdaptiveEngine(current_level=3)
    keystrokes = [
        KeystrokeRecord(expected="t", actual="t", correct=True, bigram="th", timestamp_ms=i)
        for i in range(20)
    ]
    weak = eng.detect_weak_bigrams(keystrokes, threshold=0.15)
    assert "th" not in weak
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_adaptive.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `typingapp/engine/adaptive.py`**

```python
from __future__ import annotations
from collections import defaultdict
from typingapp.data.storage import KeystrokeRecord

# WPM threshold to level up at each level
LEVEL_WPM_THRESHOLDS = {
    1: 20, 2: 30, 3: 40, 4: 50, 5: 60,
    6: 70, 7: 80, 8: 90, 9: 100, 10: 120,
}


class AdaptiveEngine:
    def __init__(self, current_level: int = 1) -> None:
        self.current_level = max(1, min(current_level, 10))

    def update_level(self, wpm: float, accuracy: float) -> int:
        threshold = LEVEL_WPM_THRESHOLDS.get(self.current_level, 60)
        if wpm >= threshold and accuracy >= 95.0 and self.current_level < 10:
            self.current_level += 1
        elif accuracy < 80.0 and self.current_level > 1:
            self.current_level -= 1
        return self.current_level

    def detect_weak_bigrams(
        self, keystrokes: list[KeystrokeRecord], threshold: float = 0.15
    ) -> list[str]:
        bigram_total: dict[str, int] = defaultdict(int)
        bigram_errors: dict[str, int] = defaultdict(int)
        for ks in keystrokes:
            if ks.bigram:
                bigram_total[ks.bigram] += 1
                if not ks.correct:
                    bigram_errors[ks.bigram] += 1
        return [
            bg for bg, total in bigram_total.items()
            if total > 0 and bigram_errors[bg] / total >= threshold
        ]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_adaptive.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/adaptive.py tests/test_adaptive.py
git commit -m "feat: adaptive difficulty engine with level up/down and weak bigram detection"
```

---

## Task 8: Recommender

**Files:**
- Create: `typingapp/engine/recommender.py`
- Create: `tests/test_recommender.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_recommender.py
import pytest
from typingapp.engine.recommender import Recommender


def _session(wpm=70.0, accuracy=92.0, content_type="words"):
    return {"wpm": wpm, "accuracy": accuracy, "content_type": content_type}


def test_plateau_recommendation():
    rec = Recommender()
    sessions = [_session(wpm=70 + i * 0.1) for i in range(8)]  # < 5% improvement
    result = rec.recommend(sessions, bigrams=["th"])
    assert "th" in result.lower() or "bigram" in result.lower() or "drill" in result.lower()


def test_low_accuracy_recommends_strict_mode():
    rec = Recommender()
    sessions = [_session(accuracy=75.0) for _ in range(5)]
    result = rec.recommend(sessions, bigrams=[])
    assert "strict" in result.lower()


def test_content_gap_recommends_practice():
    rec = Recommender()
    sessions = [_session(wpm=80, content_type="words") for _ in range(4)] + \
               [_session(wpm=40, content_type="code") for _ in range(3)]
    result = rec.recommend(sessions, bigrams=[])
    assert "code" in result.lower()


def test_positive_reinforcement_on_streak():
    rec = Recommender()
    sessions = [_session(wpm=60 + i * 3, accuracy=95.0) for i in range(5)]
    result = rec.recommend(sessions, bigrams=[])
    assert len(result) > 0   # some message returned


def test_no_sessions_returns_start_message():
    rec = Recommender()
    result = rec.recommend([], bigrams=[])
    assert len(result) > 0
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_recommender.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `typingapp/engine/recommender.py`**

```python
from __future__ import annotations
from collections import Counter


class Recommender:
    def recommend(self, sessions: list[dict], bigrams: list[str]) -> str:
        if not sessions:
            return "No sessions yet — start your first lesson to begin tracking progress!"

        avg_accuracy = sum(s["accuracy"] for s in sessions) / len(sessions)
        wpms = [s["wpm"] for s in sessions]

        if avg_accuracy < 90.0:
            return (
                f"Your average accuracy is {avg_accuracy:.1f}% — below 90%. "
                "Try enabling Strict Mode to force yourself to fix every error before continuing."
            )

        # Check for WPM plateau (last 7+ sessions, < 5% improvement)
        if len(wpms) >= 7:
            oldest, newest = wpms[0], wpms[-1]
            if oldest > 0 and (newest - oldest) / oldest < 0.05:
                if bigrams:
                    bg_list = ", ".join(f"'{b}'" for b in bigrams[:3])
                    return (
                        f"Your WPM has plateaued. You're making frequent errors on {bg_list}. "
                        "Try a focused words session — these bigrams will appear more often."
                    )
                return (
                    "Your WPM has plateaued. Mix in code or sentence sessions "
                    "to challenge different finger patterns."
                )

        # Check for content-type gap
        by_type: dict[str, list[float]] = {}
        for s in sessions:
            by_type.setdefault(s["content_type"], []).append(s["wpm"])
        if len(by_type) > 1:
            avg_by_type = {t: sum(v) / len(v) for t, v in by_type.items()}
            slowest = min(avg_by_type, key=avg_by_type.get)
            fastest = max(avg_by_type, key=avg_by_type.get)
            if avg_by_type[fastest] - avg_by_type[slowest] > 15:
                return (
                    f"You're significantly slower on '{slowest}' content "
                    f"({avg_by_type[slowest]:.0f} WPM vs {avg_by_type[fastest]:.0f} WPM on '{fastest}'). "
                    f"More '{slowest}' practice will close the gap."
                )

        # Positive reinforcement
        latest_wpm = wpms[-1]
        return f"Great work! You hit {latest_wpm:.0f} WPM last session. Keep the streak going!"
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_recommender.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/recommender.py tests/test_recommender.py
git commit -m "feat: rules-based recommender engine"
```

---

## Task 9: Textual App Root & Global CSS

**Files:**
- Create: `typingapp/app.py`
- Create: `typingapp/app.tcss`

- [ ] **Step 1: Create `typingapp/app.tcss`**

```css
/* app.tcss — global Textual styles */
Screen {
    background: #0d0d0d;
}

.stat-label {
    color: #888888;
}

.stat-value {
    color: #ffffff;
    text-style: bold;
}

.wpm-value { color: #f9c74f; }
.acc-value { color: #90be6d; }
.time-value { color: #43b0f1; }
.err-value { color: #c77dff; }

.hint-bar {
    background: #1a1a2e;
    border: tall #2a2a4e;
    color: #43b0f1;
    padding: 0 1;
}

.correct { color: #90be6d; }
.error   { background: #ff6b6b; color: #ffffff; }
.pending { color: #555555; }

.menu-title {
    color: #f9c74f;
    text-style: bold;
}
```

- [ ] **Step 2: Create `typingapp/app.py`**

```python
from __future__ import annotations
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from typingapp.config import load_config, AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine


class TypingApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "Typing Tutor"

    def __init__(self) -> None:
        super().__init__()
        self.config: AppConfig = load_config()
        self.storage: Storage = Storage()
        self.lesson_engine: LessonEngine = LessonEngine()
        self.adaptive: AdaptiveEngine = AdaptiveEngine(
            current_level=self.config.difficulty if self.config.difficulty > 0 else 1
        )

    def on_mount(self) -> None:
        from typingapp.screens.menu import MenuScreen
        self.push_screen(MenuScreen())

    def on_unmount(self) -> None:
        self.storage.close()
```

- [ ] **Step 3: Smoke test — app opens without crashing**

```bash
python -m typingapp
```
Expected: Terminal clears, Textual app launches. Press Ctrl+Q or Ctrl+C to quit (MenuScreen will be a placeholder at this point).

- [ ] **Step 4: Commit**

```bash
git add typingapp/app.py typingapp/app.tcss
git commit -m "feat: Textual App root with config, storage, and engine wiring"
```

---

## Task 10: Menu Screen

**Files:**
- Create: `typingapp/screens/menu.py`

- [ ] **Step 1: Create `typingapp/screens/menu.py`**

```python
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import Center, Middle, Vertical


class MenuScreen(Screen):
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="menu-box"):
                    yield Static("⌨  TYPING TUTOR", classes="menu-title")
                    yield Static("", classes="spacer")
                    yield Button("▶  Start Lesson", id="btn-start", variant="primary")
                    yield Button("📊  History & Progress", id="btn-history")
                    yield Button("⚙  Settings", id="btn-settings")
                    yield Button("✕  Quit", id="btn-quit", variant="error")
                    yield Static("", classes="spacer")
                    yield Label("", id="last-session-label", classes="stat-label")

    def on_mount(self) -> None:
        storage = self.app.storage          # type: ignore[attr-defined]
        sessions = storage.fetch_recent_sessions(limit=1)
        if sessions:
            s = sessions[0]
            self.query_one("#last-session-label", Label).update(
                f"Last session: {s['wpm']:.0f} WPM · {s['accuracy']:.1f}% accuracy"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            from typingapp.screens.lesson import LessonScreen
            self.app.push_screen(LessonScreen())
        elif event.button.id == "btn-history":
            from typingapp.screens.history import HistoryScreen
            self.app.push_screen(HistoryScreen())
        elif event.button.id == "btn-settings":
            from typingapp.screens.settings import SettingsScreen
            self.app.push_screen(SettingsScreen())
        elif event.button.id == "btn-quit":
            self.app.exit()

    def action_quit(self) -> None:
        self.app.exit()
```

- [ ] **Step 2: Run the app and verify menu appears**

```bash
python -m typingapp
```
Expected: Menu with four buttons visible. Arrow keys or mouse selects buttons.

- [ ] **Step 3: Commit**

```bash
git add typingapp/screens/menu.py
git commit -m "feat: main menu screen with navigation"
```

---

## Task 11: Settings Screen

**Files:**
- Create: `typingapp/screens/settings.py`

- [ ] **Step 1: Create `typingapp/screens/settings.py`**

```python
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Switch, Select, Label
from textual.containers import Vertical, Horizontal, ScrollableContainer
from typingapp.config import save_config


class SettingsScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        cfg = self.app.config       # type: ignore[attr-defined]
        with ScrollableContainer():
            yield Static("⚙  Settings", classes="menu-title")
            yield Static("")

            yield Static("TYPING BEHAVIOR", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Strict mode (block on error)")
                yield Switch(value=cfg.strict_mode, id="sw-strict")
            yield Static("When ON: you must fix each error before continuing.", classes="stat-label")
            yield Static("")

            yield Static("LESSON DEFAULTS", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Content type")
                yield Select(
                    options=[("Words", "words"), ("Sentences", "sentences"),
                             ("Code", "code"), ("Custom", "custom")],
                    value=cfg.content_type,
                    id="sel-content",
                )
            with Horizontal(classes="setting-row"):
                yield Label("Session duration (seconds)")
                yield Select(
                    options=[("30s", 30), ("60s", 60), ("120s", 120)],
                    value=cfg.session_duration,
                    id="sel-duration",
                )
            yield Static("")

            yield Static("DISPLAY", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Show live WPM")
                yield Switch(value=cfg.show_live_wpm, id="sw-wpm")
            with Horizontal(classes="setting-row"):
                yield Label("Show adaptive hints")
                yield Switch(value=cfg.show_hints, id="sw-hints")
            yield Static("")

            yield Button("💾  Save & Back", id="btn-save", variant="primary")
            yield Button("✕  Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            cfg = self.app.config       # type: ignore[attr-defined]
            cfg.strict_mode = self.query_one("#sw-strict", Switch).value
            cfg.show_live_wpm = self.query_one("#sw-wpm", Switch).value
            cfg.show_hints = self.query_one("#sw-hints", Switch).value
            sel_content = self.query_one("#sel-content", Select)
            if sel_content.value != Select.BLANK:
                cfg.content_type = sel_content.value
            sel_dur = self.query_one("#sel-duration", Select)
            if sel_dur.value != Select.BLANK:
                cfg.session_duration = sel_dur.value
            save_config(cfg)
            self.app.pop_screen()
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

- [ ] **Step 2: Run and navigate to Settings**

```bash
python -m typingapp
```
Expected: Press "Settings" button from menu. Toggle strict mode, save. Verify settings persist on restart.

- [ ] **Step 3: Commit**

```bash
git add typingapp/screens/settings.py
git commit -m "feat: settings screen with strict mode toggle and lesson defaults"
```

---

## Task 12: Custom Text Screen

**Files:**
- Create: `typingapp/screens/custom_text.py`

- [ ] **Step 1: Create `typingapp/screens/custom_text.py`**

```python
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, TextArea, Label
from textual.containers import Vertical


class CustomTextScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, on_confirm) -> None:
        super().__init__()
        self._on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📝  Enter Custom Text", classes="menu-title")
            yield Label("Paste or type the text you want to practice:", classes="stat-label")
            yield TextArea(id="custom-input")
            yield Label("", id="error-label", classes="err-value")
            yield Button("▶  Start Lesson", id="btn-confirm", variant="primary")
            yield Button("✕  Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            text = self.query_one("#custom-input", TextArea).text.strip()
            if not text:
                self.query_one("#error-label", Label).update("Please enter some text first.")
                return
            self._on_confirm(text)
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

- [ ] **Step 2: Commit**

```bash
git add typingapp/screens/custom_text.py
git commit -m "feat: custom text entry screen"
```

---

## Task 13: Lesson Screen

**Files:**
- Create: `typingapp/screens/lesson.py`

- [ ] **Step 1: Create `typingapp/screens/lesson.py`**

```python
from __future__ import annotations
import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, ProgressBar
from textual.containers import Vertical, Horizontal
from textual import work
from textual.timer import Timer

from typingapp.engine.scorer import Scorer
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.data.storage import SessionRecord


class LessonScreen(Screen):
    BINDINGS = [
        ("escape", "pause", "Pause"),
        ("ctrl+r", "restart", "Restart"),
        ("ctrl+q", "quit_lesson", "Quit"),
    ]

    def __init__(self, custom_text: str = "") -> None:
        super().__init__()
        self._custom_text = custom_text
        self._scorer: Scorer | None = None
        self._timer: Timer | None = None
        self._paused = False

    def _load_lesson_text(self) -> str:
        app = self.app      # type: ignore[attr-defined]
        cfg = app.config
        adaptive: AdaptiveEngine = app.adaptive
        storage = app.storage
        bigrams = storage.fetch_bigram_heatmap(limit=5)
        weak = [b["bigram"] for b in bigrams]
        return app.lesson_engine.get_lesson(
            content_type=cfg.content_type,
            difficulty=adaptive.current_level,
            custom_text=self._custom_text,
            weak_bigrams=weak,
        )

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
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            yield Static("", id="text-display")
            yield Label("", id="hint-bar", classes="hint-bar")
            yield Static("ESC pause  ·  Ctrl+R restart  ·  Ctrl+Q quit", classes="stat-label")

    def on_mount(self) -> None:
        self._start_lesson()

    def _start_lesson(self) -> None:
        app = self.app      # type: ignore[attr-defined]
        text = self._load_lesson_text()
        self._scorer = Scorer(text, strict_mode=app.config.strict_mode)
        self._scorer.start()
        self._render_text()
        self._timer = self.set_interval(0.25, self._tick)

    def _tick(self) -> None:
        if self._paused or self._scorer is None:
            return
        s = self._scorer
        elapsed = s.elapsed_seconds
        mins, secs = divmod(int(elapsed), 60)
        self.query_one("#wpm-val", Label).update(f"{s.wpm:.0f}")
        self.query_one("#acc-val", Label).update(f"{s.accuracy:.1f}%")
        self.query_one("#time-val", Label).update(f"{mins}:{secs:02d}")
        self.query_one("#err-val", Label).update(str(s.error_count))
        pct = int((s.position / max(len(s.target), 1)) * 100)
        self.query_one("#progress-bar", ProgressBar).update(progress=pct)

    def _render_text(self) -> None:
        if self._scorer is None:
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
        self.query_one("#text-display", Static).update(typed + cursor + rest)

    def on_key(self, event) -> None:
        if self._scorer is None or self._paused or self._scorer.is_complete:
            return
        key = event.character
        if key is None or len(key) != 1:
            return
        self._scorer.process_key(key)
        self._render_text()
        app = self.app          # type: ignore[attr-defined]
        if app.config.show_hints:
            weak = app.adaptive.detect_weak_bigrams(self._scorer.keystrokes)
            if weak:
                self.query_one("#hint-bar", Label).update(
                    f"💡 Struggling with '{weak[0]}' — slow down slightly to build accuracy"
                )
            else:
                self.query_one("#hint-bar", Label).update("")
        if self._scorer.is_complete:
            self._finish()

    def _finish(self) -> None:
        if self._timer:
            self._timer.stop()
        s = self._scorer
        app = self.app          # type: ignore[attr-defined]
        new_level = app.adaptive.update_level(s.wpm, s.accuracy)
        app.config.difficulty = new_level
        rec = SessionRecord(
            timestamp=datetime.datetime.now().isoformat(),
            content_type=app.config.content_type,
            difficulty=app.adaptive.current_level,
            duration_seconds=int(s.elapsed_seconds),
            wpm=round(s.wpm, 2),
            accuracy=round(s.accuracy, 2),
            error_count=s.error_count,
            strict_mode=app.config.strict_mode,
        )
        session_id = app.storage.insert_session(rec)
        app.storage.insert_keystrokes(session_id, s.keystrokes)
        from typingapp.screens.results import ResultsScreen
        self.app.switch_screen(ResultsScreen(scorer=s, session_id=session_id))

    def action_pause(self) -> None:
        self._paused = not self._paused
        hint = self.query_one("#hint-bar", Label)
        hint.update("⏸ PAUSED — press ESC to resume" if self._paused else "")

    def action_restart(self) -> None:
        if self._timer:
            self._timer.stop()
        self._start_lesson()

    def action_quit_lesson(self) -> None:
        if self._timer:
            self._timer.stop()
        self.app.pop_screen()
```

- [ ] **Step 2: Run and start a lesson**

```bash
python -m typingapp
```
Expected: Start Lesson → typing text appears, green/red highlight tracks keypresses, WPM/accuracy update live, lesson completes and moves to Results.

- [ ] **Step 3: Commit**

```bash
git add typingapp/screens/lesson.py
git commit -m "feat: lesson screen with real-time stats, strict/lenient mode, adaptive hints"
```

---

## Task 14: Results Screen

**Files:**
- Create: `typingapp/screens/results.py`

- [ ] **Step 1: Create `typingapp/screens/results.py`**

```python
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import Vertical, Horizontal, Center

from typingapp.engine.scorer import Scorer


class ResultsScreen(Screen):
    BINDINGS = [("escape", "go_menu", "Menu")]

    def __init__(self, scorer: Scorer, session_id: int) -> None:
        super().__init__()
        self._scorer = scorer
        self._session_id = session_id

    def compose(self) -> ComposeResult:
        s = self._scorer
        app = self.app          # type: ignore[attr-defined]
        bigrams = app.storage.fetch_bigram_heatmap(limit=5)
        mins, secs = divmod(int(s.elapsed_seconds), 60)

        with Vertical():
            yield Static("🏁  Session Complete", classes="menu-title")
            yield Static("")
            with Horizontal():
                yield Label(f"⚡ WPM:      ", classes="stat-label")
                yield Label(f"{s.wpm:.0f}", classes="stat-value wpm-value")
            with Horizontal():
                yield Label(f"✓  Accuracy: ", classes="stat-label")
                yield Label(f"{s.accuracy:.1f}%", classes="stat-value acc-value")
            with Horizontal():
                yield Label(f"⏱  Time:     ", classes="stat-label")
                yield Label(f"{mins}:{secs:02d}", classes="stat-value time-value")
            with Horizontal():
                yield Label(f"✗  Errors:   ", classes="stat-label")
                yield Label(str(s.error_count), classes="stat-value err-value")
            yield Static("")
            if bigrams:
                yield Static("TOP MISTAKE BIGRAMS", classes="stat-label")
                for b in bigrams:
                    yield Label(f"  '{b['bigram']}' — {b['errors']} errors", classes="err-value")
            yield Static("")
            yield Button("▶  Retry Same", id="btn-retry", variant="primary")
            yield Button("🔀  New Lesson", id="btn-new")
            yield Button("📊  View History", id="btn-history")
            yield Button("🏠  Menu", id="btn-menu")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from typingapp.screens.lesson import LessonScreen
        from typingapp.screens.history import HistoryScreen
        from typingapp.screens.menu import MenuScreen
        if event.button.id == "btn-retry":
            self.app.switch_screen(LessonScreen())
        elif event.button.id == "btn-new":
            self.app.switch_screen(LessonScreen())
        elif event.button.id == "btn-history":
            self.app.push_screen(HistoryScreen())
        elif event.button.id == "btn-menu":
            self.app.switch_screen(MenuScreen())

    def action_go_menu(self) -> None:
        from typingapp.screens.menu import MenuScreen
        self.app.switch_screen(MenuScreen())
```

- [ ] **Step 2: Run through a full lesson → results**

```bash
python -m typingapp
```
Expected: After completing a lesson, Results screen shows WPM, accuracy, time, errors, and top mistake bigrams.

- [ ] **Step 3: Commit**

```bash
git add typingapp/screens/results.py
git commit -m "feat: results screen with session stats and top mistake bigrams"
```

---

## Task 15: History & Progress Dashboard

**Files:**
- Create: `typingapp/screens/history.py`

- [ ] **Step 1: Create `typingapp/screens/history.py`**

```python
from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import Vertical, ScrollableContainer

from typingapp.engine.recommender import Recommender


def _bar_chart(values: list[float], width: int = 30) -> str:
    if not values:
        return "(no data yet)"
    max_val = max(values) or 1
    lines = []
    for v in values:
        bar_len = int((v / max_val) * width)
        bar = "▓" * bar_len
        lines.append(f"{v:5.0f} {bar}")
    return "\n".join(lines)


def _heatmap_line(bigrams: list[dict]) -> str:
    if not bigrams:
        return "(no data)"
    colors = ["red", "orange3", "yellow3", "white"]
    parts = []
    for i, b in enumerate(bigrams[:8]):
        color = colors[min(i, len(colors) - 1)]
        parts.append(f"[{color}]{b['bigram']}({b['errors']})[/]")
    return "  ".join(parts)


class HistoryScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        app = self.app          # type: ignore[attr-defined]
        sessions = app.storage.fetch_recent_sessions(limit=30)
        wpms = app.storage.fetch_last_n_wpm(n=14)
        summary = app.storage.fetch_summary()
        bigrams = app.storage.fetch_bigram_heatmap(limit=8)
        weak = [b["bigram"] for b in bigrams]
        recommendation = Recommender().recommend(sessions, bigrams=weak)

        with ScrollableContainer():
            yield Static("📊  Progress Dashboard", classes="menu-title")
            yield Static("")

            yield Static("WPM — LAST 14 SESSIONS", classes="stat-label")
            yield Static(_bar_chart(wpms), id="wpm-chart")
            yield Static("")

            yield Static("SUMMARY", classes="stat-label")
            yield Label(f"  Best WPM:       {summary['best_wpm'] or 0:.0f}", classes="wpm-value")
            yield Label(f"  Avg Accuracy:   {summary['avg_accuracy'] or 0:.1f}%", classes="acc-value")
            yield Label(f"  Total Sessions: {summary['total']}", classes="time-value")
            yield Static("")

            yield Static("MISTAKE HEATMAP (cumulative)", classes="stat-label")
            yield Static(_heatmap_line(bigrams), id="heatmap")
            yield Static("")

            yield Static("🤖  RECOMMENDATION", classes="stat-label")
            yield Label(recommendation, id="rec-label", classes="hint-bar")
            yield Static("")

            yield Button("← Back", id="btn-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
```

- [ ] **Step 2: Run the app and navigate to History**

```bash
python -m typingapp
```
Expected: History screen shows WPM bar chart, summary stats, bigram heatmap with color coding, and a recommendation message.

- [ ] **Step 3: Commit**

```bash
git add typingapp/screens/history.py
git commit -m "feat: history dashboard with WPM chart, heatmap, and recommendations"
```

---

## Task 16: Wire Custom Text into Menu Flow

**Files:**
- Modify: `typingapp/screens/menu.py`

- [ ] **Step 1: Update `on_button_pressed` in `MenuScreen` to handle custom content type**

Replace the `btn-start` handler in `typingapp/screens/menu.py`:

```python
def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == "btn-start":
        cfg = self.app.config       # type: ignore[attr-defined]
        if cfg.content_type == "custom":
            from typingapp.screens.custom_text import CustomTextScreen
            from typingapp.screens.lesson import LessonScreen
            def start_with_text(text: str) -> None:
                self.app.pop_screen()
                self.app.push_screen(LessonScreen(custom_text=text))
            self.app.push_screen(CustomTextScreen(on_confirm=start_with_text))
        else:
            from typingapp.screens.lesson import LessonScreen
            self.app.push_screen(LessonScreen())
    elif event.button.id == "btn-history":
        from typingapp.screens.history import HistoryScreen
        self.app.push_screen(HistoryScreen())
    elif event.button.id == "btn-settings":
        from typingapp.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen())
    elif event.button.id == "btn-quit":
        self.app.exit()
```

- [ ] **Step 2: Test the custom text flow**

```bash
python -m typingapp
```
Expected: Set content type to "Custom" in Settings. Return to menu, press Start Lesson → Custom Text screen appears with TextArea → enter text → lesson starts with that text.

- [ ] **Step 3: Commit**

```bash
git add typingapp/screens/menu.py
git commit -m "feat: custom text flow - route through CustomTextScreen when content type is custom"
```

---

## Task 17: CLAUDE.md & Final Smoke Test

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Create `CLAUDE.md`**

```markdown
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
- `AdaptiveEngine.current_level` persists on `app.adaptive` across lessons (not saved to config on every keystroke — only on lesson end).
- All DB writes happen in `LessonScreen._finish()`.
```

- [ ] **Step 2: Full smoke test — complete two lessons and check history**

```bash
python -m typingapp
```
Expected:
1. Menu shows "No last session" first run
2. Start lesson → type through text → Results screen
3. Start another lesson → Results screen again
4. Open History → bar chart shows 2 data points, recommendation appears

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```
Expected: All tests pass.

- [ ] **Step 4: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with architecture overview and commands"
```

---

## Self-Review

### Spec Coverage Check

| Spec requirement | Task |
|---|---|
| CLI / Python / Textual | Task 1, 9 |
| Vibrant colorful TUI | Task 9 (CSS) |
| Words / Sentences / Code / Custom content | Task 5, 6 |
| Adaptive difficulty (level up/down) | Task 7 |
| Adaptive hints (bigram detection) | Task 7, 13 |
| Real-time WPM, accuracy, time, errors | Task 4, 13 |
| Strict mode toggle | Task 2, 11 |
| Settings screen | Task 11 |
| SQLite database | Task 3 |
| Session history | Task 3 |
| WPM trend chart | Task 15 |
| Mistake heatmap | Task 15 |
| Recommendations | Task 8, 15 |
| Custom text via TextArea | Task 12, 16 |
| Results screen | Task 14 |
| Menu with last session summary | Task 10 |
| CLAUDE.md | Task 17 |

All spec requirements covered. ✓

### Placeholder Scan

No TBDs, TODOs, or vague steps found. All code blocks are complete.

### Type Consistency

- `KeystrokeRecord` defined in `storage.py` (Task 3), imported by `scorer.py` (Task 4) and `adaptive.py` (Task 7) — consistent.
- `Scorer` defined in Task 4, instantiated in `lesson.py` (Task 13) and passed to `ResultsScreen` (Task 14) — consistent.
- `AppConfig` fields (`strict_mode`, `content_type`, `session_duration`, `difficulty`, `show_live_wpm`, `show_hints`) used consistently across config, settings screen, and lesson screen.
- `Storage` methods (`fetch_recent_sessions`, `fetch_bigram_heatmap`, `fetch_last_n_wpm`, `fetch_summary`, `insert_session`, `insert_keystrokes`) defined in Task 3 and called correctly in Tasks 10, 13, 14, 15.
