import asyncio
from pathlib import Path
from textual.app import App
from textual.containers import VerticalScroll
from textual.widgets import Label

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.book_text import CHARS_PER_PAGE
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.sound import SoundPlayer
from typingapp.screens.lesson import LessonScreen

BOOK_ID = "gutenberg:1"


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


def _make_storage_with_book(tmp_path, total_words=2000):
    storage = Storage(tmp_path / "test.db")
    # plenty of words so total_chars comfortably exceeds several pages. Sentence-ending
    # punctuation every few words matters here: chunk_from_offset's oversized-block
    # fallback (_cut_oversized_block) can only cut a chunk short at a sentence boundary,
    # so a corpus with none of that would return the ENTIRE book as a single chunk
    # (no room to observe a real chunk boundary or trigger _maybe_extend_text within it).
    words = [f"word{i}." if i % 8 == 7 else f"word{i}" for i in range(total_words)]
    full_text = " ".join(words)
    storage.upsert_book(
        book_id=BOOK_ID, source="gutenberg", title="T", author="A",
        language="en", full_text=full_text, cached_at="2026-07-28T10:00:00",
    )
    return storage


def test_next_page_advances_progress_by_one_page_without_scoring_skipped_text(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            start_offset = screen._book_raw_offset(0)
            assert start_offset == 0

            screen.action_next_page()
            await pilot.pause()

            new_offset = storage.fetch_book_progress(BOOK_ID)
            assert new_offset == start_offset + CHARS_PER_PAGE
            # a fresh Scorer was built for the new chunk -- no keystrokes recorded
            assert screen._scorer is not None
            assert screen._scorer.keystrokes == []
            assert screen._scorer.error_count == 0

    asyncio.run(run())
    storage.close()


def test_previous_page_moves_progress_back_by_one_page(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # jump forward two pages first so there's room to go back
            screen.action_next_page()
            await pilot.pause()
            screen.action_next_page()
            await pilot.pause()
            offset_after_two = storage.fetch_book_progress(BOOK_ID)

            screen.action_previous_page()
            await pilot.pause()

            offset_after_back = storage.fetch_book_progress(BOOK_ID)
            assert offset_after_back == offset_after_two - CHARS_PER_PAGE

    asyncio.run(run())
    storage.close()


def test_previous_page_clamps_at_zero_not_negative(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_previous_page()
            await pilot.pause()

            assert storage.fetch_book_progress(BOOK_ID) == 0

    asyncio.run(run())
    storage.close()


def test_book_home_jumps_to_offset_zero(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen.action_next_page()
            await pilot.pause()
            screen.action_next_page()
            await pilot.pause()
            assert storage.fetch_book_progress(BOOK_ID) > 0

            screen.action_book_home()
            await pilot.pause()

            assert storage.fetch_book_progress(BOOK_ID) == 0

    asyncio.run(run())
    storage.close()


def test_next_page_past_end_of_book_shows_book_complete(tmp_path):
    storage = _make_storage_with_book(tmp_path, total_words=50)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            book = storage.get_book(BOOK_ID)
            total_chars = book["total_chars"]

            # jump repeatedly until we've gone past the end
            for _ in range(20):
                screen.action_next_page()
                await pilot.pause()
                if storage.fetch_book_progress(BOOK_ID) >= total_chars:
                    break

            assert storage.fetch_book_progress(BOOK_ID) >= total_chars
            assert screen._scorer is None

    asyncio.run(run())
    storage.close()


def test_page_nav_is_a_no_op_outside_book_mode(tmp_path):
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
            self.push_screen(LessonScreen(custom_text="hello world"))

    app = TestApp()

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            target_before = screen._scorer.target
            pos_before = screen._scorer.position

            screen.action_next_page()
            await pilot.pause()
            screen.action_previous_page()
            await pilot.pause()
            screen.action_book_home()
            await pilot.pause()

            # unchanged -- these actions must no-op when there's no book_id
            assert screen._scorer.target == target_before
            assert screen._scorer.position == pos_before

    asyncio.run(run())
    storage.close()


def test_next_page_after_extension_advances_forward_not_backward(tmp_path):
    # Regression test for the bug where action_next_page computed its base offset from
    # the scorer's cursor position (_book_raw_offset(scorer.position)) instead of the
    # persisted offset. _maybe_extend_text persists a DIFFERENT, further-along offset
    # (_book_raw_offset(len(scorer.target)), i.e. chunk-end) every time it tops up text
    # near the end of a chunk -- which happens routinely during normal reading, not as a
    # rare edge case. Once that has fired, the cursor-based offset is behind what's
    # already been persisted, so a naive "current_offset + CHARS_PER_PAGE" computation
    # from the cursor lands BEHIND the already-persisted offset -- i.e. pressing "next
    # page" moves progress backward. This test drives a real extension (by moving the
    # cursor near the chunk boundary and calling _maybe_extend_text directly, per the
    # task's suggested approach) and asserts the jump is strictly forward relative to the
    # already-persisted (post-extension) offset, not the stale cursor-based one.
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            s = screen._scorer
            assert s is not None
            chunk_len = len(s.target)

            # Move the cursor to just inside the "near end of chunk" trigger zone
            # (chars_remaining <= max(20, len(target) * 0.15)) without actually typing
            # every character -- position is a plain public attribute on Scorer.
            near_end_position = chunk_len - max(20, int(chunk_len * 0.15)) + 1
            s.position = near_end_position

            # Drive the extension directly (this is what _tick() does every 0.25s).
            screen._maybe_extend_text()
            await pilot.pause()

            persisted_after_extension = storage.fetch_book_progress(BOOK_ID)
            cursor_based_offset = screen._book_raw_offset(s.position)

            # Sanity-check the premise of the bug: the extension must have advanced
            # storage strictly ahead of where the cursor-based computation would put it.
            assert persisted_after_extension > cursor_based_offset
            assert len(s.target) > chunk_len  # text really was extended

            # Now perform the actual page jump and confirm it moves forward relative to
            # the offset that was ALREADY persisted by the extension -- not backward.
            # The old, buggy computation (cursor_based_offset + CHARS_PER_PAGE) would be
            # LESS than persisted_after_extension here, i.e. a regression; this asserts
            # the jump lands exactly CHARS_PER_PAGE forward of the pre-jump persisted
            # value instead.
            screen.action_next_page()
            await pilot.pause()

            new_offset = storage.fetch_book_progress(BOOK_ID)
            assert new_offset == persisted_after_extension + CHARS_PER_PAGE

    asyncio.run(run())
    storage.close()


def test_page_jump_scrolls_back_to_top_even_when_content_height_unavailable(tmp_path):
    # Regression test: _scroll_to_cursor's ratio-based math silently no-ops (leaving
    # whatever scroll position the PREVIOUS chunk left behind) whenever the display
    # widget reports a non-positive width/content_height -- which is exactly the state
    # a freshly-rebuilt screen can be in for its first render after a page jump (see
    # the get_content_height gotcha documented in CLAUDE.md). That silent no-op is
    # what made "next page" look like it landed on the last word/section the user had
    # typed instead of resetting to the top of the new page. Position 0 (always true
    # immediately after a page jump) must scroll to the top unconditionally, without
    # going through that ratio math at all.
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            scroll_container = screen.query_one("#text-scroll", VerticalScroll)

            # spy on scroll_to so this test verifies _scroll_to_cursor's own decision
            # (does it call scroll_to(y=0) at all?) rather than fighting Textual's
            # internal scroll_y clamping, which this short test corpus's small content
            # height would otherwise make indistinguishable from "never scrolled".
            calls = []
            scroll_container.scroll_to = lambda *a, **k: calls.append(k)

            # simulate the widget not being laid out yet on this render -- the exact
            # condition CLAUDE.md warns about: get_content_height returns 0 whenever
            # width is falsy, which the OLD implementation of _scroll_to_cursor treated
            # as "nothing to do" and returned without calling scroll_to at all, silently
            # leaving whatever scroll position the previous chunk had left behind
            # instead of resetting to the top of the new page.
            display = screen.query_one("#text-display")
            display.get_content_height = lambda *a, **k: 0

            screen._scroll_to_cursor(0, len(screen._scorer.target))

            assert calls == [{"y": 0, "animate": False}]

    asyncio.run(run())
    storage.close()


def test_accuracy_after_page_skip_reflects_only_typed_text(tmp_path):
    storage = _make_storage_with_book(tmp_path)
    cfg = AppConfig(content_type="literature", selected_book_id=BOOK_ID, key_sounds=False)
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen

            # Type into the CURRENT (pre-jump) chunk first, including a deliberate
            # wrong keystroke, so there is real keystroke/error state in play before
            # the jump -- a buggy implementation that reused/leaked Scorer state
            # across the jump would show up here, unlike a scenario that jumps
            # before typing anything at all.
            pre_jump_target = screen._scorer.target
            # deliberate mistake: press a char that doesn't match position 0 ("w" of
            # "word0..."). strict_mode is off by default, so position still advances
            # to 1 even though this keystroke was wrong.
            wrong_char = "z" if pre_jump_target[0] != "z" else "y"
            await pilot.press(wrong_char)
            # follow up with whatever IS correct for the new position (1), to keep
            # typing normally in the chunk we're about to abandon.
            second_char = pre_jump_target[1]
            await pilot.press(second_char if second_char != " " else "space")
            await pilot.pause()
            assert screen._scorer.error_count == 1
            assert len(screen._scorer.keystrokes) == 2

            # Now skip a page -- this pre-jump chunk (with its real mistake) must
            # never leak into the next chunk's Scorer.
            screen.action_next_page()
            await pilot.pause()

            target = screen._scorer.target
            # type the first few characters correctly in the NEW chunk
            for ch in target[:5]:
                await pilot.press(ch if ch != " " else "space")
            await pilot.pause()

            # The post-jump Scorer must start completely fresh: only the 5
            # correctly-typed keystrokes above show up, and the wrong keystroke
            # typed into the skipped chunk is nowhere to be found.
            assert screen._scorer.error_count == 0
            assert screen._scorer.accuracy == 100.0
            assert len(screen._scorer.keystrokes) == 5

    asyncio.run(run())
    storage.close()
