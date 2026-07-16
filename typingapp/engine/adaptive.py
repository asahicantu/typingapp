from __future__ import annotations
from collections import defaultdict
from typingapp.data.storage import KeystrokeRecord

LEVEL_WPM_THRESHOLDS = {
    1: 20, 2: 30, 3: 40, 4: 50, 5: 60,
    6: 70, 7: 80, 8: 90, 9: 100, 10: 120,
}


class AdaptiveEngine:
    def __init__(self, current_level: int = 1) -> None:
        self.current_level = max(1, min(current_level, 10))

    def update_level(self, wpm: float, accuracy: float) -> int:
        threshold = LEVEL_WPM_THRESHOLDS.get(self.current_level, 60)
        if wpm >= threshold and accuracy >= 95.0 and self.current_level < 10:
            self.current_level += 1
        elif accuracy < 80.0 and self.current_level > 1:
            self.current_level -= 1
        return self.current_level

    def detect_weak_bigrams(
        self, keystrokes: list[KeystrokeRecord], threshold: float = 0.15
    ) -> list[str]:
        bigram_total: dict[str, int] = defaultdict(int)
        bigram_errors: dict[str, int] = defaultdict(int)
        for ks in keystrokes:
            if ks.bigram:
                bigram_total[ks.bigram] += 1
                if not ks.correct:
                    bigram_errors[ks.bigram] += 1
        return [
            bg for bg, total in bigram_total.items()
            if total > 0 and bigram_errors[bg] / total >= threshold
        ]
