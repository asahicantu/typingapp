import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Static

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen


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
            self.push_screen(LessonScreen(custom_text="hello"))

    return TestApp()


def test_non_book_footer_lists_core_shortcuts_and_new_toggles(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.screen.query_one("#footer-hint", Static)
            text = str(footer.renderable) if hasattr(footer, "renderable") else str(footer.content)
            for expected in ("Ctrl+R", "Ctrl+Q", "Ctrl+E", "Ctrl+S", "Ctrl+K"):
                assert expected in text
            assert "Ctrl+F" not in text  # finish_session is book-mode only

    asyncio.run(run())
    storage.close()


def test_book_mode_footer_includes_finish_shortcut(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text="word " * 200, cached_at="2026-07-27T10:00:00")
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.screen.query_one("#footer-hint", Static)
            text = str(footer.content)
            assert "Ctrl+F" in text
            assert "Ctrl+S" in text
            assert "Ctrl+K" in text

    asyncio.run(run())
    storage.close()
