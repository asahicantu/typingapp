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
    assert s.position == 0
    assert s.error_count == 1


def test_incorrect_keystroke_lenient_mode_advances():
    s = Scorer("hi", strict_mode=False)
    s.start()
    result = s.process_key("x")
    assert result is False
    assert s.position == 1
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
    s.process_key("a")
    s.process_key("x")
    s.process_key("c")
    assert s.accuracy == pytest.approx(66.67, abs=0.1)


def test_bigram_tracking():
    s = Scorer("abc", strict_mode=False)
    s.start()
    s.process_key("a")
    s.process_key("x")
    assert s.keystrokes[-1].bigram == "ab"


def test_wpm_nonzero_after_typing(monkeypatch):
    s = Scorer("the quick")
    s.start()
    s._start_time -= 30
    for ch in "the quick":
        s.process_key(ch)
    assert s.wpm > 0


def test_word_error_attributed_to_correct_word():
    s = Scorer("cat dog", strict_mode=False)
    s.start()
    for ch in "cat ":
        s.process_key(ch)
    s.process_key("x")  # wrong 'd' in "dog"
    s.process_key("o")
    s.process_key("g")
    assert s.word_errors == {"dog": 1}


def test_word_error_attributed_to_first_word():
    s = Scorer("cat dog", strict_mode=False)
    s.start()
    s.process_key("x")  # wrong 'c' in "cat"
    assert s.word_errors == {"cat": 1}


def test_multiple_errors_same_word_accumulate():
    s = Scorer("hello", strict_mode=False)
    s.start()
    s.process_key("x")
    s.process_key("y")
    s.process_key("l")
    s.process_key("l")
    s.process_key("o")
    assert s.word_errors == {"hello": 2}


def test_top_mistaken_words_sorted_desc():
    s = Scorer("aa bb bb cc cc cc", strict_mode=False)
    s.start()
    for ch in s.target:
        s.process_key("!" if ch != " " else " ")
    top = s.top_mistaken_words(limit=2)
    # "cc" occurs 3x (6 char-errors), "bb" occurs 2x (4 char-errors), "aa" once (2 char-errors)
    assert top[0] == ("cc", 6)
    assert top[1] == ("bb", 4)


def test_strict_mode_retries_count_once_per_error():
    s = Scorer("hi", strict_mode=True)
    s.start()
    s.process_key("x")
    s.process_key("x")
    s.process_key("h")
    assert s.word_errors == {"hi": 2}


def test_extend_appends_to_target_without_resetting_position():
    s = Scorer("ab", strict_mode=False)
    s.start()
    s.process_key("a")
    s.process_key("b")
    assert s.is_complete
    s.extend(" cd")
    assert s.target == "ab cd"
    assert s.position == 2
    assert not s.is_complete


def test_extend_preserves_stats():
    s = Scorer("ab", strict_mode=False)
    s.start()
    s.process_key("a")
    s.process_key("x")  # one error
    s.extend(" cd")
    assert s.error_count == 1
    assert len(s.keystrokes) == 2
