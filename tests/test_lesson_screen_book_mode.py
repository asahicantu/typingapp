import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Static

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

BOOK_TEXT = (
    "# Chapter One\n\n"
    "It was a bright cold day in April, and the clocks were striking thirteen. "
    "Winston Smith, his chin nuzzled into his breast, slipped quickly.\n\n"
    "The hallway smelt of boiled cabbage and old rag mats."
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
            from typingapp.screens.lesson import LessonScreen
            self.push_screen(LessonScreen())

    return TestApp()


def test_book_mode_target_never_contains_heading_marker(tmp_path):
    # regression: chunk_from_offset's raw markup text (with '# ' heading markers) was being
    # used directly as the literal string the user has to type
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=BOOK_TEXT, cached_at="2026-07-26T10:00:00")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            target = app.screen._scorer.target
            assert "#" not in target
            assert target.startswith("Chapter One")

    asyncio.run(run())
    storage.close()


def test_book_mode_rendering_survives_headings_and_punctuation(tmp_path):
    # regression: styling untyped punctuation with Rich's `color(244)` syntax crashed Textual's
    # own (stricter) markup parser with "auto closing tag has nothing to close"
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=BOOK_TEXT, cached_at="2026-07-26T10:00:00")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            target = screen._scorer.target
            for ch in target[:25]:
                await pilot.press(ch if ch != " " else "space")
            await pilot.pause()
            # would have raised MarkupError during _render_text() if broken
            assert isinstance(screen.query_one("#text-display", Static), Static)

    asyncio.run(run())
    storage.close()


def test_book_mode_completion_persists_exact_end_offset(tmp_path):
    # regression: absolute offset math didn't account for the 2 stripped '# ' chars per heading,
    # so progress would under-count once a chunk contained a heading
    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=BOOK_TEXT, cached_at="2026-07-26T10:00:00")
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

    assert storage.fetch_book_progress("gutenberg:1") == len(BOOK_TEXT)
    storage.close()


def test_book_mode_does_not_auto_finish_session_on_chunk_completion(tmp_path):
    # the user decides when a reading session ends, not the chunk boundary — finishing the
    # currently-loaded text must NOT switch to ResultsScreen the way non-book lessons do.
    from typingapp.screens.lesson import LessonScreen

    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=BOOK_TEXT, cached_at="2026-07-26T10:00:00")
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
            assert isinstance(app.screen, LessonScreen)
            assert app.screen._scorer is not None

    asyncio.run(run())
    storage.close()


def test_ctrl_f_finish_session_action_ends_a_book_mode_session(tmp_path):
    from typingapp.screens.results import ResultsScreen

    storage = Storage(tmp_path / "test.db")
    storage.upsert_book(book_id="gutenberg:1", source="gutenberg", title="T", author="A",
                         language="en", full_text=BOOK_TEXT, cached_at="2026-07-26T10:00:00")
    app = _make_app(storage)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+f")
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)

    asyncio.run(run())
    storage.close()


def test_ctrl_f_finish_session_is_a_noop_outside_book_mode(tmp_path):
    # non-book lessons already end themselves on completion; Ctrl+F should do nothing while
    # a non-book lesson is still in progress (no premature finish, no crash).
    from typingapp.screens.lesson import LessonScreen

    storage = Storage(tmp_path / "test.db")

    class TestApp(App):
        CSS_PATH = APP_TCSS_PATH

        def __init__(self):
            super().__init__()
            self.config = AppConfig(content_type="words", session_duration=600, key_sounds=False)
            self.storage = storage
            self.lesson_engine = LessonEngine()
            self.adaptive = AdaptiveEngine(current_level=1)
            self.sound = SoundPlayer()

        def on_mount(self):
            self.push_screen(LessonScreen())

    app = TestApp()

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+f")
            await pilot.pause()
            assert isinstance(app.screen, LessonScreen)
            assert app.screen._scorer is not None
            assert not app.screen._scorer.is_complete

    asyncio.run(run())
    storage.close()
