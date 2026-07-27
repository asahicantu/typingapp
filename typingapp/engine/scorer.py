from __future__ import annotations
import re
import time
from dataclasses import dataclass, field

from typingapp.data.storage import KeystrokeRecord

_STRIP_NON_ALNUM_RE = re.compile(r"^\W+|\W+$")


def normalize_mistake_word(word: str) -> str:
    """Normalize a word for use as a mistake-tracking lookup key.

    Strips leading/trailing non-word characters (punctuation such as commas,
    periods, quotes, em-dashes, etc.) and lowercases the result. This is the
    ONE shared normalization used everywhere a word is written to or read
    from the mistake-tracking system (Scorer.word_errors, Storage's
    word_mistakes table, and the LessonScreen highlight-lookup code), so a
    word like "dog," typed with an error and a word rendered as "Dog" in a
    later lesson are recognized as the same key. It intentionally does NOT
    change what is rendered/highlighted on screen -- only the lookup key.
    """
    return _STRIP_NON_ALNUM_RE.sub("", word).lower()


def current_word_at(text: str, position: int) -> str:
    """Return the word (original case/punctuation, unlike normalize_mistake_word)
    containing text[position], or "" if position is out of bounds or lands on
    whitespace. Used for display purposes (e.g. the finger-hint coaching bar),
    not for mistake-tracking lookups."""
    if not text or position < 0 or position >= len(text):
        return ""
    if text[position].isspace():
        return ""
    start = text.rfind(" ", 0, position) + 1
    end = text.find(" ", position)
    if end == -1:
        end = len(text)
    return text[start:end]


@dataclass
class Scorer:
    target: str
    strict_mode: bool = False
    position: int = field(default=0, init=False)
    error_count: int = field(default=0, init=False)
    keystrokes: list[KeystrokeRecord] = field(default_factory=list, init=False)
    word_errors: dict[str, int] = field(default_factory=dict, init=False)
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
            word = self._word_at(self.position)
            if word:
                self.word_errors[word] = self.word_errors.get(word, 0) + 1
            if not self.strict_mode:
                self.position += 1
        return correct

    def _word_at(self, index: int) -> str:
        start = self.target.rfind(" ", 0, index) + 1
        end = self.target.find(" ", index)
        if end == -1:
            end = len(self.target)
        return normalize_mistake_word(self.target[start:end])

    def top_mistaken_words(self, limit: int = 5) -> list[tuple[str, int]]:
        return sorted(self.word_errors.items(), key=lambda kv: kv[1], reverse=True)[:limit]

    def extend(self, more_text: str) -> None:
        self.target += more_text
