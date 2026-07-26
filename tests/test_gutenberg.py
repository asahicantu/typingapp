from unittest.mock import patch, MagicMock
import json
import urllib.error
from typingapp.engine.gutenberg import search_books, fetch_excerpt, fetch_full_text, BookMeta, USER_AGENT


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


def test_search_books_sends_browser_like_user_agent():
    captured_request = {}

    def fake_urlopen(request, timeout=None):
        captured_request["request"] = request
        return _mock_urlopen_returning(SAMPLE_GUTENDEX_RESPONSE)

    with patch("typingapp.engine.gutenberg.urlopen", side_effect=fake_urlopen):
        search_books(language="en", limit=20)
    assert captured_request["request"].get_header("User-agent") == USER_AGENT


def test_search_books_appends_search_query_param():
    captured_request = {}

    def fake_urlopen(request, timeout=None):
        captured_request["request"] = request
        return _mock_urlopen_returning(SAMPLE_GUTENDEX_RESPONSE)

    with patch("typingapp.engine.gutenberg.urlopen", side_effect=fake_urlopen):
        search_books(language="en", limit=20, query="pride and prejudice")
    assert "search=pride%20and%20prejudice" in captured_request["request"].full_url


def test_search_books_without_query_omits_search_param():
    with patch("typingapp.engine.gutenberg.urlopen", return_value=_mock_urlopen_returning(SAMPLE_GUTENDEX_RESPONSE)):
        search_books(language="en", limit=20)


def test_fetch_full_text_strips_boilerplate_and_returns_whole_body():
    book = BookMeta(gutenberg_id=1, title="Sample", author="Someone", text_url="https://example.org/1.txt")
    with patch("typingapp.engine.gutenberg.urlopen", return_value=_mock_urlopen_returning(SAMPLE_BOOK_TEXT)):
        full_text = fetch_full_text(book)
    assert full_text is not None
    assert "Project Gutenberg eBook" not in full_text
    assert "More boilerplate" not in full_text
    assert len(full_text.split()) == 500


def test_fetch_full_text_returns_none_on_network_error():
    book = BookMeta(gutenberg_id=1, title="Sample", author="Someone", text_url="https://example.org/1.txt")
    with patch("typingapp.engine.gutenberg.urlopen", side_effect=urllib.error.URLError("no connection")):
        assert fetch_full_text(book) is None
