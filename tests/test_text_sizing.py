import pytest
from typingapp.engine.text_sizing import estimate_word_count, MIN_WPM_FLOOR


def test_estimate_scales_with_wpm():
    low = estimate_word_count(recent_wpm=20, session_duration_seconds=60)
    high = estimate_word_count(recent_wpm=80, session_duration_seconds=60)
    assert high > low


def test_estimate_scales_with_duration():
    short = estimate_word_count(recent_wpm=40, session_duration_seconds=30)
    long_ = estimate_word_count(recent_wpm=40, session_duration_seconds=120)
    assert long_ > short


def test_estimate_applies_slack_factor():
    # 40 wpm for 60s = 40 words at 1.0x; with 1.3x slack, expect ~52
    result = estimate_word_count(recent_wpm=40, session_duration_seconds=60, slack_factor=1.3)
    assert result == pytest.approx(52, abs=1)


def test_zero_or_negative_wpm_uses_floor():
    result = estimate_word_count(recent_wpm=0, session_duration_seconds=60)
    floored = estimate_word_count(recent_wpm=MIN_WPM_FLOOR, session_duration_seconds=60)
    assert result == floored


def test_result_is_at_least_ten_words():
    result = estimate_word_count(recent_wpm=1, session_duration_seconds=5)
    assert result >= 10
