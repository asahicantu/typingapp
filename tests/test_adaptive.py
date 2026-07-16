import pytest
from typingapp.engine.adaptive import AdaptiveEngine


def test_level_up_on_high_performance():
    eng = AdaptiveEngine(current_level=3)
    new_level = eng.update_level(wpm=80, accuracy=96.0)
    assert new_level == 4


def test_level_down_on_low_accuracy():
    eng = AdaptiveEngine(current_level=5)
    new_level = eng.update_level(wpm=40, accuracy=75.0)
    assert new_level == 4


def test_level_stays_on_middle_performance():
    eng = AdaptiveEngine(current_level=3)
    new_level = eng.update_level(wpm=50, accuracy=88.0)
    assert new_level == 3


def test_level_clamps_at_minimum():
    eng = AdaptiveEngine(current_level=1)
    new_level = eng.update_level(wpm=10, accuracy=60.0)
    assert new_level == 1


def test_level_clamps_at_maximum():
    eng = AdaptiveEngine(current_level=10)
    new_level = eng.update_level(wpm=200, accuracy=99.0)
    assert new_level == 10


def test_detect_weak_bigrams():
    from typingapp.data.storage import KeystrokeRecord
    eng = AdaptiveEngine(current_level=3)
    keystrokes = (
        [KeystrokeRecord(expected="t", actual="x", correct=False, bigram="th", timestamp_ms=i)
         for i in range(6)]
        + [KeystrokeRecord(expected="h", actual="h", correct=True, bigram="th", timestamp_ms=i+100)
           for i in range(30)]
    )
    weak = eng.detect_weak_bigrams(keystrokes, threshold=0.15)
    assert "th" in weak


def test_no_weak_bigrams_when_accurate():
    from typingapp.data.storage import KeystrokeRecord
    eng = AdaptiveEngine(current_level=3)
    keystrokes = [
        KeystrokeRecord(expected="t", actual="t", correct=True, bigram="th", timestamp_ms=i)
        for i in range(20)
    ]
    weak = eng.detect_weak_bigrams(keystrokes, threshold=0.15)
    assert "th" not in weak
