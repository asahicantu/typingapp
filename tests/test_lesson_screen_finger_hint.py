# tests/test_lesson_screen_finger_hint.py
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


def test_finger_hint_shows_immediately_on_lesson_start(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "the" in text
            assert "next key" in text.lower()

    asyncio.run(run())
    storage.close()


def test_finger_hint_names_the_correct_finger_for_the_next_key(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            # target text is "the quick fox" — first char 't' is Left index
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "Left" in text
            assert "index" in text

    asyncio.run(run())
    storage.close()


def test_finger_hint_updates_as_the_user_types(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.press("h")
            await pilot.press("e")
            await pilot.press("space")
            await pilot.pause()
            # after typing "the ", the current word is "quick", next key is 'q' -> Left pinky
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "quick" in text
            assert "Left" in text
            assert "pinky" in text

    asyncio.run(run())
    storage.close()


def test_finger_hint_is_empty_when_lesson_is_complete(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # Grab the label reference up front: completing the final keystroke of a
            # non-book lesson triggers LessonScreen._finish() -> switch_screen(ResultsScreen)
            # synchronously within on_key, so app.screen is no longer the LessonScreen (and
            # the widget is unmounted) by the time typing finishes. The label is updated to
            # "" before that switch happens (_update_finger_hint_label runs right after
            # _render_text, before the is_complete/_finish check), so querying the
            # already-held reference captures that correct state.
            hint = screen.query_one("#finger-hint-val", Label)
            target = screen._scorer.target
            for ch in target:
                await pilot.press(ch if ch != " " else "space")
            await pilot.pause()
            assert str(hint.content) == ""

    asyncio.run(run())
    storage.close()


def test_finger_hint_shown_in_book_mode_too(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text="word " * 200, cached_at="2026-07-27T10:00:00")
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            hint = app.screen.query_one("#finger-hint-val", Label)
            text = str(hint.content)
            assert "word" in text
            assert "next key" in text.lower()

    asyncio.run(run())
    storage.close()
