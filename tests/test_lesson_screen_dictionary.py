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


def test_ctrl_d_strips_punctuation_before_lookup(tmp_path):
    # cursor starts at position 0, which is 't' of "times," -- current_word_at
    # returns "times," (with the trailing comma) for display purposes, but the
    # dictionary lookup itself must use the stripped/lowercased form "times"
    # or it 404s against dictionaryapi.dev on real book prose.
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
            self.push_screen(LessonScreen(custom_text="times, and wisdom"))

    app = TestApp()

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a moment") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("ctrl+d")
                found = await _wait_for_popup(pilot, app)
                assert found
                mock_fetch.assert_called_once()
                called_word = mock_fetch.call_args[0][0]
                assert called_word == "times"
                # the popup title should still show the original, unstripped word
                title = app.screen.query_one(".menu-title", Static)
                assert "times," in str(title.content)

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


def test_ctrl_d_survives_fetch_definition_raising_and_resets_in_progress_flag(tmp_path):
    # engine/dictionary.py's fetch_definition claims "never raises," but its except
    # clause doesn't cover http.client.HTTPException/IncompleteRead. If it raises
    # inside the _lookup_definition worker thread, call_from_thread never runs and
    # _dictionary_lookup_in_progress is stuck True forever -- and Textual's @work
    # defaults to exit_on_error=True, crashing the app. This test proves both that
    # a raising fetch_definition degrades to the normal "No definition found." popup
    # (no crash) and that a SECOND, later Ctrl+D press still reaches fetch_definition
    # (proving the in-progress flag was correctly reset, not permanently stuck).
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
            self.push_screen(LessonScreen(custom_text="the quick fox"))

    app = TestApp()

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            with patch("typingapp.screens.lesson.fetch_definition", side_effect=RuntimeError("boom")):
                await pilot.press("ctrl+d")
                found = await _wait_for_popup(pilot, app)
                assert found
                definition = app.screen.query_one("#dictionary-definition", Static)
                assert "No definition found." in str(definition.content)
                await pilot.press("escape")
                await pilot.pause()
                assert isinstance(app.screen, LessonScreen)

            with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal") as mock_fetch:
                await pilot.press("ctrl+d")
                found = await _wait_for_popup(pilot, app)
                assert found
                mock_fetch.assert_called_once()
                definition = app.screen.query_one("#dictionary-definition", Static)
                assert "fast animal" in str(definition.content)

    asyncio.run(run())
    storage.close()


def test_repeated_ctrl_d_does_not_stack_multiple_popups(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                # fire several Ctrl+D presses back-to-back before the first lookup's
                # popup has had a chance to appear/settle
                await pilot.press("ctrl+d")
                await pilot.press("ctrl+d")
                await pilot.press("ctrl+d")
                found = await _wait_for_popup(pilot, app)
                assert found
                await pilot.pause()
                # a second press once the popup IS showing should also be a no-op
                await pilot.press("ctrl+d")
                await pilot.pause()
                # only one DictionaryPopupScreen should ever be on the stack
                popup_count = sum(
                    1 for screen in app.screen_stack if isinstance(screen, DictionaryPopupScreen)
                )
                assert popup_count == 1
                mock_fetch.assert_called_once()

    asyncio.run(run())
    storage.close()
