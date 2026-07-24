# Literature Text, Contextual Random Words & Rich Landscape UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Project Gutenberg literature-mode lessons, Markov-chain contextual random-sentence generation, English/Spanish/French language selection, and a wide-terminal-first UI overhaul (Settings row width, Lesson auto-scroll, Results card layout with arrow-key navigation).

**Architecture:** New pure-Python engine modules (`gutenberg.py`, `markov.py`, `text_sizing.py`) with zero Textual dependency, following the existing `typingapp/engine/` pattern. Storage gains a bounded excerpt cache table. Config gains a `language` field and two new `content_type` values. Screens (`lesson.py`, `settings.py`, `results.py`) are updated last, once the engine layer is fully tested in isolation.

**Tech Stack:** Python 3.10+, Textual (existing), stdlib `urllib.request`/`json` for Gutendex/Gutenberg HTTP calls (no new dependency), stdlib `sqlite3` (existing), pytest (existing).

## Global Constraints

- No new third-party dependencies — network calls use stdlib `urllib.request`.
- All Gutenberg/Gutendex network calls use a short timeout (3 seconds) and never raise into caller code — every failure path returns `None`/`[]` and the caller falls back to local content.
- Gutenberg excerpts are cached only as bounded slices (a few hundred words), never full book texts, tagged with `gutenberg_id`/`title`/`author` for attribution.
- Spanish and French word lists and sample sentences are original content written for this app — not copied from any external source.
- Existing DB tables (`sessions`, `keystrokes`, `gamification`, `badges`) are unchanged; only a new `gutenberg_cache` table is added.
- Follow existing code conventions: `from __future__ import annotations` at the top of every module, dataclasses for records, per-module `tests/test_<module>.py` files, English inline comments only where the *why* is non-obvious.

---

## Task 1: Text sizing — WPM/duration → word count

**Files:**
- Create: `typingapp/engine/text_sizing.py`
- Test: `tests/test_text_sizing.py`

