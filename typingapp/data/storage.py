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
