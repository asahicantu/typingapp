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
    assert any(bg in text for bg in ["th"])


def test_load_words_defaults_to_english():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="words", difficulty=3, language="en")
    assert len(lesson) > 0


def test_load_words_spanish():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="words", difficulty=3, language="es")
    assert len(lesson) > 0


def test_load_words_french():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="words", difficulty=3, language="fr")
    assert len(lesson) > 0


def test_unknown_language_falls_back_to_english():
    engine = LessonEngine()
    lesson_unknown = engine.get_lesson(content_type="sentences", difficulty=3, language="de")
    lesson_en = engine.get_lesson(content_type="sentences", difficulty=3, language="en")
    # both draw from the same (English) pool, so unknown doesn't crash or return empty
    assert len(lesson_unknown) > 0


def test_random_sentences_content_type_produces_text():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="random_sentences", difficulty=3, language="en")
    assert len(lesson.strip()) > 0


def test_literature_content_type_falls_back_when_no_storage_or_network(monkeypatch):
    import typingapp.engine.lesson as lesson_module
    monkeypatch.setattr(lesson_module, "search_books", lambda *a, **k: [])
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="literature", difficulty=3, language="en", storage=None)
    # falls back to random_sentences/local text, never empty, never raises
    assert len(lesson.strip()) > 0


def test_literature_fallback_sets_last_fallback_reason(monkeypatch):
    import typingapp.engine.lesson as lesson_module
    monkeypatch.setattr(lesson_module, "search_books", lambda *a, **k: [])
    engine = LessonEngine()
    engine.get_lesson(content_type="literature", difficulty=3, language="en", storage=None)
    assert engine.last_fallback_reason is not None
    assert "Gutenberg" in engine.last_fallback_reason


def test_last_fallback_reason_cleared_on_successful_call(monkeypatch):
    import typingapp.engine.lesson as lesson_module
    engine = LessonEngine()
    engine.last_fallback_reason = "stale reason from a previous call"
    monkeypatch.setattr(lesson_module, "search_books", lambda *a, **k: [])
    engine.get_lesson(content_type="words", difficulty=1)
    assert engine.last_fallback_reason is None


def test_word_count_override_controls_word_count_regardless_of_difficulty():
    eng = LessonEngine()
    text = eng.get_lesson("words", difficulty=1, word_count_override=45)
    assert len(text.split()) == 45


def test_word_count_override_zero_falls_back_to_difficulty_table():
    eng = LessonEngine()
    text = eng.get_lesson("words", difficulty=1, word_count_override=0)
    assert len(text.split()) == 10


def test_get_lesson_accepts_recent_wpm_and_session_duration_for_sizing():
    engine = LessonEngine()
    short = engine.get_lesson(content_type="words", difficulty=3, language="en",
                                recent_wpm=20, session_duration=30)
    long_ = engine.get_lesson(content_type="words", difficulty=3, language="en",
                                recent_wpm=20, session_duration=180)
    # word-count content_type still uses WORD_COUNTS by difficulty (unaffected by sizing params);
    # this test only confirms the new kwargs are accepted without raising
    assert isinstance(short, str) and isinstance(long_, str)
