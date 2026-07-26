import datetime
from types import SimpleNamespace

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.screens.menu import _next_lesson_preview


def _fake_app(config, storage):
    return SimpleNamespace(config=config, storage=storage)


def test_preview_shows_plain_content_type_when_not_literature():
    app = _fake_app(AppConfig(content_type="words"), storage=None)
    assert _next_lesson_preview(app) == "Next: Words"


def test_preview_shows_random_excerpts_for_literature_without_selected_book():
    app = _fake_app(AppConfig(content_type="literature"), storage=None)
    assert _next_lesson_preview(app) == "Next: Literature"


def test_preview_shows_book_title_and_progress_when_book_selected(tmp_path):
    storage = Storage(tmp_path / "test.db")
    full_text = "word " * 3000
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Pride and Prejudice",
                         author="Jane Austen", language="en", full_text=full_text,
                         cached_at=datetime.datetime.now().isoformat())
    storage.update_book_progress("gutenberg:1", current_offset=600, updated_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1")
    app = _fake_app(cfg, storage)

    preview = _next_lesson_preview(app)
    assert "Pride and Prejudice" in preview
    assert "page 1/" in preview
    storage.close()


def test_preview_shows_not_cached_yet_when_book_selected_but_missing_from_storage(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:999")
    app = _fake_app(cfg, storage)

    preview = _next_lesson_preview(app)
    assert "not cached yet" in preview
    storage.close()


def test_preview_ignores_selected_book_when_content_type_is_not_literature(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Some Book",
                         author="Someone", language="en", full_text="x" * 100,
                         cached_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="words", selected_book_id="gutenberg:1")
    app = _fake_app(cfg, storage)

    preview = _next_lesson_preview(app)
    assert preview == "Next: Words"
    assert "Some Book" not in preview
    storage.close()
