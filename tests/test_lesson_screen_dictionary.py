import asyncio
from pathlib import Path
from unittest.mock import patch
from textual.app import App
from textual.widgets import Static

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen
from typingapp.screens.dictionary_popup import DictionaryPopupScreen


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
            self.push_screen(LessonScreen(custom_text="the quick fox"))

    return TestApp()


async def _wait_for_popup(pilot, app):
    for _ in range(50):
        await pilot.pause()
        if isinstance(app.screen, DictionaryPopupScreen):
            return True
        await asyncio.sleep(0.05)
    return False


def test_ctrl_d_opens_popup_with_definition(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal"):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+d")
                found = await _wait_for_popup(pilot, app)
                assert found
                assert isinstance(app.screen, DictionaryPopupScreen)
                definition = app.screen.query_one("#dictionary-definition", Static)
                assert "fast animal" in str(definition.content)

    asyncio.run(run())
    storage.close()


def test_ctrl_d_shows_no_definition_found_message(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value=None):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+d")
                found = await _wait_for_popup(pilot, app)
                assert found
                definition = app.screen.query_one("#dictionary-definition", Static)
                assert "No definition found." in str(definition.content)

    asyncio.run(run())
    storage.close()


def test_ctrl_d_shows_unavailable_message_for_non_english_language(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, language="es")
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+d")
                await pilot.pause()
                assert isinstance(app.screen, DictionaryPopupScreen)
                definition = app.screen.query_one("#dictionary-definition", Static)
                assert "Dictionary not available for this language yet" in str(definition.content)
                mock_fetch.assert_not_called()

    asyncio.run(run())
    storage.close()


def test_escape_closes_dictionary_popup(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition"):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+d")
                found = await _wait_for_popup(pilot, app)
                assert found
                await pilot.press("escape")
                await pilot.pause()
                assert isinstance(app.screen, LessonScreen)

    asyncio.run(run())
    storage.close()


def test_ctrl_d_is_a_no_op_when_lesson_is_complete(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                target = screen._scorer.target
                for ch in target:
                    await pilot.press(ch if ch != " " else "space")
                await pilot.pause()
                await pilot.press("ctrl+d")
                await pilot.pause()
                assert not isinstance(app.screen, DictionaryPopupScreen)
                mock_fetch.assert_not_called()

    asyncio.run(run())
    storage.close()
