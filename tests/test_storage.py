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


def test_get_book_returns_none_when_missing(tmp_path):
    s = Storage(tmp_path / "test.db")
    assert s.get_book("gutenberg:1342") is None
    s.close()


def test_upsert_book_insert_then_update(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.upsert_book(
        book_id="gutenberg:1342", source="gutenberg", title="Pride and Prejudice",
        author="Jane Austen", language="en", full_text="It is a truth...",
        cached_at="2026-07-26T10:00:00",
    )
    book = s.get_book("gutenberg:1342")
    assert book["title"] == "Pride and Prejudice"
    assert book["total_chars"] == len("It is a truth...")

    s.upsert_book(
        book_id="gutenberg:1342", source="gutenberg", title="Pride and Prejudice",
        author="Jane Austen", language="en", full_text="It is a truth universally acknowledged...",
        cached_at="2026-07-26T11:00:00",
    )
    updated = s.get_book("gutenberg:1342")
    assert updated["cached_at"] == "2026-07-26T11:00:00"
    assert updated["total_chars"] == len("It is a truth universally acknowledged...")
    s.close()


def test_fetch_book_progress_defaults_to_zero(tmp_path):
    s = Storage(tmp_path / "test.db")
    assert s.fetch_book_progress("gutenberg:1342") == 0
    s.close()


def test_update_book_progress_upserts(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.upsert_book(
        book_id="gutenberg:1342", source="gutenberg", title="T", author="A",
        language="en", full_text="x" * 100, cached_at="2026-07-26T10:00:00",
    )
    s.update_book_progress("gutenberg:1342", current_offset=50, updated_at="2026-07-26T10:05:00")
    assert s.fetch_book_progress("gutenberg:1342") == 50
    s.update_book_progress("gutenberg:1342", current_offset=80, updated_at="2026-07-26T10:10:00")
    assert s.fetch_book_progress("gutenberg:1342") == 80
    s.close()


def test_delete_book_removes_book_and_its_progress(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                  language="en", full_text="x" * 10, cached_at="2026-07-26T09:00:00")
    s.update_book_progress("gutenberg:1", current_offset=5, updated_at="2026-07-26T09:05:00")

    s.delete_book("gutenberg:1")

    assert s.get_book("gutenberg:1") is None
    assert s.fetch_book_progress("gutenberg:1") == 0
    assert s.list_books_with_progress() == []
    s.close()


def test_delete_book_is_a_noop_for_unknown_book_id(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.delete_book("gutenberg:999")  # should not raise
    s.close()


def test_list_books_with_progress_orders_by_most_recently_updated(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.upsert_book(book_id="gutenberg:1", source="gutenberg", title="First", author="A",
                   language="en", full_text="x" * 10, cached_at="2026-07-26T09:00:00")
    s.upsert_book(book_id="gutenberg:2", source="gutenberg", title="Second", author="B",
                   language="en", full_text="y" * 10, cached_at="2026-07-26T09:00:00")
    s.update_book_progress("gutenberg:2", current_offset=5, updated_at="2026-07-26T12:00:00")
    books = s.list_books_with_progress(limit=10)
    assert [b["title"] for b in books] == ["Second", "First"]
    assert books[0]["current_offset"] == 5
    assert books[1]["current_offset"] == 0
    s.close()


def test_record_word_mistakes_creates_new_entries(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({"the": 2, "quick": 1})
    missed = s.fetch_frequently_missed_words(min_misses=1)
    assert missed == {"the", "quick"}
    s.close()


def test_record_word_mistakes_accumulates_across_calls(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({"the": 2})
    s.record_word_mistakes({"the": 3, "fox": 1})
    # "the" should now have 5 cumulative misses, "fox" only 1
    assert s.fetch_frequently_missed_words(min_misses=4) == {"the"}
    assert s.fetch_frequently_missed_words(min_misses=1) == {"the", "fox"}
    s.close()


def test_fetch_frequently_missed_words_respects_min_misses_threshold(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({"rare": 1, "common": 10})
    assert s.fetch_frequently_missed_words(min_misses=2) == {"common"}
    s.close()


def test_fetch_frequently_missed_words_empty_when_no_data(tmp_path):
    s = Storage(tmp_path / "test.db")
    assert s.fetch_frequently_missed_words() == set()
    s.close()


def test_record_word_mistakes_with_empty_dict_is_a_noop(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.record_word_mistakes({})
    assert s.fetch_frequently_missed_words(min_misses=1) == set()
    s.close()
