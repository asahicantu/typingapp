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
