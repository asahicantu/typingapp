import asyncio
import datetime
from pathlib import Path
from textual.app import App
from textual.widgets import Label, ListView

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.library import LibraryScreen
from typingapp.screens.lesson import LessonScreen


def _make_app(storage, config=None):
    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = config or AppConfig()
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LibraryScreen())

    return TestApp()


def test_empty_library_shows_helpful_status(tmp_path):
    storage = Storage(tmp_path / "test.db")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            status = app.screen.query_one("#library-status", Label)
            assert "browse" in str(status.content).lower() or "no books yet" in str(status.content).lower()

    asyncio.run(run())
    storage.close()


def test_library_lists_all_cached_books_with_progress(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Pride and Prejudice",
                         author="Jane Austen", language="en", full_text="word " * 5000,
                         cached_at=datetime.datetime.now().isoformat())
    storage.upsert_book(book_id="epub:abc", source="epub", title="Dracula",
                         author="Bram Stoker", language="en", full_text="word " * 3000,
                         cached_at=datetime.datetime.now().isoformat())
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            status = app.screen.query_one("#library-status", Label)
            assert "2 book" in str(status.content)
            items = list(app.screen.query("ListItem"))
            assert len(items) == 2

    asyncio.run(run())
    storage.close()


def test_reading_a_book_pins_it_and_starts_a_lesson(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Pride and Prejudice",
                         author="Jane Austen", language="en", full_text="word " * 5000,
                         cached_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="words")  # deliberately mismatched, to prove Read fixes it
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.screen.query_one("#library-list", ListView).index = 0
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, LessonScreen)

    asyncio.run(run())

    assert app.config.content_type == "literature"
    assert app.config.selected_book_id == "gutenberg:1"
    storage.close()


def test_deleting_a_book_removes_it_from_the_list_and_storage(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Pride and Prejudice",
                         author="Jane Austen", language="en", full_text="word " * 5000,
                         cached_at=datetime.datetime.now().isoformat())
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.screen.query_one("#library-list", ListView).index = 0
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            items = list(app.screen.query("ListItem"))
            assert len(items) == 1  # placeholder "(your library is empty)" row

    asyncio.run(run())

    assert storage.get_book("gutenberg:1") is None
    storage.close()


def test_deleting_the_currently_selected_book_clears_selection(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Pride and Prejudice",
                         author="Jane Austen", language="en", full_text="word " * 5000,
                         cached_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1")
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.screen.query_one("#library-list", ListView).index = 0
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()

    asyncio.run(run())

    assert app.config.selected_book_id == ""
    storage.close()
