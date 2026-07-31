# tests/test_lesson_screen_norwegian.py
import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Label

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen


def _make_app(storage, config, custom_text):
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
            self.push_screen(LessonScreen(custom_text=custom_text))

    return TestApp()


def test_finger_hint_not_blank_when_cursor_is_on_ae(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, language="no")
    # cursor starts at position 0, directly on the ae character
    app = _make_app(storage, cfg, custom_text="æra og tid")

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert text != ""
            assert "Right" in text
            assert "pinky" in text

    asyncio.run(run())
    storage.close()


def test_finger_hint_not_blank_when_cursor_is_on_oe(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, language="no")
    app = _make_app(storage, cfg, custom_text="øye og hjerte")

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert text != ""
            assert "Right" in text
            assert "pinky" in text

    asyncio.run(run())
    storage.close()


def test_finger_hint_not_blank_when_cursor_is_on_aa(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, language="no")
    app = _make_app(storage, cfg, custom_text="åpen dor")

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert text != ""
            assert "Right" in text
            assert "pinky" in text

    asyncio.run(run())
    storage.close()


def test_finger_hint_not_blank_mid_word_on_ae_ligature(tmp_path):
    # a Nordic letter appearing mid-word (not just at cursor start position 0)
    # must also not blank the hint bar once the cursor advances onto it.
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, language="no")
    app = _make_app(storage, cfg, custom_text="træ er fint")

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.press("r")
            await pilot.pause()
            # cursor is now on the ae character (position 2)
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert text != ""
            assert "Right" in text
            assert "pinky" in text

    asyncio.run(run())
    storage.close()
