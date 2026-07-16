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
