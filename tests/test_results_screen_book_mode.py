import asyncio
import datetime
from pathlib import Path
from textual.app import App

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.engine.scorer import Scorer
from typingapp.screens.results import ResultsScreen
from typingapp.screens.lesson import LessonScreen
from typingapp.screens.library import LibraryScreen


def _make_scorer(text="hello world"):
    scorer = Scorer(text, strict_mode=False)
    scorer.start()
    for ch in text:
        scorer.process_key(ch)
    return scorer


def _make_app(storage, config, screen):
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
            self.push_screen(screen)

    return TestApp()


def test_book_session_results_shows_continue_and_library_shortcuts_not_retry_new(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Dracula",
                         author="Bram Stoker", language="en", full_text="word " * 3000,
                         cached_at=datetime.datetime.now().isoformat())
    storage.update_book_progress("gutenberg:1", current_offset=600, updated_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1")
    screen = ResultsScreen(scorer=_make_scorer(), session_id=1, book_id="gutenberg:1")
    app = _make_app(storage, cfg, screen)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            labels = [str(w.content) for w in app.screen.query(".command-item")]
            assert any("Continue Book" in l for l in labels)
            assert any("My Books" in l for l in labels)
            assert not any("Retry Same" in l for l in labels)
            assert not any("New Lesson" in l for l in labels)

    asyncio.run(run())
    storage.close()


def test_non_book_session_results_shows_retry_and_new_lesson_shortcuts(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="words")
    screen = ResultsScreen(scorer=_make_scorer(), session_id=1, book_id="")
    app = _make_app(storage, cfg, screen)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            labels = [str(w.content) for w in app.screen.query(".command-item")]
            assert any("Retry Same" in l for l in labels)
            assert any("New Lesson" in l for l in labels)
            assert not any("Continue Book" in l for l in labels)
            assert not any("My Books" in l for l in labels)

    asyncio.run(run())
    storage.close()


def test_ctrl_c_continue_book_switches_to_lesson_screen(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Dracula",
                         author="Bram Stoker", language="en", full_text="word " * 3000,
                         cached_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1")
    screen = ResultsScreen(scorer=_make_scorer(), session_id=1, book_id="gutenberg:1")
    app = _make_app(storage, cfg, screen)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("c")
            await pilot.pause()
            assert isinstance(app.screen, LessonScreen)

    asyncio.run(run())
    storage.close()


def test_l_open_library_from_book_results(tmp_path):
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Dracula",
                         author="Bram Stoker", language="en", full_text="word " * 3000,
                         cached_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1")
    screen = ResultsScreen(scorer=_make_scorer(), session_id=1, book_id="gutenberg:1")
    app = _make_app(storage, cfg, screen)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()
            assert isinstance(app.screen, LibraryScreen)

    asyncio.run(run())
    storage.close()


def test_r_retry_same_is_a_noop_in_book_mode_results(tmp_path):
    from typingapp.screens.results import ResultsScreen as RS

    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="Dracula",
                         author="Bram Stoker", language="en", full_text="word " * 3000,
                         cached_at=datetime.datetime.now().isoformat())
    cfg = AppConfig(content_type="literature", selected_book_id="gutenberg:1")
    screen = ResultsScreen(scorer=_make_scorer(), session_id=1, book_id="gutenberg:1")
    app = _make_app(storage, cfg, screen)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
            assert isinstance(app.screen, RS)  # stayed on Results — 'r' is a no-op here

    asyncio.run(run())
    storage.close()
