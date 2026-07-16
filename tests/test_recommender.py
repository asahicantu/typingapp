import pytest
from typingapp.engine.recommender import Recommender


def _session(wpm=70.0, accuracy=92.0, content_type="words"):
    return {"wpm": wpm, "accuracy": accuracy, "content_type": content_type}


def test_plateau_recommendation():
    rec = Recommender()
    sessions = [_session(wpm=70 + i * 0.1) for i in range(8)]
    result = rec.recommend(sessions, bigrams=["th"])
    assert "th" in result.lower() or "bigram" in result.lower() or "drill" in result.lower()


def test_low_accuracy_recommends_strict_mode():
    rec = Recommender()
    sessions = [_session(accuracy=75.0) for _ in range(5)]
    result = rec.recommend(sessions, bigrams=[])
    assert "strict" in result.lower()


def test_content_gap_recommends_practice():
    rec = Recommender()
    sessions = [_session(wpm=80, content_type="words") for _ in range(4)] + \
               [_session(wpm=40, content_type="code") for _ in range(3)]
    result = rec.recommend(sessions, bigrams=[])
    assert "code" in result.lower()


def test_positive_reinforcement_on_streak():
    rec = Recommender()
    sessions = [_session(wpm=60 + i * 3, accuracy=95.0) for i in range(5)]
    result = rec.recommend(sessions, bigrams=[])
    assert len(result) > 0


def test_no_sessions_returns_start_message():
    rec = Recommender()
    result = rec.recommend([], bigrams=[])
    assert len(result) > 0
