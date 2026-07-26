from __future__ import annotations
import datetime
import random
from importlib import resources
from typingapp.engine.content.code_snippets import SNIPPETS
from typingapp.engine.markov import build_chain
from typingapp.engine.gutenberg import search_books, fetch_excerpt
from typingapp.engine.text_sizing import estimate_word_count

WORD_COUNTS = {1: 10, 2: 15, 3: 20, 4: 25, 5: 30, 6: 40, 7: 50, 8: 60, 9: 80, 10: 100}
SUPPORTED_LANGUAGES = {"en", "es", "fr"}
CACHE_REFRESH_THRESHOLD = 5


def _content_filename(base: str, language: str) -> str:
    lang = language if language in SUPPORTED_LANGUAGES else "en"
    return base if lang == "en" else f"{base.split('.')[0]}_{lang}.txt"


def _load_lines(filename: str) -> list[str]:
    pkg = resources.files("typingapp.engine.content")
    return [line for line in (pkg / filename).read_text(encoding="utf-8").splitlines() if line.strip()]


class LessonEngine:
    def __init__(self) -> None:
        self._words_cache: dict[str, list[str]] = {}
        self._sentences_cache: dict[str, list[str]] = {}

    def _words(self, language: str) -> list[str]:
        if language not in self._words_cache:
            self._words_cache[language] = _load_lines(_content_filename("words.txt", language))
        return self._words_cache[language]

    def _sentences(self, language: str) -> list[str]:
        if language not in self._sentences_cache:
            self._sentences_cache[language] = _load_lines(_content_filename("sentences.txt", language))
        return self._sentences_cache[language]

    def get_lesson(
        self,
        content_type: str,
        difficulty: int,
        custom_text: str = "",
        weak_bigrams: list[str] | None = None,
        language: str = "en",
        storage=None,
        recent_wpm: float = 0,
        session_duration: int = 60,
        word_count_override: int = 0,
    ) -> str:
        if content_type == "custom":
            return custom_text
        if content_type == "sentences":
            return random.choice(self._sentences(language))
        if content_type == "code":
            return random.choice(SNIPPETS)
        if content_type == "random_sentences":
            return self._build_random_sentences(language, recent_wpm, session_duration, storage)
        if content_type == "literature":
            return self._build_literature_lesson(language, recent_wpm, session_duration, storage)
        return self._build_word_lesson(difficulty, weak_bigrams or [], language, word_count_override)

    def _build_word_lesson(
        self, difficulty: int, weak_bigrams: list[str], language: str, word_count_override: int = 0
    ) -> str:
        count = word_count_override if word_count_override > 0 else WORD_COUNTS.get(max(1, min(difficulty, 10)), 20)
        pool = self._words(language)
        if weak_bigrams:
            biased = [w for w in pool if any(bg in w for bg in weak_bigrams)]
            if biased:
                n_biased = count // 2
                chosen = random.choices(biased, k=n_biased) + random.choices(pool, k=count - n_biased)
                random.shuffle(chosen)
                return " ".join(chosen)
        return " ".join(random.choices(pool, k=count))

    def _build_random_sentences(self, language: str, recent_wpm: float, session_duration: int, storage) -> str:
        word_count = estimate_word_count(recent_wpm, session_duration)
        corpus = list(self._sentences(language))
        if storage is not None:
            cached = storage.fetch_cached_excerpts(language=language, limit=10)
            corpus.extend(entry["excerpt"] for entry in cached)
        chain = build_chain(corpus)
        result = chain.generate(word_count)
        if not result.strip():
            return self._build_word_lesson(5, [], language)
        return result

    def _build_literature_lesson(self, language: str, recent_wpm: float, session_duration: int, storage) -> str:
        word_count = estimate_word_count(recent_wpm, session_duration)
        min_words, max_words = max(20, word_count // 2), word_count * 2

        if storage is not None:
            cached = storage.fetch_cached_excerpts(language=language, limit=20)
            if len(cached) >= CACHE_REFRESH_THRESHOLD:
                entry = random.choice(cached)
                return entry["excerpt"]

        books = search_books(language=language, limit=20)
        if books:
            book = random.choice(books)
            excerpt = fetch_excerpt(book, min_words=min_words, max_words=max_words)
            if excerpt:
                if storage is not None:
                    storage.cache_excerpt(
                        gutenberg_id=book.gutenberg_id, title=book.title, author=book.author,
                        language=language, excerpt=excerpt,
                        fetched_at=datetime.datetime.now().isoformat(),
                    )
                    storage.prune_old_excerpts(language=language, keep=20)
                return excerpt

        if storage is not None:
            cached = storage.fetch_cached_excerpts(language=language, limit=20)
            if cached:
                return random.choice(cached)["excerpt"]

        return self._build_random_sentences(language, recent_wpm, session_duration, storage)
