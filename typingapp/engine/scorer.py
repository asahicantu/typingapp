from __future__ import annotations
import time
from dataclasses import dataclass, field

from typingapp.data.storage import KeystrokeRecord


@dataclass
class Scorer:
    target: str
    strict_mode: bool = False
    position: int = field(default=0, init=False)
    error_count: int = field(default=0, init=False)
    keystrokes: list[KeystrokeRecord] = field(default_factory=list, init=False)
    _start_time: float = field(default=0.0, init=False)
    _total_keys: int = field(default=0, init=False)
    _correct_keys: int = field(default=0, init=False)

    def start(self) -> None:
        self._start_time = time.monotonic()

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time == 0:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def wpm(self) -> float:
        elapsed_min = self.elapsed_seconds / 60
        if elapsed_min == 0:
            return 0.0
        return (self._correct_keys / 5) / elapsed_min

    @property
    def accuracy(self) -> float:
        if self._total_keys == 0:
            return 100.0
        return (self._correct_keys / self._total_keys) * 100

    @property
    def is_complete(self) -> bool:
        return self.position >= len(self.target)

    def process_key(self, char: str) -> bool:
        expected = self.target[self.position]
        correct = char == expected
        bigram = self.target[self.position - 1: self.position + 1] if self.position > 0 else None
        self.keystrokes.append(KeystrokeRecord(
            expected=expected,
            actual=char,
            correct=correct,
            bigram=bigram,
            timestamp_ms=int(time.monotonic() * 1000),
        ))
        self._total_keys += 1
        if correct:
            self._correct_keys += 1
            self.position += 1
        else:
            self.error_count += 1
            if not self.strict_mode:
                self.position += 1
        return correct
