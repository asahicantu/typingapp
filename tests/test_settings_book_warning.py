from types import SimpleNamespace

from typingapp.config import AppConfig
from typingapp.screens.settings import _book_mismatch_warning


def _fake_app(config):
    return SimpleNamespace(config=config)


def test_no_warning_when_no_book_selected():
    app = _fake_app(AppConfig(content_type="words", selected_book_id=""))
    assert _book_mismatch_warning(app, "words") == ""


def test_no_warning_when_content_type_matches_literature():
    app = _fake_app(AppConfig(content_type="literature", selected_book_id="gutenberg:1"))
    assert _book_mismatch_warning(app, "literature") == ""


def test_warning_when_book_selected_but_content_type_mismatched():
    app = _fake_app(AppConfig(content_type="words", selected_book_id="gutenberg:1"))
    warning = _book_mismatch_warning(app, "words")
    assert "Words" in warning
    assert "Literature" in warning
    assert warning.startswith("⚠")


def test_warning_reflects_the_passed_content_type_not_saved_config():
    # the Select widget's live (unsaved) value should drive the warning, not app.config.content_type
    app = _fake_app(AppConfig(content_type="literature", selected_book_id="gutenberg:1"))
    warning = _book_mismatch_warning(app, "code")
    assert "Code" in warning
