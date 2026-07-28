import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Label

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.book_text import CHARS_PER_PAGE
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen

BOOK_ID = "gutenberg:1"


def _make_app(storage, config):
    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = config
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LessonScreen())

    return TestApp()


def _make_storage_with_book(tmp_path, total_words=2000):
    storage = Storage(tmp_path / "test.db")
    # plenty of words so total_chars comfortably exceeds several pages
    full_text = " ".join(f"word{i}" for i in range(total_words))
    storage.upsert_book(
        book_id=BOOK_ID, source="gutenberg", title="T", author="A",
        language="en", full_text=full_text, cached_at="2026-07-28T10:00:00",
    )
    return storage


def test_next_page_advances_progress_by_one_page_without_scoring_skipped_text(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            start_offset = screen._book_raw_offset(0)
            assert start_offset == 0

            screen.action_next_page()
            await pilot.pause()

            new_offset = storage.fetch_book_progress(BOOK_ID)
            assert new_offset == start_offset + CHARS_PER_PAGE
            # a fresh Scorer was built for the new chunk -- no keystrokes recorded
            assert screen._scorer is not None
            assert screen._scorer.keystrokes == []
            assert screen._scorer.error_count == 0

    asyncio.run(run())
    storage.close()


def test_previous_page_moves_progress_back_by_one_page(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # jump forward two pages first so there's room to go back
            screen.action_next_page()
            await pilot.pause()
            screen.action_next_page()
            await pilot.pause()
            offset_after_two = storage.fetch_book_progress(BOOK_ID)

            screen.action_previous_page()
            await pilot.pause()

            offset_after_back = storage.fetch_book_progress(BOOK_ID)
            assert offset_after_back == offset_after_two - CHARS_PER_PAGE

    asyncio.run(run())
    storage.close()


def test_previous_page_clamps_at_zero_not_negative(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_previous_page()
            await pilot.pause()

            assert storage.fetch_book_progress(BOOK_ID) == 0

    asyncio.run(run())
    storage.close()


def test_book_home_jumps_to_offset_zero(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_next_page()
            await pilot.pause()
            screen.action_next_page()
            await pilot.pause()
            assert storage.fetch_book_progress(BOOK_ID) > 0

            screen.action_book_home()
            await pilot.pause()

            assert storage.fetch_book_progress(BOOK_ID) == 0

    asyncio.run(run())
    storage.close()


def test_next_page_past_end_of_book_shows_book_complete(tmp_path):
    storage = _make_storage_with_book(tmp_path, total_words=50)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            book = storage.get_book(BOOK_ID)
            total_chars = book["total_chars"]

            # jump repeatedly until we've gone past the end
            for _ in range(20):
                screen.action_next_page()
                await pilot.pause()
                if storage.fetch_book_progress(BOOK_ID) >= total_chars:
                    break

            assert storage.fetch_book_progress(BOOK_ID) >= total_chars
            assert screen._scorer is None

    asyncio.run(run())
    storage.close()


def test_page_nav_is_a_no_op_outside_book_mode(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)

    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = cfg
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LessonScreen(custom_text="hello world"))

    app = TestApp()

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            target_before = screen._scorer.target
            pos_before = screen._scorer.position

            screen.action_next_page()
            await pilot.pause()
            screen.action_previous_page()
            await pilot.pause()
            screen.action_book_home()
            await pilot.pause()

            # unchanged -- these actions must no-op when there's no book_id
            assert screen._scorer.target == target_before
            assert screen._scorer.position == pos_before

    asyncio.run(run())
    storage.close()
