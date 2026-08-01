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


def _make_app(storage, config, custom_text="the quick fox"):
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


async def _wait_for_panel_content(pilot, screen, expected_substring, attempts=50):
    for _ in range(attempts):
        await pilot.pause()
        content = screen.query_one("#dictionary-panel-content", Static)
        if expected_substring in str(content.content):
            return True
        await asyncio.sleep(0.05)
    return False


def test_ctrl_d_populates_panel_with_definition_and_keeps_typing_focus(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg, custom_text="fox")

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "fast animal")
                assert found
                assert screen._dictionary_word == "fox"
                # focus stays on the typing area -- panel is NOT focused after a fresh lookup
                panel = screen.query_one("#dictionary-panel")
                assert not panel.has_focus

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
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "No definition found.")
                assert found

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
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(
                    pilot, screen, "Dictionary not available for this language yet"
                )
                assert found
                mock_fetch.assert_not_called()

    asyncio.run(run())
    storage.close()


def test_second_ctrl_d_on_same_word_focuses_panel_instead_of_relookup(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "fast animal")
                assert found
                mock_fetch.assert_called_once()

                # cursor hasn't moved -- second Ctrl+D on the SAME word focuses the panel
                # instead of re-fetching
                await pilot.press("ctrl+d")
                await pilot.pause()
                panel = screen.query_one("#dictionary-panel")
                assert panel.has_focus
                mock_fetch.assert_called_once()  # still only once -- no re-fetch

    asyncio.run(run())
    storage.close()


def test_ctrl_d_on_different_word_relooksup_instead_of_focusing(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg, custom_text="the quick fox")

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")  # looks up "the" (cursor starts at position 0)
                found = await _wait_for_panel_content(pilot, screen, "a definition")
                assert found
                assert screen._dictionary_word == "the"
                mock_fetch.assert_called_once()

                # move the cursor onto a different word, then Ctrl+D again
                screen._scorer.position = screen._scorer.target.index("quick")
                await pilot.press("ctrl+d")
                await pilot.pause()
                assert screen._dictionary_word == "quick"
                assert mock_fetch.call_count == 2
                panel = screen.query_one("#dictionary-panel")
                assert not panel.has_focus

    asyncio.run(run())
    storage.close()


def test_escape_while_panel_focused_returns_focus_without_pausing(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                await _wait_for_panel_content(pilot, screen, "a definition")
                await pilot.press("ctrl+d")  # second press on same word -> focuses panel
                await pilot.pause()
                panel = screen.query_one("#dictionary-panel")
                assert panel.has_focus

                await pilot.press("escape")
                await pilot.pause()

                assert not panel.has_focus
                assert not screen._paused
                # definition content is untouched
                content = screen.query_one("#dictionary-panel-content", Static)
                assert "a definition" in str(content.content)

    asyncio.run(run())
    storage.close()


def test_escape_while_typing_focused_still_pauses(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert not screen._paused

            await pilot.press("escape")
            await pilot.pause()

            assert screen._paused

    asyncio.run(run())
    storage.close()


def test_ctrl_shift_d_clears_panel_and_returns_focus(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                await _wait_for_panel_content(pilot, screen, "a definition")
                await pilot.press("ctrl+d")  # focus the panel
                await pilot.pause()
                panel = screen.query_one("#dictionary-panel")
                assert panel.has_focus

                await pilot.press("ctrl+shift+d")
                await pilot.pause()

                assert screen._dictionary_word == ""
                content = screen.query_one("#dictionary-panel-content", Static)
                assert str(content.content) == ""
                assert not panel.has_focus

    asyncio.run(run())
    storage.close()


def test_ctrl_d_strips_punctuation_before_lookup(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg, custom_text="times, and wisdom")

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a moment") as mock_fetch:
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "a moment")
                assert found
                mock_fetch.assert_called_once()
                called_word = mock_fetch.call_args[0][0]
                assert called_word == "times"
                # the panel's stored display word keeps the original, unstripped form
                assert screen._dictionary_word == "times,"

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
                assert screen._dictionary_word == ""
                mock_fetch.assert_not_called()

    asyncio.run(run())
    storage.close()


def test_ctrl_d_survives_fetch_definition_raising_and_resets_in_progress_flag(tmp_path):
    storage = Storage(tmp_path / "test.db")
    cfg = AppConfig(content_type="custom", key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            with patch("typingapp.screens.lesson.fetch_definition", side_effect=RuntimeError("boom")):
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "No definition found.")
                assert found
                assert not screen._dictionary_lookup_in_progress

            # move to a different word so this is treated as a fresh lookup, not a focus-toggle
            screen._dictionary_word = ""  # force re-lookup path deterministically
            with patch("typingapp.screens.lesson.fetch_definition", return_value="(noun) a fast animal") as mock_fetch:
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "fast animal")
                assert found
                mock_fetch.assert_called_once()

    asyncio.run(run())
    storage.close()


def test_dictionary_panel_persists_across_book_page_jump(tmp_path):
    from typingapp.engine.book_text import CHARS_PER_PAGE

    BOOK_ID = "gutenberg:1"
    storage = Storage(tmp_path / "test.db")
    words = [f"word{i}." if i % 8 == 7 else f"word{i}" for i in range(2000)]
    storage.upsert_book(
        book_id=BOOK_ID, source="gutenberg", title="T", author="A",
        language="en", full_text=" ".join(words), cached_at="2026-07-28T10:00:00",
    )
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        with patch("typingapp.screens.lesson.fetch_definition", return_value="a definition"):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = app.screen
                await pilot.press("ctrl+d")
                found = await _wait_for_panel_content(pilot, screen, "a definition")
                assert found

                screen.action_next_page()
                await pilot.pause()

                content = screen.query_one("#dictionary-panel-content", Static)
                assert "a definition" in str(content.content)

    asyncio.run(run())
    storage.close()
