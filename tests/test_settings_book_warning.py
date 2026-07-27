from types import SimpleNamespace

from typingapp.config import AppConfig
from typingapp.screens.settings import _book_mismatch_warning, _epub_folder_status


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


def test_epub_folder_status_blank_when_no_folder_configured():
    assert _epub_folder_status("") == ""


def test_epub_folder_status_warns_when_folder_has_no_epub_files(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    status = _epub_folder_status(str(empty_dir))
    assert status.startswith("⚠")
    assert "No .epub files found" in status


def test_epub_folder_status_ok_when_epub_files_present(tmp_path):
    from tests.test_epub_source import _write_epub
    _write_epub(tmp_path / "book.epub")
    status = _epub_folder_status(str(tmp_path))
    assert status.startswith("✓")
    assert "1 EPUB file" in status


def test_book_display_text_explains_uncached_book_clearly():
    from typingapp.screens.settings import _book_display_text

    class FakeStorage:
        def get_book(self, book_id):
            return None

    app = _fake_app(AppConfig(selected_book_id="gutenberg:999"))
    app.storage = FakeStorage()
    text = _book_display_text(app)
    assert text.startswith("⚠")
    assert "gutenberg:999" in text
    assert "Browse Books" in text or "My Books" in text
