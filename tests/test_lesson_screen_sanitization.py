import asyncio
from pathlib import Path
from textual.app import App

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen

UNTYPEABLE_BOOK_TEXT = (
    "# Chapter One\n\n"
    "“Wait—no,” she said… ‘Really?’ A pause of 100 km followed.\n\n"
    "Second paragraph with normal ascii text."
)


def _make_app(storage, book_id="gutenberg:1"):
    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = AppConfig(content_type="literature", selected_book_id=book_id,
                                     session_duration=600, key_sounds=False)
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LessonScreen())

    return TestApp()


def test_book_mode_target_contains_no_untypeable_characters(tmp_path):
    from typingapp.engine.keyboard_sanitize import TYPEABLE_ASCII

    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=UNTYPEABLE_BOOK_TEXT, cached_at="2026-07-27T10:00:00")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            target = app.screen._scorer.target
            for ch in target:
                assert ch in TYPEABLE_ASCII, f"untypeable character {ch!r} reached the Scorer target"

    asyncio.run(run())
    storage.close()


def test_sanitization_preserves_book_offset_arithmetic(tmp_path):
    # regression: sanitizing must never change character COUNT, or book_progress offsets
    # (measured against the original, unsanitized full_text) would drift from what was
    # actually typed.
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=UNTYPEABLE_BOOK_TEXT, cached_at="2026-07-27T10:00:00")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            target = screen._scorer.target
            while not screen._scorer.is_complete:
                ch = target[screen._scorer.position]
                await pilot.press(ch if ch != " " else "space")
            await pilot.pause()

    asyncio.run(run())

    assert storage.fetch_book_progress("gutenberg:1") == len(UNTYPEABLE_BOOK_TEXT)
    storage.close()
