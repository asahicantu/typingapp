import pytest
from typingapp.data.storage import Storage, SessionRecord, KeystrokeRecord


def test_init_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    s = Storage(db_path)
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
