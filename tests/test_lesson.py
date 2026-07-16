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