**Interfaces:**
- Consumes: nothing (pure function, no dependency on other new modules).
- Produces: `estimate_word_count(recent_wpm: float, session_duration_seconds: int, slack_factor: float = 1.3) -> int` — used by Task 4 (`LessonEngine`) and Task 8 (`LessonScreen`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_text_sizing.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_text_sizing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'typingapp.engine.text_sizing'`

- [ ] **Step 3: Write minimal implementation**

```python
# typingapp/engine/text_sizing.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_text_sizing.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/text_sizing.py tests/test_text_sizing.py
git commit -m "feat: add WPM/duration-based text length estimation"
```

---

## Task 2: Scorer.extend() — mid-session text extension

**Files:**
- Modify: `typingapp/engine/scorer.py`
- Test: `tests/test_scorer.py`

**Interfaces:**
- Consumes: existing `Scorer` dataclass (`target: str`, `position: int`, `is_complete` property).
- Produces: `Scorer.extend(more_text: str) -> None` — used by Task 8 (`LessonScreen` mid-session extension).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scorer.py`:

```python
def test_extend_appends_to_target_without_resetting_position():
    s = Scorer("ab", strict_mode=False)
    s.start()
    s.process_key("a")
    s.process_key("b")
    assert s.is_complete
    s.extend(" cd")
    assert s.target == "ab cd"
    assert s.position == 2
    assert not s.is_complete


def test_extend_preserves_stats():
    s = Scorer("ab", strict_mode=False)
    s.start()
    s.process_key("a")
    s.process_key("x")  # one error
    s.extend(" cd")
    assert s.error_count == 1
    assert len(s.keystrokes) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scorer.py -v -k extend`
Expected: FAIL with `AttributeError: 'Scorer' object has no attribute 'extend'`

- [ ] **Step 3: Write minimal implementation**

In `typingapp/engine/scorer.py`, add a method after `top_mistaken_words` (end of class, currently ending at line 78):

```python
    def extend(self, more_text: str) -> None:
        self.target += more_text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scorer.py -v -k extend`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full scorer suite to confirm no regressions**

Run: `pytest tests/test_scorer.py -v`
Expected: PASS (all tests, including the 13 pre-existing ones)

- [ ] **Step 6: Commit**

```bash
git add typingapp/engine/scorer.py tests/test_scorer.py
git commit -m "feat: add Scorer.extend() for mid-session text extension"
```

---

## Task 3: Markov chain contextual sentence generator

**Files:**
- Create: `typingapp/engine/markov.py`
- Test: `tests/test_markov.py`

**Interfaces:**
- Consumes: `list[str]` of training sentences (plain strings, no dependency on other new modules — Task 5's Gutenberg excerpts and existing `sentences.txt` content are both just `list[str]`/`str` at the call site).
- Produces: `build_chain(corpus_sentences: list[str], order: int = 2) -> MarkovChain`, `MarkovChain.generate(word_count: int) -> str`. Used by Task 4 (`LessonEngine`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_markov.py
import random
import pytest
from typingapp.engine.markov import build_chain, MarkovChain


CORPUS = [
    "the quick brown fox jumps over the lazy dog",
    "the lazy dog sleeps in the warm sun",
    "a quick fox runs through the green forest",
    "the brown dog and the quick fox are friends",
]


def test_build_chain_returns_markov_chain():
    chain = build_chain(CORPUS)
    assert isinstance(chain, MarkovChain)


def test_generate_respects_approximate_word_count():
    random.seed(42)
    chain = build_chain(CORPUS)
    result = chain.generate(word_count=10)
    words = result.split()
    # allow some slack since generation rounds out to sentence end
    assert 5 <= len(words) <= 20


def test_generate_produces_nonempty_text():
    random.seed(1)
    chain = build_chain(CORPUS)
    result = chain.generate(word_count=8)
    assert len(result.strip()) > 0


def test_generate_words_come_from_corpus_vocabulary():
    random.seed(7)
    chain = build_chain(CORPUS)
    result = chain.generate(word_count=12)
    corpus_vocab = set(" ".join(CORPUS).lower().split())
    for word in result.lower().split():
        assert word.strip(".,!?") in corpus_vocab


def test_empty_corpus_raises_no_exception_and_returns_empty():
    chain = build_chain([])
    result = chain.generate(word_count=10)
    assert result == ""


def test_tiny_corpus_still_generates():
    chain = build_chain(["hello world"])
    result = chain.generate(word_count=5)
    assert len(result) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_markov.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'typingapp.engine.markov'`

- [ ] **Step 3: Write minimal implementation**

```python
# typingapp/engine/markov.py
from __future__ import annotations
import random
from collections import defaultdict

SENTENCE_END_CHARS = ".!?"


class MarkovChain:
    def __init__(self, transitions: dict[tuple[str, ...], list[str]], order: int) -> None:
        self._transitions = transitions
        self._order = order
        self._starts = list(transitions.keys())

    def generate(self, word_count: int) -> str:
        if not self._starts:
            return ""
        state = random.choice(self._starts)
        words = list(state)
        while len(words) < word_count:
            next_words = self._transitions.get(state)
            if not next_words:
                state = random.choice(self._starts)
                words.extend(state)
                continue
            next_word = random.choice(next_words)
            words.append(next_word)
            state = tuple(words[-self._order:])
            if len(words) >= word_count and next_word[-1:] in SENTENCE_END_CHARS:
                break
        return " ".join(words)


def build_chain(corpus_sentences: list[str], order: int = 2) -> MarkovChain:
    transitions: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for sentence in corpus_sentences:
        words = sentence.split()
        if len(words) <= order:
            continue
        for i in range(len(words) - order):
            state = tuple(words[i:i + order])
            next_word = words[i + order]
            transitions[state].append(next_word)
    return MarkovChain(dict(transitions), order)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_markov.py -v`
Expected: PASS (6 tests)

Note: `test_generate_words_come_from_corpus_vocabulary` may need the corpus words lowercase-compared since `MarkovChain` doesn't lowercase internally — the test already handles this via `.lower()` on both sides.

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/markov.py tests/test_markov.py
git commit -m "feat: add Markov chain contextual sentence generator"
```

---

## Task 4: Gutenberg cache table in Storage

**Files:**
- Modify: `typingapp/data/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: nothing new (extends existing `Storage` class).
- Produces: `GutenbergExcerpt` dataclass, `Storage.cache_excerpt(gutenberg_id: int, title: str, author: str, language: str, excerpt: str, fetched_at: str) -> int`, `Storage.fetch_cached_excerpts(language: str, limit: int = 20) -> list[dict]`, `Storage.prune_old_excerpts(language: str, keep: int = 20) -> None`. Used by Task 6 (`gutenberg.py` caller / `LessonEngine`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_storage.py`:

```python
def test_cache_excerpt_and_fetch(tmp_path):
    s = Storage(tmp_path / "test.db")
    excerpt_id = s.cache_excerpt(
        gutenberg_id=1342, title="Pride and Prejudice", author="Jane Austen",
        language="en", excerpt="It is a truth universally acknowledged...",
        fetched_at="2026-07-24T10:00:00",
    )
    assert excerpt_id > 0
    cached = s.fetch_cached_excerpts(language="en", limit=10)
    assert len(cached) == 1
    assert cached[0]["title"] == "Pride and Prejudice"
    assert cached[0]["gutenberg_id"] == 1342
    s.close()


def test_fetch_cached_excerpts_filters_by_language(tmp_path):
    s = Storage(tmp_path / "test.db")
    s.cache_excerpt(gutenberg_id=1, title="A", author="X", language="en",
                     excerpt="text", fetched_at="2026-07-24T10:00:00")
    s.cache_excerpt(gutenberg_id=2, title="B", author="Y", language="es",
                     excerpt="texto", fetched_at="2026-07-24T10:00:00")
    en_only = s.fetch_cached_excerpts(language="en", limit=10)
    assert len(en_only) == 1
    assert en_only[0]["title"] == "A"
    s.close()


def test_prune_old_excerpts_keeps_only_n_most_recent(tmp_path):
    s = Storage(tmp_path / "test.db")
    for i in range(5):
        s.cache_excerpt(
            gutenberg_id=i, title=f"Book{i}", author="X", language="en",
            excerpt="text", fetched_at=f"2026-07-{i+1:02d}T10:00:00",
        )
    s.prune_old_excerpts(language="en", keep=2)
    remaining = s.fetch_cached_excerpts(language="en", limit=10)
    assert len(remaining) == 2
    # keeps the most recently fetched
    titles = {r["title"] for r in remaining}
    assert titles == {"Book3", "Book4"}
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py -v -k excerpt`
Expected: FAIL with `AttributeError: 'Storage' object has no attribute 'cache_excerpt'`

- [ ] **Step 3: Write minimal implementation**

In `typingapp/data/storage.py`, add after `CREATE_KEYSTROKES` (currently ending at line 31):

```python
CREATE_GUTENBERG_CACHE = """
CREATE TABLE IF NOT EXISTS gutenberg_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gutenberg_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    language TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    fetched_at TEXT NOT NULL
)"""
```

Add a matching dataclass after `KeystrokeRecord` (currently ending at line 52):

```python
@dataclass
class GutenbergExcerpt:
    gutenberg_id: int
    title: str
    author: str
    language: str
    excerpt: str
    fetched_at: str
```

In `Storage.__init__`, add the table creation next to the existing two (currently lines 61-62):

```python
        self._conn.execute(CREATE_SESSIONS)
        self._conn.execute(CREATE_KEYSTROKES)
        self._conn.execute(CREATE_GUTENBERG_CACHE)
        self._conn.commit()
```

Add methods after `fetch_summary` (currently ending at line 110, before `close`):

```python
    def cache_excerpt(
        self, gutenberg_id: int, title: str, author: str, language: str,
        excerpt: str, fetched_at: str,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO gutenberg_cache (gutenberg_id, title, author, language, excerpt, fetched_at) "
            "VALUES (?,?,?,?,?,?)",
            (gutenberg_id, title, author, language, excerpt, fetched_at),
        )
        self._conn.commit()
        return cur.lastrowid

    def fetch_cached_excerpts(self, language: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM gutenberg_cache WHERE language=? ORDER BY fetched_at DESC LIMIT ?",
            (language, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def prune_old_excerpts(self, language: str, keep: int = 20) -> None:
        self._conn.execute(
            "DELETE FROM gutenberg_cache WHERE language=? AND id NOT IN ("
            "  SELECT id FROM gutenberg_cache WHERE language=? "
            "  ORDER BY fetched_at DESC LIMIT ?"
            ")",
            (language, language, keep),
        )
        self._conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py -v`
Expected: PASS (all tests, including the 4 pre-existing ones and 3 new ones)

- [ ] **Step 5: Commit**

```bash
git add typingapp/data/storage.py tests/test_storage.py
git commit -m "feat: add gutenberg_cache table for bounded excerpt caching"
```

---

## Task 5: Gutenberg client (search + fetch)

**Files:**
- Create: `typingapp/engine/gutenberg.py`
- Test: `tests/test_gutenberg.py`

**Interfaces:**
- Consumes: nothing from other new modules (uses stdlib `urllib.request`/`json`/`re`/`random` only).
- Produces: `BookMeta` dataclass (`gutenberg_id: int`, `title: str`, `author: str`, `text_url: str`), `search_books(language: str, limit: int = 20) -> list[BookMeta]`, `fetch_excerpt(book: BookMeta, min_words: int, max_words: int) -> str | None`. Used by Task 6 (`LessonEngine` literature mode).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gutenberg.py
from unittest.mock import patch, MagicMock
import json
import urllib.error
from typingapp.engine.gutenberg import search_books, fetch_excerpt, BookMeta


SAMPLE_GUTENDEX_RESPONSE = json.dumps({
    "results": [
        {
            "id": 1342,
            "title": "Pride and Prejudice",
            "authors": [{"name": "Austen, Jane"}],
            "formats": {"text/plain; charset=utf-8": "https://example.org/1342.txt"},
        },
        {
            "id": 84,
            "title": "Frankenstein",
            "authors": [{"name": "Shelley, Mary"}],
            "formats": {"text/plain": "https://example.org/84.txt"},
        },
    ]
}).encode("utf-8")

SAMPLE_BOOK_TEXT = (
    "The Project Gutenberg eBook of Sample Book\n"
    "*** START OF THE PROJECT GUTENBERG EBOOK SAMPLE ***\n"
    + " ".join(f"word{i}" for i in range(500)) +
    "\n*** END OF THE PROJECT GUTENBERG EBOOK SAMPLE ***\n"
    "More boilerplate after the end marker."
).encode("utf-8")


def _mock_urlopen_returning(payload_bytes):
    mock_response = MagicMock()
    mock_response.read.return_value = payload_bytes
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    return mock_response


def test_search_books_parses_gutendex_response():
    with patch("typingapp.engine.gutenberg.urlopen", return_value=_mock_urlopen_returning(SAMPLE_GUTENDEX_RESPONSE)):
        books = search_books(language="en", limit=20)
    assert len(books) == 2
    assert books[0] == BookMeta(
        gutenberg_id=1342, title="Pride and Prejudice", author="Austen, Jane",
        text_url="https://example.org/1342.txt",
    )


def test_search_books_returns_empty_on_timeout():
    with patch("typingapp.engine.gutenberg.urlopen", side_effect=TimeoutError):
        books = search_books(language="en", limit=20)
    assert books == []


def test_search_books_returns_empty_on_malformed_json():
    with patch("typingapp.engine.gutenberg.urlopen", return_value=_mock_urlopen_returning(b"not json")):
        books = search_books(language="en", limit=20)
    assert books == []


def test_search_books_skips_entries_without_plain_text_format():
    payload = json.dumps({"results": [
        {"id": 1, "title": "No Text", "authors": [{"name": "Nobody"}], "formats": {"application/epub": "x"}},
    ]}).encode("utf-8")
    with patch("typingapp.engine.gutenberg.urlopen", return_value=_mock_urlopen_returning(payload)):
        books = search_books(language="en", limit=20)
    assert books == []


def test_fetch_excerpt_strips_boilerplate_and_returns_slice():
    book = BookMeta(gutenberg_id=1, title="Sample", author="Someone", text_url="https://example.org/1.txt")
    with patch("typingapp.engine.gutenberg.urlopen", return_value=_mock_urlopen_returning(SAMPLE_BOOK_TEXT)):
        excerpt = fetch_excerpt(book, min_words=20, max_words=40)
    assert excerpt is not None
    assert "Project Gutenberg eBook" not in excerpt
    assert "More boilerplate" not in excerpt
    words = excerpt.split()
    assert 20 <= len(words) <= 40


def test_fetch_excerpt_returns_none_on_network_error():
    book = BookMeta(gutenberg_id=1, title="Sample", author="Someone", text_url="https://example.org/1.txt")
    with patch("typingapp.engine.gutenberg.urlopen", side_effect=urllib.error.URLError("no connection")):
        excerpt = fetch_excerpt(book, min_words=20, max_words=40)
    assert excerpt is None


def test_fetch_excerpt_returns_none_when_body_too_short():
    book = BookMeta(gutenberg_id=1, title="Sample", author="Someone", text_url="https://example.org/1.txt")
    short_text = b"*** START OF THE PROJECT GUTENBERG EBOOK ***\ntoo short\n*** END OF THE PROJECT GUTENBERG EBOOK ***"
    with patch("typingapp.engine.gutenberg.urlopen", return_value=_mock_urlopen_returning(short_text)):
        excerpt = fetch_excerpt(book, min_words=500, max_words=1000)
    assert excerpt is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gutenberg.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'typingapp.engine.gutenberg'`

- [ ] **Step 3: Write minimal implementation**

```python
# typingapp/engine/gutenberg.py
from __future__ import annotations
import json
import random
import re
from dataclasses import dataclass
from urllib.request import urlopen
from urllib.error import URLError

GUTENDEX_URL = "https://gutendex.com/books"
TIMEOUT_SECONDS = 3
START_MARKER_RE = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE)
END_MARKER_RE = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE)


@dataclass(frozen=True)
class BookMeta:
    gutenberg_id: int
    title: str
    author: str
    text_url: str


def search_books(language: str, limit: int = 20) -> list[BookMeta]:
    url = f"{GUTENDEX_URL}?languages={language}&mime_type=text/plain"
    try:
        with urlopen(url, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError, OSError):
        return []

    books: list[BookMeta] = []
    for entry in payload.get("results", [])[:limit]:
        text_url = _find_plain_text_url(entry.get("formats", {}))
        if not text_url:
            continue
        authors = entry.get("authors") or [{"name": "Unknown"}]
        books.append(BookMeta(
            gutenberg_id=entry["id"],
            title=entry.get("title", "Untitled"),
            author=authors[0].get("name", "Unknown"),
            text_url=text_url,
        ))
    return books


def _find_plain_text_url(formats: dict) -> str | None:
    for mime, url in formats.items():
        if mime.startswith("text/plain"):
            return url
    return None


def fetch_excerpt(book: BookMeta, min_words: int, max_words: int) -> str | None:
    try:
        with urlopen(book.text_url, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except (URLError, TimeoutError, OSError):
        return None

    body = _strip_boilerplate(raw)
    words = body.split()
    if len(words) < min_words:
        return None

    slice_len = min(max_words, len(words))
    max_start = len(words) - slice_len
    start = random.randint(0, max_start) if max_start > 0 else 0
    return " ".join(words[start:start + slice_len])


def _strip_boilerplate(raw: str) -> str:
    start_match = START_MARKER_RE.search(raw)
    end_match = END_MARKER_RE.search(raw)
    start = start_match.end() if start_match else 0
    end = end_match.start() if end_match else len(raw)
    return raw[start:end].strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_gutenberg.py -v`
Expected: PASS (7 tests). No real network calls are made — all `urlopen` calls are mocked.

- [ ] **Step 5: Commit**

```bash
git add typingapp/engine/gutenberg.py tests/test_gutenberg.py
git commit -m "feat: add Gutendex/Gutenberg client for public-domain excerpt fetching"
```

---

## Task 6: Language-aware content files (Spanish, French)

**Files:**
- Create: `typingapp/engine/content/words_es.txt`
- Create: `typingapp/engine/content/sentences_es.txt`
- Create: `typingapp/engine/content/words_fr.txt`
- Create: `typingapp/engine/content/sentences_fr.txt`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing (static data files).
- Produces: files loadable via `importlib.resources` the same way `words.txt`/`sentences.txt` already are. Used by Task 7 (`LessonEngine` language parameter).

- [ ] **Step 1: Write the Spanish word list**

Create `typingapp/engine/content/words_es.txt` — 150 common Spanish words, one per line, no header:

```
el
la
de
que
y
en
un
ser
se
no
haber
por
con
su
para
como
estar
tener
le
lo
lo
todo
pero
mas
hacer
o
poder
decir
este
ir
otro
ese
si
yo
ver
haber
por
para
con
como
todo
esta
uno
al
donde
quien
desde
todos
durante
tiempo
manera
mismo
mientras
casa
vida
mundo
mano
ojo
dia
nada
mujer
hombre
gran
grande
nuevo
mejor
alto
tanto
mismo
propio
distinto
libre
posible
cierto
diferente
pequeno
largo
verdad
agua
tierra
fuego
aire
luz
noche
sol
luna
cielo
mar
rio
monte
campo
ciudad
pueblo
calle
puerta
ventana
mesa
silla
libro
papel
palabra
nombre
numero
tiempo
momento
lugar
punto
forma
parte
grupo
persona
gente
nino
familia
amigo
trabajo
escuela
empresa
gobierno
pais
estado
historia
arte
musica
comida
agua
salud
amor
paz
guerra
verdad
razon
idea
pregunta
respuesta
problema
solucion
cambio
proceso
sistema
metodo
resultado
efecto
causa
razon
motivo
fin
inicio
final
principio
```

- [ ] **Step 2: Write the Spanish sentence list**

Create `typingapp/engine/content/sentences_es.txt` — 15 original simple sentences, one per line:

```
El sol brilla sobre las montanas cada manana.
Mi hermana prepara cafe antes de salir a trabajar.
Los ninos juegan en el parque despues de la escuela.
Un buen libro puede cambiar la forma en que piensas.
La ciudad se llena de luces cuando cae la noche.
Caminar por la playa siempre me hace sentir tranquilo.
El agua del rio corre clara entre las piedras.
Mis amigos y yo cocinamos juntos los fines de semana.
La musica suave ayuda a concentrarse mientras estudio.
El viejo puente conecta los dos lados del pueblo.
Aprender un idioma nuevo requiere paciencia y practica.
El jardin florece con colores brillantes en primavera.
Un cafe caliente es perfecto para las mananas frias.
La biblioteca del pueblo tiene miles de libros antiguos.
Mi abuelo cuenta historias interesantes sobre su juventud.
```

- [ ] **Step 3: Write the French word list**

Create `typingapp/engine/content/words_fr.txt` — 150 common French words, one per line, no header:

```
le
de
un
etre
et
a
il
avoir
ne
je
son
que
se
qui
ce
dans
en
du
elle
au
de
ce
le
pour
sont
avec
son
sur
se
pas
plus
pouvoir
par
je
avec
tout
faire
son
mettre
autre
on
mais
nous
comme
ou
si
leur
y
dire
elle
devoir
avant
deux
meme
prendre
aussi
celui
donner
bien
encore
nouveau
aller
cela
entre
premier
vouloir
deja
grand
homme
temps
tres
savoir
falloir
voir
en
bien
ou
sans
tenir
petit
la
maison
jour
vie
monde
main
oeil
nuit
soleil
lune
ciel
mer
riviere
montagne
champ
ville
village
rue
porte
fenetre
table
chaise
livre
papier
mot
nom
nombre
moment
endroit
point
forme
partie
groupe
personne
gens
enfant
famille
ami
travail
ecole
entreprise
gouvernement
pays
etat
histoire
art
musique
nourriture
eau
sante
amour
paix
guerre
verite
raison
idee
question
reponse
probleme
solution
changement
processus
systeme
methode
resultat
effet
cause
motif
fin
debut
final
principe
lumiere
espoir
force
courage
liberte
justice
beaute
```

- [ ] **Step 4: Write the French sentence list**

Create `typingapp/engine/content/sentences_fr.txt` — 15 original simple sentences, one per line:

```
Le soleil brille sur les montagnes chaque matin.
Ma soeur prepare du cafe avant d'aller travailler.
Les enfants jouent dans le parc apres l'ecole.
Un bon livre peut changer ta facon de penser.
La ville se remplit de lumieres quand la nuit tombe.
Marcher sur la plage me rend toujours calme.
L'eau de la riviere coule claire entre les pierres.
Mes amis et moi cuisinons ensemble le week-end.
La musique douce aide a se concentrer pendant l'etude.
Le vieux pont relie les deux cotes du village.
Apprendre une nouvelle langue demande patience et pratique.
Le jardin fleurit avec des couleurs vives au printemps.
Un cafe chaud est parfait pour les matins froids.
La bibliotheque du village possede des milliers de vieux livres.
Mon grand-pere raconte des histoires interessantes sur sa jeunesse.
```

- [ ] **Step 5: Register the new files as package data**

Read `pyproject.toml` — the existing `[tool.setuptools.package-data]` section (line 18-19) already uses a glob:

```toml
[tool.setuptools.package-data]
"typingapp.engine.content" = ["*.txt"]
```

This glob already covers the new files — no change needed to `pyproject.toml`. Confirm by running Step 6.

- [ ] **Step 6: Verify the files are readable via importlib.resources**

Run this ad-hoc check (not a permanent test — just confirms packaging picks up the new files):

```bash
python -c "
from importlib import resources
pkg = resources.files('typingapp.engine.content')
for name in ('words_es.txt', 'sentences_es.txt', 'words_fr.txt', 'sentences_fr.txt'):
    text = (pkg / name).read_text(encoding='utf-8')
    lines = [l for l in text.splitlines() if l.strip()]
    print(name, len(lines), 'lines')
"
```

Expected output: four lines showing each file with a non-zero line count (approximately 150 for word files, 15 for sentence files).

- [ ] **Step 7: Commit**

```bash
git add typingapp/engine/content/words_es.txt typingapp/engine/content/sentences_es.txt typingapp/engine/content/words_fr.txt typingapp/engine/content/sentences_fr.txt
git commit -m "feat: add original Spanish and French word/sentence corpora"
```

---

## Task 7: Config — language field and new content_type values

**Files:**
- Modify: `typingapp/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `AppConfig.language: str = "en"` field. Used by Task 8 (`LessonEngine`), Task 9 (Settings screen), Task 5's caller (literature mode language filter).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_default_language_is_english():
    cfg = AppConfig()
    assert cfg.language == "en"


def test_language_roundtrips_through_save_and_load(tmp_path):
    cfg = AppConfig(language="es")
    path = tmp_path / "config.json"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.language == "es"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v -k language`
Expected: FAIL with `TypeError: AppConfig.__init__() got an unexpected keyword argument 'language'`

- [ ] **Step 3: Write minimal implementation**

In `typingapp/config.py`, add the field to `AppConfig` (currently ending at line 17):

```python
    key_sounds: bool = True
    language: str = "en"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (all tests, including 3 pre-existing and 2 new)

- [ ] **Step 5: Commit**

```bash
git add typingapp/config.py tests/test_config.py
git commit -m "feat: add language field to AppConfig"
```

---

## Task 8: LessonEngine — language routing, literature mode, random_sentences mode

**Files:**
- Modify: `typingapp/engine/lesson.py`
- Test: `tests/test_lesson.py`

**Interfaces:**
- Consumes: `estimate_word_count` (Task 1), `build_chain`/`MarkovChain.generate` (Task 3), `search_books`/`fetch_excerpt`/`BookMeta` (Task 5), `Storage.fetch_cached_excerpts`/`cache_excerpt`/`prune_old_excerpts` (Task 4).
- Produces: `LessonEngine.get_lesson(..., language: str = "en", storage=None, recent_wpm: float = 0, session_duration: int = 60)` extended signature; new content types `"random_sentences"` and `"literature"`. Used by Task 10 (`LessonScreen`).

- [ ] **Step 1: Read the current file to confirm exact content before editing**

Run: `cat typingapp/engine/lesson.py` (already read above — current content reproduced here for reference):

```python
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
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_lesson.py` (read the existing file first to match its exact style/fixtures before appending):

```python
def test_load_words_defaults_to_english():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="words", difficulty=3, language="en")
    assert len(lesson) > 0


def test_load_words_spanish():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="words", difficulty=3, language="es")
    assert len(lesson) > 0


def test_load_words_french():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="words", difficulty=3, language="fr")
    assert len(lesson) > 0


def test_unknown_language_falls_back_to_english():
    engine = LessonEngine()
    lesson_unknown = engine.get_lesson(content_type="sentences", difficulty=3, language="de")
    lesson_en = engine.get_lesson(content_type="sentences", difficulty=3, language="en")
    # both draw from the same (English) pool, so unknown doesn't crash or return empty
    assert len(lesson_unknown) > 0


def test_random_sentences_content_type_produces_text():
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="random_sentences", difficulty=3, language="en")
    assert len(lesson.strip()) > 0


def test_literature_content_type_falls_back_when_no_storage_or_network(monkeypatch):
    import typingapp.engine.lesson as lesson_module
    monkeypatch.setattr(lesson_module, "search_books", lambda *a, **k: [])
    engine = LessonEngine()
    lesson = engine.get_lesson(content_type="literature", difficulty=3, language="en", storage=None)
    # falls back to random_sentences/local text, never empty, never raises
    assert len(lesson.strip()) > 0


def test_get_lesson_accepts_recent_wpm_and_session_duration_for_sizing():
    engine = LessonEngine()
    short = engine.get_lesson(content_type="words", difficulty=3, language="en",
                                recent_wpm=20, session_duration=30)
    long_ = engine.get_lesson(content_type="words", difficulty=3, language="en",
                                recent_wpm=20, session_duration=180)
    # word-count content_type still uses WORD_COUNTS by difficulty (unaffected by sizing params);
    # this test only confirms the new kwargs are accepted without raising
    assert isinstance(short, str) and isinstance(long_, str)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_lesson.py -v -k "spanish or french or random_sentences or literature or fallback or sizing"`
Expected: FAIL with `TypeError: LessonEngine.get_lesson() got an unexpected keyword argument 'language'`

- [ ] **Step 4: Write the implementation**

Replace the full content of `typingapp/engine/lesson.py`:

```python
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
        return self._build_word_lesson(difficulty, weak_bigrams or [], language)

    def _build_word_lesson(self, difficulty: int, weak_bigrams: list[str], language: str) -> str:
        count = WORD_COUNTS.get(max(1, min(difficulty, 10)), 20)
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_lesson.py -v`
Expected: PASS (all tests, including pre-existing ones — check the existing file's test count first with `grep -c "^def test_" tests/test_lesson.py` before this task, then confirm the new total after)

- [ ] **Step 6: Commit**

```bash
git add typingapp/engine/lesson.py tests/test_lesson.py
git commit -m "feat: add language routing, literature mode, and random_sentences mode to LessonEngine"
```

---

## Task 9: Settings screen — language selector, new content types, wider rows

**Files:**
- Modify: `typingapp/screens/settings.py`
- Modify: `typingapp/app.tcss`

**Interfaces:**
- Consumes: `AppConfig.language` (Task 7), new `content_type` values `"random_sentences"`/`"literature"` (Task 8, validated only at the UI layer — no schema change).
- Produces: updated Settings screen. No downstream consumers within this plan (terminal UI task).

- [ ] **Step 1: Modify the content-type Select to include the two new options**

In `typingapp/screens/settings.py`, replace the `sel-content` `Select` block (currently lines 28-33):

```python
                yield Select(
                    options=[
                        ("Words", "words"), ("Sentences", "sentences"),
                        ("Random Sentences", "random_sentences"), ("Literature", "literature"),
                        ("Code", "code"), ("Custom", "custom"),
                    ],
                    value=cfg.content_type,
                    id="sel-content",
                )
```

- [ ] **Step 2: Add a Language selector row**

Immediately after the `sel-duration` `Select` block (currently ending at line 40, before the `yield Static("")` on line 41), insert:

```python
            with Horizontal(classes="setting-row"):
                yield Label("Language")
                yield Select(
                    options=[("English", "en"), ("Espanol", "es"), ("Francais", "fr")],
                    value=cfg.language,
                    id="sel-language",
                )
```

- [ ] **Step 3: Persist the language selection on save**

In `on_button_pressed`, after the existing `sel_dur` handling block (currently lines 73-75), add:

```python
            sel_lang = self.query_one("#sel-language", Select)
            if sel_lang.value != Select.BLANK:
                cfg.language = sel_lang.value
```

- [ ] **Step 4: Widen setting rows for landscape terminals**

In `typingapp/app.tcss`, replace the `.setting-row` and `.setting-row Label` rules (currently lines 65-73):

```css
.setting-row {
    height: auto;
    margin: 0 0 1 0;
    align: left middle;
    width: 100%;
}

.setting-row Label {
    width: 2fr;
}

.setting-row Switch,
.setting-row Select {
    width: 1fr;
}
```

This changes the ratio from an unconstrained label to a proportional label:control split, using more of a wide terminal's horizontal space instead of controls hugging the left edge.

- [ ] **Step 5: Verify manually via the Textual test pilot**

Run this ad-hoc verification script (not a permanent test file — Settings/screen-level behavior in this codebase is verified via manual pilot probes, consistent with prior UI work):

```bash
python -c "
import asyncio
from typingapp.app import TypingApp
from typingapp.screens.settings import SettingsScreen
from textual.widgets import Select

async def main():
    app = TypingApp()
    async with app.run_test() as pilot:
        await pilot.press('3')
        await pilot.pause()
        assert isinstance(app.screen, SettingsScreen), f'expected SettingsScreen, got {app.screen}'
        sel_content = app.screen.query_one('#sel-content', Select)
        options = [opt[1] for opt in sel_content._options] if hasattr(sel_content, '_options') else None
        sel_lang = app.screen.query_one('#sel-language', Select)
        print('language selector exists, current value:', sel_lang.value)
        print('OK')

asyncio.run(main())
"
```

Expected output: `language selector exists, current value: en` then `OK`, no exceptions.

- [ ] **Step 6: Commit**

```bash
git add typingapp/screens/settings.py typingapp/app.tcss
git commit -m "feat: add language selector, literature/random_sentences options, wider setting rows"
```

---

## Task 10: LessonScreen — wire language/sizing into lesson loading, dynamic extension, auto-scroll

**Files:**
- Modify: `typingapp/screens/lesson.py`
- Modify: `typingapp/app.tcss`

**Interfaces:**
- Consumes: `LessonEngine.get_lesson(..., language=, storage=, recent_wpm=, session_duration=)` (Task 8), `Scorer.extend()` (Task 2), `storage.fetch_last_n_wpm()` (existing).
- Produces: updated Lesson screen. No downstream consumers within this plan.

- [ ] **Step 1: Wire language and sizing params into `_load_lesson_text`**

In `typingapp/screens/lesson.py`, replace `_load_lesson_text` (currently lines 29-41):

```python
    def _load_lesson_text(self) -> str:
        app = self.app      # type: ignore[attr-defined]
        cfg = app.config
        adaptive: AdaptiveEngine = app.adaptive
        storage = app.storage
        bigrams = storage.fetch_bigram_heatmap(limit=5)
        weak = [b["bigram"] for b in bigrams]
        recent_wpms = storage.fetch_last_n_wpm(n=5)
        recent_wpm = sum(recent_wpms) / len(recent_wpms) if recent_wpms else 0
        return app.lesson_engine.get_lesson(
            content_type=cfg.content_type,
            difficulty=adaptive.current_level,
            custom_text=self._custom_text,
            weak_bigrams=weak,
            language=cfg.language,
            storage=storage,
            recent_wpm=recent_wpm,
            session_duration=cfg.session_duration,
        )
```

- [ ] **Step 2: Add mid-session dynamic extension in `_tick`**

Replace `_tick` (currently lines 70-81):

```python
    def _tick(self) -> None:
        if self._paused or self._scorer is None:
            return
        s = self._scorer
        elapsed = s.elapsed_seconds
        mins, secs = divmod(int(elapsed), 60)
        self.query_one("#wpm-val", Label).update(f"{s.wpm:.0f}")
        self.query_one("#acc-val", Label).update(f"{s.accuracy:.1f}%")
        self.query_one("#time-val", Label).update(f"{mins}:{secs:02d}")
        self.query_one("#err-val", Label).update(str(s.error_count))
        pct = int((s.position / max(len(s.target), 1)) * 100)
        self.query_one("#progress-bar", ProgressBar).update(progress=pct)
        self._maybe_extend_text()

    def _maybe_extend_text(self) -> None:
        app = self.app      # type: ignore[attr-defined]
        s = self._scorer
        if s is None:
            return
        cfg = app.config
        time_remaining = cfg.session_duration - s.elapsed_seconds
        chars_remaining = len(s.target) - s.position
        near_end = chars_remaining <= max(20, len(s.target) * 0.15)
        if near_end and time_remaining > 5 and cfg.content_type in ("literature", "random_sentences"):
            try:
                more_text = app.lesson_engine.get_lesson(
                    content_type=cfg.content_type,
                    difficulty=app.adaptive.current_level,
                    language=cfg.language,
                    storage=app.storage,
                    recent_wpm=s.wpm,
                    session_duration=max(int(time_remaining), 15),
                )
            except Exception:
                more_text = ""
            if more_text:
                s.extend(" " + more_text)
```

- [ ] **Step 3: Add teleprompter auto-scroll to `_render_text`**

Replace the `compose` method's `#text-display` line (currently line 55) to wrap it in a scrollable container. Replace the full `compose` method (currently lines 43-57):

```python
    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="stats-bar"):
                yield Label("⚡ WPM: ", classes="stat-label")
                yield Label("0", id="wpm-val", classes="stat-value wpm-value")
                yield Label("  ✓ ACC: ", classes="stat-label")
                yield Label("100%", id="acc-val", classes="stat-value acc-value")
                yield Label("  ⏱ TIME: ", classes="stat-label")
                yield Label("0:00", id="time-val", classes="stat-value time-value")
                yield Label("  ✗ ERR: ", classes="stat-label")
                yield Label("0", id="err-val", classes="stat-value err-value")
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            with VerticalScroll(id="text-scroll"):
                yield Static("", id="text-display")
            yield Label("", id="hint-bar", classes="hint-bar")
            yield Static("ESC pause  ·  Ctrl+R restart  ·  Ctrl+Q quit  ·  Ctrl+E menu", classes="stat-label")
```

Update the import line (currently line 6):

```python
from textual.containers import Vertical, Horizontal, VerticalScroll
```

Replace `_render_text` (currently lines 83-95):

```python
    def _render_text(self) -> None:
        if self._scorer is None:
            return
        s = self._scorer
        target = s.target
        pos = s.position
        typed = f"[bold green]{target[:pos]}[/]"
        cursor = ""
        rest = ""
        if pos < len(target):
            cursor = f"[bold on red]{target[pos]}[/]"
            rest = f"[dim]{target[pos+1:]}[/]"
        display = self.query_one("#text-display", Static)
        display.update(typed + cursor + rest)
        self._scroll_to_cursor(pos, len(target))

    def _scroll_to_cursor(self, position: int, target_length: int) -> None:
        if target_length == 0:
            return
        scroll_container = self.query_one("#text-scroll", VerticalScroll)
        display = self.query_one("#text-display", Static)
        content_height = display.get_content_height(self.size, self.size.height, None) if hasattr(display, "get_content_height") else display.size.height
        if content_height <= 0:
            return
        progress_ratio = position / target_length
        target_scroll_y = max(0, int(content_height * progress_ratio) - int(scroll_container.size.height / 3))
        scroll_container.scroll_to(y=target_scroll_y, animate=False)
```

- [ ] **Step 4: Add CSS for the scroll container**

In `typingapp/app.tcss`, replace the `#text-display` rule (currently lines 80-86):

```css
#text-scroll {
    border: tall #333333;
    padding: 1 2;
    margin: 1 0;
    height: 1fr;
    max-height: 60%;
}

#text-display {
    height: auto;
}
```

- [ ] **Step 5: Verify manually via the Textual test pilot**

Run this ad-hoc verification (mirrors the probe style used to verify sound/results in prior work on this project):

```bash
python -c "
import asyncio
from typingapp.app import TypingApp
from typingapp.screens.lesson import LessonScreen

async def main():
    app = TypingApp()
    app.config.strict_mode = False
    app.config.content_type = 'words'
    async with app.run_test() as pilot:
        await pilot.press('1')
        await pilot.pause()
        assert isinstance(app.screen, LessonScreen)
        screen = app.screen
        target = screen._scorer.target
        print('lesson loaded, target len:', len(target))
        for ch in target[:10]:
            await pilot.press(ch)
        await pilot.pause()
        print('position after 10 keys:', screen._scorer.position)
        print('OK — no exceptions during render/scroll')

asyncio.run(main())
"
```

Expected output: lesson loads, position advances to 10, no exceptions. (Full literature-mode + extension behavior requires network access — verify that path separately in Task 12's end-to-end check.)

- [ ] **Step 6: Commit**

```bash
git add typingapp/screens/lesson.py typingapp/app.tcss
git commit -m "feat: wire language/sizing into LessonScreen, add mid-session extension and auto-scroll"
```

---

## Task 11: Results screen — card layout, color-coded accuracy, arrow-key navigation

**Files:**
- Modify: `typingapp/screens/results.py`
- Modify: `typingapp/app.tcss`

**Interfaces:**
- Consumes: existing `Scorer`, `horizontal_bar`/`ranked_bars` from `typingapp/engine/charts.py` (already exists from a prior round).
- Produces: updated Results screen. No downstream consumers within this plan.

- [ ] **Step 1: Add a color-coded accuracy helper**

In `typingapp/screens/results.py`, add a module-level function after the imports (currently after line 8):

```python
def _accuracy_color(accuracy: float) -> str:
    if accuracy < 80:
        return "red"
    if accuracy < 95:
        return "yellow"
    return "green"
```

- [ ] **Step 2: Restructure compose() into a horizontal card layout**

Replace the full `compose` method (currently lines 24-77):

```python
    def compose(self) -> ComposeResult:
        s = self._scorer
        session_bigrams = self._session_mistake_bigrams()
        mistaken_words = s.top_mistaken_words(limit=5)

        hint_parts = ["P performance"]
        if session_bigrams:
            hint_parts.append("B bigrams")
        if mistaken_words:
            hint_parts.append("W words")
        section_hint = "Jump to: " + "  ·  ".join(hint_parts) + "  ·  ←→ switch card  ·  ↑↓ scroll"

        with ScrollableContainer():
            yield Static("🏁  Session Complete", classes="menu-title")
            yield Static("Here's how this session went and where to focus next.", classes="section-desc")
            yield Static(section_hint, classes="nav-hint")
            yield Static("")

            with Horizontal(id="results-cards"):
                with VerticalScroll(id="section-performance", classes="result-card", can_focus=True):
                    yield Static("PERFORMANCE", classes="section-title")
                    yield Static("Your speed and accuracy for this lesson.", classes="section-desc")
                    cfg = self.app.config       # type: ignore[attr-defined]
                    yield Label(f"⚡ WPM: {s.wpm:.0f}", classes="stat-value wpm-value")
                    yield Static(
                        horizontal_bar("Accuracy", s.accuracy, 100, value_fmt="{:.1f}%",
                                       color=_accuracy_color(s.accuracy)),
                        classes="stat-value acc-value",
                    )
                    yield Static(
                        horizontal_bar("Time", s.elapsed_seconds, cfg.session_duration,
                                       value_fmt=lambda v: f"{int(v) // 60}:{int(v) % 60:02d}", color="cyan"),
                        classes="stat-value time-value",
                    )
                    max_errors = max(s.error_count, len(s.target) // 5, 1)
                    yield Static(
                        horizontal_bar("Errors", s.error_count, max_errors, value_fmt="{:.0f}", color="magenta"),
                        classes="stat-value err-value",
                    )

                if session_bigrams:
                    with VerticalScroll(id="section-bigrams", classes="result-card", can_focus=True):
                        yield Static("MISTAKE BIGRAMS", classes="section-title")
                        yield Static("Two-letter combinations you mistyped most in this session.", classes="section-desc")
                        yield Static(ranked_bars(session_bigrams), id="bigram-chart")

                if mistaken_words:
                    with VerticalScroll(id="section-words", classes="result-card", can_focus=True):
                        yield Static("MISTAKEN WORDS", classes="section-title")
                        yield Static("The words that caused the most keystroke errors this session.", classes="section-desc")
                        yield Static(ranked_bars(mistaken_words), id="word-chart")

            yield Static("")
            yield Button("▶  Retry Same", id="btn-retry", variant="primary")
            yield Button("🔀  New Lesson", id="btn-new")
            yield Button("📊  View History", id="btn-history")
            yield Button("🏠  Menu", id="btn-menu")
```

- [ ] **Step 3: Update imports for the new containers**

Replace the import line (currently line 5):

```python
from textual.containers import ScrollableContainer, Horizontal, VerticalScroll
```

- [ ] **Step 4: Add arrow-key card navigation actions**

Replace the `_jump_to` method and everything after it (currently lines 112-117) with an extended version that adds card-list tracking and arrow-key focus movement:

```python
    def _jump_to(self, selector: str) -> None:
        try:
            target = self.query_one(selector)
        except Exception:
            return
        target.focus()

    def _card_ids(self) -> list[str]:
        return [card.id for card in self.query(".result-card") if card.id]

    def action_focus_next_card(self) -> None:
        self._shift_card_focus(1)

    def action_focus_previous_card(self) -> None:
        self._shift_card_focus(-1)

    def _shift_card_focus(self, direction: int) -> None:
        card_ids = self._card_ids()
        if not card_ids:
            return
        focused = self.focused
        current_id = focused.id if focused and focused.id in card_ids else None
        if current_id is None:
            next_id = card_ids[0]
        else:
            idx = card_ids.index(current_id)
            next_id = card_ids[(idx + direction) % len(card_ids)]
        self.query_one(f"#{next_id}").focus()
```

- [ ] **Step 5: Register the arrow-key bindings**

Replace the `BINDINGS` list (currently lines 12-17):

```python
    BINDINGS = [
        ("escape", "go_menu", "Menu"),
        ("p", "jump_performance", "Performance"),
        ("b", "jump_bigrams", "Bigrams"),
        ("w", "jump_words", "Words"),
        ("right", "focus_next_card", "Next Card"),
        ("left", "focus_previous_card", "Previous Card"),
    ]
```

Note: `action_jump_performance`/`action_jump_bigrams`/`action_jump_words` (currently lines 103-110) are unchanged — `_jump_to` now calls `.focus()` instead of `.scroll_visible()`, which both moves focus (enabling Up/Down scroll-within-card via the `VerticalScroll` card itself receiving key events) and scrolls it into view as a side effect of focusing.

- [ ] **Step 6: Add CSS for the card layout**

In `typingapp/app.tcss`, add after the existing `.section-desc` rule (currently ending at line 45):

```css
#results-cards {
    height: auto;
    max-height: 20;
}

.result-card {
    width: 1fr;
    height: 20;
    border: round #333333;
    padding: 1 2;
    margin: 0 1 0 0;
}

.result-card:focus {
    border: round #43b0f1;
}
```

- [ ] **Step 7: Verify manually via the Textual test pilot**

Run this ad-hoc verification (extends the probe pattern used for the P/B/W shortcuts in prior work):

```bash
python -c "
import asyncio
from typingapp.app import TypingApp
from typingapp.screens.results import ResultsScreen

async def main():
    app = TypingApp()
    app.config.strict_mode = False
    async with app.run_test() as pilot:
        await pilot.press('1')
        await pilot.pause()
        lesson_screen = app.screen
        target = lesson_screen._scorer.target
        for i, ch in enumerate(target):
            if ch.isalpha() and i in (2, 10):
                await pilot.press('x' if ch != 'x' else 'z')
            else:
                await pilot.press(ch)
        await pilot.pause()
        results = app.screen
        assert isinstance(results, ResultsScreen), f'expected ResultsScreen, got {results}'
        card_ids = results._card_ids()
        print('cards found:', card_ids)
        await pilot.press('right')
        await pilot.pause()
        print('focused after right:', results.focused.id if results.focused else None)
        await pilot.press('left')
        await pilot.pause()
        print('focused after left:', results.focused.id if results.focused else None)
        print('OK')

asyncio.run(main())
"
```

Expected output: `cards found: [...]` with at least `section-performance` present, focus IDs printed for right/left presses, `OK`, no exceptions.

- [ ] **Step 8: Commit**

```bash
git add typingapp/screens/results.py typingapp/app.tcss
git commit -m "feat: restructure Results screen into card layout with arrow-key navigation"
```

---

## Task 12: Full regression pass and CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing (documentation task, terminal in this plan).

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: PASS — all tests across every module (existing + all new tests added in Tasks 1-9). If any test fails, stop and fix before proceeding; do not skip.

- [ ] **Step 2: Manually verify the literature-mode network path end-to-end (requires internet access)**

Run this ad-hoc verification — this is the one path prior tasks' mocked tests can't cover, since it needs real network access to gutendex.com and a Gutenberg mirror:

```bash
python -c "
from typingapp.engine.gutenberg import search_books, fetch_excerpt
books = search_books(language='en', limit=5)
print('found books:', [(b.gutenberg_id, b.title) for b in books])
if books:
    excerpt = fetch_excerpt(books[0], min_words=50, max_words=150)
    print('excerpt length (words):', len(excerpt.split()) if excerpt else None)
    print('excerpt preview:', (excerpt[:100] + '...') if excerpt else None)
else:
    print('no books found — check network connectivity')
"
```

Expected: a non-empty book list and a successfully fetched excerpt of roughly 50-150 words. If this fails due to no network access in the current environment, note it explicitly rather than silently treating literature mode as verified — the mocked unit tests in Task 5 cover correctness of the parsing/boilerplate-stripping logic, but not actual reachability of gutendex.com.

- [ ] **Step 3: Update CLAUDE.md**

Read the current `CLAUDE.md` and add to the "Architecture" bullet list (the `typingapp/engine/` bullet) and "Key Invariants" section. Add a new bullet after the existing `engine/` description line:

```markdown
- `typingapp/engine/gutenberg.py` — Gutendex search + Gutenberg plain-text fetch for literature-mode lessons. All network calls use a 3s timeout and never raise — callers always get `[]`/`None` on failure and fall back to local content. Excerpts are cached in the `gutenberg_cache` DB table as bounded slices (not full books).
- `typingapp/engine/markov.py` — n-gram Markov chain for `random_sentences` content type; trained at lesson-build time from local sentence corpus + cached Gutenberg excerpts.
- `typingapp/engine/text_sizing.py` — `estimate_word_count(recent_wpm, session_duration_seconds)` sizes literature/random-sentence lesson text to the user's recent typing speed.
```

Add to "Key Invariants":

```markdown
- Literature mode (`content_type="literature"`) and random-sentences mode (`content_type="random_sentences"`) size their text via `estimate_word_count` and extend live mid-session (`Scorer.extend()`) if the user finishes with time remaining — see `LessonScreen._maybe_extend_text`. Both fall back silently to local corpus content on any network failure; there is no user-facing error path for this.
- `AppConfig.language` (`"en"`/`"es"`/`"fr"`) selects which `words_<lang>.txt`/`sentences_<lang>.txt` corpus `LessonEngine` loads; unknown/missing languages fall back to English rather than raising.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document literature mode, Markov generation, and language selection in CLAUDE.md"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Task 1 (sizing) → spec §1 dynamic length calc. Task 2 (Scorer.extend) → spec §1 dynamic extension. Task 3 (Markov) → spec §2. Task 4 (cache table) → spec §1 caching + §5 data model. Task 5 (Gutenberg client) → spec §1 core fetch. Task 6 (ES/FR corpora) → spec §3 language corpora, with the copyright-boundary constraint (original content) honored. Task 7 (config field) → spec §3 language selection. Task 8 (LessonEngine routing) → spec §1 + §2 + §3 integration. Task 9 (Settings UI) → spec §4 Settings row widening + language/content-type selectors. Task 10 (Lesson UI) → spec §4 teleprompter auto-scroll + §1 dynamic extension wiring. Task 11 (Results UI) → spec §4 card layout, color coding, arrow-key nav. Task 12 → spec §6 error handling verification + §8 dependency documentation.
- **Not separately task'd, confirmed already satisfied:** spec §6 "Markov chain trained on empty/too-small corpus falls back to word-shuffle" is implemented inline in Task 8's `_build_random_sentences` (checks `if not result.strip()`).
- **Type/signature consistency check:** `LessonEngine.get_lesson` signature in Task 8 matches the call sites added in Task 10 (`language=`, `storage=`, `recent_wpm=`, `session_duration=` all keyword args, matching). `Scorer.extend(more_text: str)` from Task 2 matches its call site in Task 10's `_maybe_extend_text`. `Storage.fetch_cached_excerpts`/`cache_excerpt`/`prune_old_excerpts` signatures from Task 4 match their call sites in Task 8.
