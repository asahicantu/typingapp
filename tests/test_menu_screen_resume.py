import asyncio
import datetime
from pathlib import Path
from textual.app import App
from textual.widgets import Label, Select, Button

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer


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
            from typingapp.screens.menu import MenuScreen
            self.push_screen(MenuScreen())

    return TestApp()


def test_menu_preview_refreshes_after_returning_from_settings(tmp_path):
    # regression: MenuScreen used to only set the "Next: ..." preview label in on_mount,
    # which fires once ever — after Settings changes content type/book and pops back,
    # the label stayed stale. on_screen_resume fires on every return, on_show does not.
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Dracula",
                         author="Bram Stoker", language="en", full_text="word " * 3000,
                         cached_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="words", selected_book_id="gutenberg:1")
    app = _make_app(storage, cfg)

    async def run():
        from typingapp.screens.settings import SettingsScreen
        async with app.run_test() as pilot:
            await pilot.pause()
            preview = app.screen.query_one("#next-lesson-label", Label)
            assert str(preview.content) == "Next: Words"

            app.push_screen(SettingsScreen())
            await pilot.pause()
            sel = app.screen.query_one("#sel-content", Select)
            sel.value = "literature"
            await pilot.pause()

            save_btn = app.screen.query_one("#btn-save", Button)
            save_btn.scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click("#btn-save")
            await pilot.pause()

            preview_after = app.screen.query_one("#next-lesson-label", Label)
            assert "Dracula" in str(preview_after.content)

    asyncio.run(run())
    storage.close()
