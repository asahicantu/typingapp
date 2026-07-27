import asyncio
from pathlib import Path
from textual.app import App

APP_TCSS_PATH = str(Path(__file__).resolve().parent.parent / "typingapp" / "app.tcss")

from typingapp.config import AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.scorer import Scorer
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


def test_book_mode_paragraph_highlights_only_the_missed_word(tmp_path):
    # regression: _style_paragraph_punctuation used to check membership of the ENTIRE
    # multi-word segment string (the run of text between punctuation marks) against
    # _missed_words, which only ever holds single words — so highlighting silently never
    # fired for realistic book prose. This asserts the specific missed word "jumps" gets
    # wrapped in the #ffb347 highlight color, while its neighboring words in the same
    # comma-delimited segment ("quick", "fox", "over") do NOT.
    storage = Storage(tmp_path / "test.db")
    storage.record_word_mistakes({"jumps": 5})
    book_text = "The quick fox jumps over the lazy dog, and then ran home."
    storage.upsert_book(
        book_id="gutenberg:1", source="gutenberg", title="T", author="A",
        language="en", full_text=book_text, cached_at="2026-07-26T10:00:00",
    )
    cfg = AppConfig(
        content_type="literature", selected_book_id="gutenberg:1",
        session_duration=600, key_sounds=False, highlight_past_mistakes=True,
    )
    app = _make_app(storage, cfg)

    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._start_lesson()
            await pilot.pause()
            assert "jumps" in screen._missed_words
            target = screen._scorer.target
            # style everything after the cursor (position 0) as "rest of paragraph" text
            markup = screen._style_book_rest(target, 0)
            assert "[#ffb347]jumps[/]" in markup
            # the whole multi-word segment must NOT be wrapped in the highlight color —
            # only the single word "jumps" is a member of _missed_words
            assert "[#ffb347]The quick fox jumps over the lazy dog[/]" not in markup
            assert "[#ffb347]quick[/]" not in markup
            assert "[#ffb347]fox[/]" not in markup
            assert "[#ffb347]over[/]" not in markup

    asyncio.run(run())
    storage.close()


def test_punctuation_adjacent_mistake_highlights_in_plain_and_book_mode(tmp_path):
    # Regression: Scorer._word_at splits on spaces only, so a mistake made in
    # "dog," (immediately followed by a comma) used to be stored in
    # word_errors / word_mistakes as the literal "dog," -- WITH the comma.
    # Plain-mode highlighting (_style_rest_with_mistake_highlight) looks up
    # WORD_RE.finditer() tokens directly against _missed_words, so "dog,"
    # (comma attached) would match a "dog," entry but never a clean "dog"
    # entry. Book-mode highlighting (_style_words_with_mistake_highlight)
    # runs on text that PUNCTUATION_SPLIT_RE already split apart, so its
    # tokens arrive punctuation-free ("dog") and would never match a "dog,"
    # entry either. The 3-way mismatch meant a mistake recorded against a
    # punctuation-adjacent word would never re-highlight correctly in at
    # least one of the two rendering paths. normalize_mistake_word() fixes
    # this by being the single normalization used on both the write side
    # (Scorer._word_at) and both read sides (both highlight methods).
    storage = Storage(tmp_path / "test.db")

    # 1. Simulate a real mistake on "dog," via the actual Scorer, exactly as
    #    LessonScreen._finish() would persist it. Mistype it twice (in
    #    strict mode, so each wrong keystroke retries and counts again) to
    #    reach the miss_count >= 2 threshold that fetch_frequently_missed_words
    #    (and thus LessonScreen._start_lesson) uses by default.
    scorer = Scorer("the lazy dog, and then ran home", strict_mode=True)
    scorer.start()
    for ch in "the lazy ":
        scorer.process_key(ch)
    scorer.process_key("x")  # wrong first char of "dog," (retry #1)
    scorer.process_key("x")  # wrong again (retry #2)
    for ch in "dog,":
        scorer.process_key(ch)
    assert scorer.word_errors == {"dog": 2}
    assert "dog," not in scorer.word_errors  # normalized at write time

    storage.record_word_mistakes(scorer.word_errors)
    missed = storage.fetch_frequently_missed_words()  # default min_misses=2
    assert "dog" in missed

    # 2. Plain-mode rendering path: does the punctuation-adjacent token
    #    "dog," (as it appears verbatim in the lesson text) get recognized
    #    as a miss when _missed_words holds the clean "dog"?
    cfg = AppConfig(content_type="custom", key_sounds=False, highlight_past_mistakes=True)
    app = _make_app(storage, cfg)

    async def run_plain():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            screen._custom_text = "the lazy dog, and then ran home"
            screen._start_lesson()
            await pilot.pause()
            assert "dog" in screen._missed_words
            markup = screen._style_rest_with_mistake_highlight("dog, and then ran home")
            assert "[#ffb347]dog,[/]" in markup

    asyncio.run(run_plain())
    storage.close()

    # 3. Book-mode rendering path: same missed-word set, but now the token
    #    arrives already split from its punctuation by PUNCTUATION_SPLIT_RE.
    storage2 = Storage(tmp_path / "test2.db")
    storage2.record_word_mistakes(scorer.word_errors)
    # "dog," must fall outside the book-mode lead-in (first BOOK_LEAD_IN_WORDS
    # words of the paragraph render as plain bold-white text, bypassing
    # mistake highlighting entirely by design), so put extra lead-in words first.
    book_text = "Once upon a time the lazy dog, and then ran home to sleep."
    storage2.upsert_book(
        book_id="gutenberg:1", source="gutenberg", title="T", author="A",
        language="en", full_text=book_text, cached_at="2026-07-26T10:00:00",
    )
    cfg2 = AppConfig(
        content_type="literature", selected_book_id="gutenberg:1",
        session_duration=600, key_sounds=False, highlight_past_mistakes=True,
    )
    app2 = _make_app(storage2, cfg2)

    async def run_book():
        async with app2.run_test() as pilot:
            await pilot.pause()
            screen = app2.screen
            screen._start_lesson()
            await pilot.pause()
            assert "dog" in screen._missed_words
            target = screen._scorer.target
            markup = screen._style_book_rest(target, 0)
            assert "[#ffb347]dog[/]" in markup

    asyncio.run(run_book())
    storage2.close()


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
