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


def test_current_word_at_returns_the_word_containing_position():
    from typingapp.engine.scorer import current_word_at
    text = "the quick brown fox"
    # position 4 is the 'q' in "quick"
    assert current_word_at(text, 4) == "quick"


def test_current_word_at_preserves_original_case_and_punctuation():
    from typingapp.engine.scorer import current_word_at
    text = "Hello, World!"
    assert current_word_at(text, 0) == "Hello,"


def test_current_word_at_at_start_of_text():
    from typingapp.engine.scorer import current_word_at
    text = "start of text"
    assert current_word_at(text, 0) == "start"


def test_current_word_at_at_last_word():
    from typingapp.engine.scorer import current_word_at
    text = "the last word"
    assert current_word_at(text, len(text) - 1) == "word"


def test_current_word_at_on_whitespace_returns_empty():
    from typingapp.engine.scorer import current_word_at
    text = "two  words"  # double space at index 3-4
    assert current_word_at(text, 3) == ""


def test_current_word_at_out_of_bounds_returns_empty():
    from typingapp.engine.scorer import current_word_at
    text = "short"
    assert current_word_at(text, len(text)) == ""
    assert current_word_at(text, -1) == ""
    assert current_word_at(text, 999) == ""


def test_current_word_at_empty_text_returns_empty():
    from typingapp.engine.scorer import current_word_at
    assert current_word_at("", 0) == ""
