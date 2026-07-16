from __future__ import annotations
import random
from importlib import resources
from typingapp.engine.content.code_snippets import SNIPPETS

WORD_COUNTS = {1: 10, 2: 15, 3: 20, 4: 25, 5: 30, 6: 40, 7: 50, 8: 60, 9: 80, 10: 100}


def _load_words() -> list[str]:
    pkg = resources.files("typingapp.engine.content")
    return (pkg / "words.txt").read_text(encoding="utf-8").splitlines()


def _load_sentences() -> list[str]:
    pkg = resources.files("typingapp.engine.content")
    return (pkg / "sentences.txt").read_text(encoding="utf-8").splitlines()


class LessonEngine:
    def __init__(self) -> None:
        self._words = _load_words()
        self._sentences = _load_sentences()

    def get_lesson(
        self,
        content_type: str,
        difficulty: int,
        custom_text: str = "",
        weak_bigrams: list[str] | None = None,
    ) -> str:
        if content_type == "custom":
            return custom_text
        if content_type == "sentences":
            return random.choice(self._sentences)
        if content_type == "code":
            return random.choice(SNIPPETS)
        return self._build_word_lesson(difficulty, weak_bigrams or [])

    def _build_word_lesson(self, difficulty: int, weak_bigrams: list[str]) -> str:
        count = WORD_COUNTS.get(max(1, min(difficulty, 10)), 20)
        pool = self._words
        if weak_bigrams:
            biased = [w for w in pool if any(bg in w for bg in weak_bigrams)]
            if biased:
                n_biased = count // 2
                chosen = random.choices(biased, k=n_biased) + random.choices(pool, k=count - n_biased)
                random.shuffle(chosen)
                return " ".join(chosen)
        return " ".join(random.choices(pool, k=count))
