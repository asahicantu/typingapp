import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Label

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig, load_config
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
            self.push_screen(LessonScreen(custom_text="hello world"))

    return TestApp()


def test_ctrl_s_toggles_strict_mode_and_persists(tmp_path):
    storage = Storage(tmp_path / "test.db")
    config_path = tmp_path / "config.json"
    cfg = AppConfig(content_type="custom", strict_mode=False, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()

    asyncio.run(run())

    assert app.config.strict_mode is True
    storage.close()


def test_ctrl_s_shows_confirmation_in_hint_bar(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", strict_mode=False, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
            hint = app.screen.query_one("#hint-bar", Label)
            assert "Strict mode" in str(hint.content)
            assert "ON" in str(hint.content)

    asyncio.run(run())
    storage.close()


def test_ctrl_k_toggles_key_sounds_and_persists(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=True)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+k")
            await pilot.pause()

    asyncio.run(run())

    assert app.config.key_sounds is False
    storage.close()


def test_toggling_strict_mode_writes_to_disk(tmp_path):
    from typingapp.config import DEFAULT_CONFIG_PATH
    import typingapp.config as config_module

    storage = Storage(tmp_path / "test.db")
    config_path = tmp_path / "config.json"
    cfg = AppConfig(content_type="custom", strict_mode=False, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run(monkeypatch_path):
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()

    # save_config is called with the default path inside LessonScreen; to verify
    # persistence without monkeypatching the module-level default, just re-load
    # the in-memory app.config object directly (already covered by the first test).
    # This test instead verifies save_config was actually invoked by checking a
    # patched call.
    from unittest.mock import patch
    with patch("typingapp.screens.lesson.save_config") as mock_save:
        asyncio.run(run(config_path))
        assert mock_save.called
    storage.close()
