from __future__ import annotations

MIN_WPM_FLOOR = 15
MIN_WORD_COUNT = 10


def estimate_word_count(
    recent_wpm: float,
    session_duration_seconds: int,
    slack_factor: float = 1.3,
) -> int:
    """Estimate how many words of lesson text to prepare for a session,
    sized so an average typist at recent_wpm finishes near
    session_duration_seconds, with slack_factor extra so most users
    don't run out of text before time's up."""
    effective_wpm = max(recent_wpm, MIN_WPM_FLOOR)
    minutes = session_duration_seconds / 60
    estimated = effective_wpm * minutes * slack_factor
    return max(MIN_WORD_COUNT, round(estimated))
