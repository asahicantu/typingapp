from unittest.mock import patch, MagicMock
import json
import urllib.error
from typingapp.engine.dictionary import fetch_definition


SAMPLE_DICTIONARY_RESPONSE = json.dumps([
    {
        "word": "hello",
        "phonetic": "/həˈloʊ/",
        "meanings": [
            {
                "partOfSpeech": "exclamation",
                "definitions": [
                    {
                        "definition": "used as a greeting or to begin a phone conversation.",
                        "example": "hello there, Katie!",
                    }
                ],
            }
        ],
    }
]).encode("utf-8")

SAMPLE_404_RESPONSE = json.dumps({
    "title": "No Definitions Found",
    "message": "Sorry pal, we couldn't find definitions for the word you were looking for.",
    "resolution": "You can try the search again at later time or head to the web instead.",
}).encode("utf-8")


def _mock_urlopen_returning(payload_bytes):
    mock_response = MagicMock()
    mock_response.read.return_value = payload_bytes
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    return mock_response


def test_fetch_definition_returns_formatted_string_on_success():
    with patch("typingapp.engine.dictionary.urlopen", return_value=_mock_urlopen_returning(SAMPLE_DICTIONARY_RESPONSE)):
        result = fetch_definition("hello", "en")
    assert result is not None
    assert "exclamation" in result
    assert "used as a greeting" in result


def test_fetch_definition_returns_none_for_non_english_language():
    with patch("typingapp.engine.dictionary.urlopen") as mock_urlopen:
        result = fetch_definition("hola", "es")
    assert result is None
    mock_urlopen.assert_not_called()


def test_fetch_definition_returns_none_on_network_error():
    with patch("typingapp.engine.dictionary.urlopen", side_effect=urllib.error.URLError("no connection")):
        result = fetch_definition("hello", "en")
    assert result is None


def test_fetch_definition_returns_none_on_404_style_empty_response():
    with patch("typingapp.engine.dictionary.urlopen", return_value=_mock_urlopen_returning(SAMPLE_404_RESPONSE)):
        result = fetch_definition("asdfghjkl", "en")
    assert result is None


def test_fetch_definition_returns_none_for_empty_word():
    with patch("typingapp.engine.dictionary.urlopen") as mock_urlopen:
        assert fetch_definition("", "en") is None
        assert fetch_definition("   ", "en") is None
    mock_urlopen.assert_not_called()
