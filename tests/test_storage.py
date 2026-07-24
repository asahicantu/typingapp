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


def test_cache_excerpt_and_fetch(tmp_path):
    s = Storage(tmp_path / "test.db")
    excerpt_id = s.cache_excerpt(
        gutenberg_id=1342, title="Pride and Prejudice", author="Jane Austen",
        language="en", excerpt="It is a truth universally acknowledged...",
        fetched_at="2026-07-24T10:00:00",
    )
    assert excerpt_id > 0
    cached = s.fetch_cached_excerpts(language="en", limit=10)
    assert len(cached) == 1
    assert cached[0]["title"] == "Pride and Prejudice"
    assert cached[0]["gutenberg_id"] == 1342
    s.close()


def test_fetch_cached_excerpts_filters_by_language(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.cache_excerpt(gutenberg_id=1, title="A", author="X", language="en",
                     excerpt="text", fetched_at="2026-07-24T10:00:00")
    s.cache_excerpt(gutenberg_id=2, title="B", author="Y", language="es",
                     excerpt="texto", fetched_at="2026-07-24T10:00:00")
    en_only = s.fetch_cached_excerpts(language="en", limit=10)
    assert len(en_only) == 1
    assert en_only[0]["title"] == "A"
    s.close()


def test_prune_old_excerpts_keeps_only_n_most_recent(tmp_path):
    s = Storage(tmp_path / "test.db")
    for i in range(5):
        s.cache_excerpt(
            gutenberg_id=i, title=f"Book{i}", author="X", language="en",
            excerpt="text", fetched_at=f"2026-07-{i+1:02d}T10:00:00",
        )
    s.prune_old_excerpts(language="en", keep=2)
    remaining = s.fetch_cached_excerpts(language="en", limit=10)
    assert len(remaining) == 2
    # keeps the most recently fetched
    titles = {r["title"] for r in remaining}
    assert titles == {"Book3", "Book4"}
    s.close()
