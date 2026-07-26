import asyncio
from pathlib import Path
from unittest.mock import patch
from textual.app import App
from textual.widgets import Input, Label, ListView

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.engine.gutenberg import BookMeta


def _make_app(storage, epub_folder=""):
    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = AppConfig(epub_folder=epub_folder)
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            from typingapp.screens.settings import SettingsScreen
            self.push_screen(SettingsScreen())

    return TestApp()


def test_selecting_first_search_result_immediately_pins_book(tmp_path):
    # regression: ListView.clear() resets .index to None, so a search result render that
    # doesn't re-highlight the first item leaves Enter/select-cursor a no-op until the user
    # manually presses an arrow key first.
    storage = Storage(tmp_path / "test.db")
    app = _make_app(storage)
    book = BookMeta(gutenberg_id=1342, title="Pride and Prejudice", author="Jane Austen",
                     text_url="https://example.org/1342.txt")

    async def run():
        with patch("typingapp.screens.book_search.search_books", return_value=[book]), \
             patch("typingapp.screens.settings.fetch_full_text", return_value="Some book text here."):
            async with app.run_test() as pilot:
                await pilot.pause()
                app.screen.query_one("#btn-browse-books").press()
                await pilot.pause()

                # Browsing no longer auto-searches on mount (that surfaced an unfiltered,
                # irrelevant default catalog listing) — the user must type a query first.
                search_input = app.screen.query_one("#search-input", Input)
                search_input.value = "pride"
                app.screen._run_search("pride")

                list_view = app.screen.query_one("#results-list", ListView)
                for _ in range(50):
                    await pilot.pause()
                    if list_view.index is not None:
                        break
                    await asyncio.sleep(0.05)
                assert list_view.index == 0

                list_view.action_select_cursor()
                await pilot.pause()

    asyncio.run(run())

    assert app.config.selected_book_id == "gutenberg:1342"
    assert storage.get_book("gutenberg:1342") is not None
    storage.close()


def test_browsing_does_not_run_an_unfiltered_default_search(tmp_path):
    # regression: opening Browse Books used to immediately run an empty-query search,
    # which shows Gutendex's unfiltered default catalog listing — confusing "results"
    # unrelated to anything the user typed. The list should start empty.
    storage = Storage(tmp_path / "test.db")
    app = _make_app(storage)
    book = BookMeta(gutenberg_id=1, title="Some Book", author="Someone",
                     text_url="https://example.org/1.txt")

    async def run():
        with patch("typingapp.screens.book_search.search_books", return_value=[book]) as mock_search:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.screen.query_one("#btn-browse-books").press()
                await pilot.pause()

                list_view = app.screen.query_one("#results-list", ListView)
                assert list_view.index is None
                mock_search.assert_not_called()

    asyncio.run(run())
    storage.close()


def test_gutenberg_search_runs_off_the_ui_thread_and_shows_warning_when_empty(tmp_path):
    # regression: _run_search used to call search_books() synchronously, freezing the UI
    # for the duration of the network call, and silently showed "(no matches)" whether
    # the query genuinely had no matches or Gutenberg was simply unreachable.
    storage = Storage(tmp_path / "test.db")
    app = _make_app(storage)

    async def run():
        with patch("typingapp.screens.book_search.search_books", return_value=[]):
            async with app.run_test() as pilot:
                await pilot.pause()
                app.screen.query_one("#btn-browse-books").press()
                await pilot.pause()

                app.screen._run_search("nonexistent query")

                status = app.screen.query_one("#search-status", Label)
                for _ in range(50):
                    await pilot.pause()
                    if "unreachable" in str(status.content) or "No Gutenberg matches" in str(status.content):
                        break
                    await asyncio.sleep(0.05)
                text = str(status.content)
                assert "unreachable" in text or "No Gutenberg matches" in text

    asyncio.run(run())
    storage.close()


def test_clear_selection_resets_selected_book_id(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text="x" * 10, cached_at="2026-07-26T10:00:00")
    app = _make_app(storage)
    app.config.selected_book_id = "gutenberg:1"

    async def run():
        with patch("typingapp.screens.book_search.search_books", return_value=[]):
            async with app.run_test() as pilot:
                await pilot.pause()
                app.screen.query_one("#btn-clear-book").press()
                await pilot.pause()

    asyncio.run(run())

    assert app.config.selected_book_id == ""
    storage.close()
