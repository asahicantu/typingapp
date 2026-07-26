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

CREATE_GUTENBERG_CACHE = """
CREATE TABLE IF NOT EXISTS gutenberg_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gutenberg_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    language TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    fetched_at TEXT NOT NULL
)"""

CREATE_BOOKS = """
CREATE TABLE IF NOT EXISTS books (
    book_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    language TEXT NOT NULL,
    full_text TEXT NOT NULL,
    total_chars INTEGER NOT NULL,
    cached_at TEXT NOT NULL
)"""

CREATE_BOOK_PROGRESS = """
CREATE TABLE IF NOT EXISTS book_progress (
    book_id TEXT PRIMARY KEY REFERENCES books(book_id),
    current_offset INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
)"""

CREATE_WORD_MISTAKES = """
CREATE TABLE IF NOT EXISTS word_mistakes (
    word TEXT PRIMARY KEY,
    miss_count INTEGER NOT NULL DEFAULT 0
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


@dataclass
class GutenbergExcerpt:
    gutenberg_id: int
    title: str
    author: str
    language: str
    excerpt: str
    fetched_at: str


class Storage:
    def __init__(self, path: Path = DEFAULT_DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute(CREATE_SESSIONS)
        self._conn.execute(CREATE_KEYSTROKES)
        self._conn.execute(CREATE_GUTENBERG_CACHE)
        self._conn.execute(CREATE_BOOKS)
        self._conn.execute(CREATE_BOOK_PROGRESS)
        self._conn.execute(CREATE_WORD_MISTAKES)
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

    def cache_excerpt(
        self, gutenberg_id: int, title: str, author: str, language: str,
        excerpt: str, fetched_at: str,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO gutenberg_cache (gutenberg_id, title, author, language, excerpt, fetched_at) "
            "VALUES (?,?,?,?,?,?)",
            (gutenberg_id, title, author, language, excerpt, fetched_at),
        )
        self._conn.commit()
        return cur.lastrowid

    def fetch_cached_excerpts(self, language: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM gutenberg_cache WHERE language=? ORDER BY fetched_at DESC LIMIT ?",
            (language, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def prune_old_excerpts(self, language: str, keep: int = 20) -> None:
        self._conn.execute(
            "DELETE FROM gutenberg_cache WHERE language=? AND id NOT IN ("
            "  SELECT id FROM gutenberg_cache WHERE language=? "
            "  ORDER BY fetched_at DESC LIMIT ?"
            ")",
            (language, language, keep),
        )
        self._conn.commit()

    def get_book(self, book_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
        return dict(row) if row else None

    def upsert_book(
        self, book_id: str, source: str, title: str, author: str, language: str,
        full_text: str, cached_at: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO books (book_id, source, title, author, language, full_text, total_chars, cached_at) "
            "VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(book_id) DO UPDATE SET "
            "source=excluded.source, title=excluded.title, author=excluded.author, "
            "language=excluded.language, full_text=excluded.full_text, "
            "total_chars=excluded.total_chars, cached_at=excluded.cached_at",
            (book_id, source, title, author, language, full_text, len(full_text), cached_at),
        )
        self._conn.commit()

    def fetch_book_progress(self, book_id: str) -> int:
        row = self._conn.execute(
            "SELECT current_offset FROM book_progress WHERE book_id=?", (book_id,)
        ).fetchone()
        return row["current_offset"] if row else 0

    def update_book_progress(self, book_id: str, current_offset: int, updated_at: str) -> None:
        self._conn.execute(
            "INSERT INTO book_progress (book_id, current_offset, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(book_id) DO UPDATE SET "
            "current_offset=excluded.current_offset, updated_at=excluded.updated_at",
            (book_id, current_offset, updated_at),
        )
        self._conn.commit()

    def delete_book(self, book_id: str) -> None:
        self._conn.execute("DELETE FROM book_progress WHERE book_id=?", (book_id,))
        self._conn.execute("DELETE FROM books WHERE book_id=?", (book_id,))
        self._conn.commit()

    def list_books_with_progress(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT b.book_id, b.title, b.author, b.source, b.language, b.total_chars, "
            "COALESCE(p.current_offset, 0) AS current_offset, "
            "COALESCE(p.updated_at, b.cached_at) AS updated_at "
            "FROM books b LEFT JOIN book_progress p ON p.book_id = b.book_id "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def record_word_mistakes(self, word_counts: dict[str, int]) -> None:
        if not word_counts:
            return
        self._conn.executemany(
            "INSERT INTO word_mistakes (word, miss_count) VALUES (?, ?) "
            "ON CONFLICT(word) DO UPDATE SET miss_count = miss_count + excluded.miss_count",
            list(word_counts.items()),
        )
        self._conn.commit()

    def fetch_frequently_missed_words(self, min_misses: int = 2, limit: int = 200) -> set[str]:
        rows = self._conn.execute(
            "SELECT word FROM word_mistakes WHERE miss_count >= ? ORDER BY miss_count DESC LIMIT ?",
            (min_misses, limit),
        ).fetchall()
        return {r["word"] for r in rows}

    def close(self) -> None:
        self._conn.close()
