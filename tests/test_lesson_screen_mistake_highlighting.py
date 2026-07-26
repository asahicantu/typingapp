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


def test_previously_missed_words_render_with_highlight_class(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.record_word_mistakes({"jumps": 5})
    cfg = AppConfig(content_type="custom", key_sounds=False, highlight_past_mistakes=True)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # custom_text must be set before _start_lesson runs; on_mount already
            # called _start_lesson once during push_screen, so re-set _custom_text
            # and call _start_lesson() again explicitly to pick it up deterministically.
            screen._custom_text = "the quick fox jumps over"
            screen._start_lesson()
            await pilot.pause()
            assert "jumps" in screen._missed_words

    asyncio.run(run())
    storage.close()


def test_words_below_threshold_are_not_highlighted(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.record_word_mistakes({"rare": 1})  # below default min_misses=2
    cfg = AppConfig(content_type="custom", key_sounds=False, highlight_past_mistakes=True)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._custom_text = "a rare word here"
            screen._start_lesson()
            await pilot.pause()
            assert "rare" not in screen._missed_words

    asyncio.run(run())
    storage.close()


def test_highlighting_disabled_via_config_yields_empty_missed_words(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.record_word_mistakes({"jumps": 10})
    cfg = AppConfig(content_type="custom", key_sounds=False, highlight_past_mistakes=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._custom_text = "the quick fox jumps over"
            screen._start_lesson()
            await pilot.pause()
            assert screen._missed_words == set()

    asyncio.run(run())
    storage.close()


def test_finishing_a_session_records_word_mistakes_for_next_time(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False, session_duration=600)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._custom_text = "cat"
            screen._start_lesson()
            await pilot.pause()
            # type it wrong once, then correctly, to generate a word_errors entry
            await pilot.press("x")  # wrong first char
            await pilot.press("c")
            await pilot.press("a")
            await pilot.press("t")
            await pilot.pause()

    asyncio.run(run())

    missed = storage.fetch_frequently_missed_words(min_misses=1)
    assert "cat" in missed
    storage.close()
