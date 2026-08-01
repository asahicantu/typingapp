from __future__ import annotations
import json
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError

DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"
TIMEOUT_SECONDS = 3
USER_AGENT = "Mozilla/5.0 (compatible; typingapp/1.0; +https://github.com/)"


def _get(url: str, timeout: float):
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def fetch_definition(word: str, language: str = "en") -> str | None:
    """Look up a short definition for `word`. dictionaryapi.dev only serves English
    definitions (confirmed: every non-English language tried 404s) -- short-circuit
    to None for any other language before making a network call, rather than making
    a request that's guaranteed to fail. Never raises; returns None on any failure
    (unreachable, 404, malformed response, empty word)."""
    word = word.strip()
    if not word or language != "en":
        return None
    url = f"{DICTIONARY_API_URL}/{quote(word)}"
    try:
        with _get(url, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError, OSError):
        return None
    try:
        entry = payload[0]
        meaning = entry["meanings"][0]
        part_of_speech = meaning.get("partOfSpeech", "")
        definition = meaning["definitions"][0]["definition"]
    except (KeyError, IndexError, TypeError):
        return None
    if part_of_speech:
        return f"({part_of_speech}) {definition}"
    return definition
