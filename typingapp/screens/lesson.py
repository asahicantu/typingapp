from __future__ import annotations
import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, ProgressBar
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.timer import Timer

from typingapp.engine.scorer import Scorer
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.lesson import BOOK_COMPLETE_SENTINEL
from typingapp.engine.book_text import page_info
from typingapp.engine.charts import horizontal_bar
from typingapp.data.storage import SessionRecord

BOOK_PROGRESS_PERSIST_TICKS = 80  # ~20s at the 0.25s tick interval


class LessonScreen(Screen):
    BINDINGS = [
        ("escape", "pause", "Pause"),
        ("ctrl+r", "restart", "Restart"),
        ("ctrl+q", "quit_lesson", "Quit"),
        ("ctrl+e", "go_menu", "Main Menu"),
    ]

    def __init__(self, custom_text: str = "") -> None:
        super().__init__()
        self._custom_text = custom_text
        self._scorer: Scorer | None = None
        self._timer: Timer | None = None
        self._paused = False
        self._book_id = ""
        self._book_chunk_start_offset = 0
        self._book_total_chars = 0
        self._book_tick_counter = 0

    def _load_lesson_text(self) -> str:
        app = self.app      # type: ignore[attr-defined]
        cfg = app.config
        adaptive: AdaptiveEngine = app.adaptive
        storage = app.storage
        bigrams = storage.fetch_bigram_heatmap(limit=5)
        weak = [b["bigram"] for b in bigrams]
        recent_wpms = storage.fetch_last_n_wpm(n=5)
        recent_wpm = sum(recent_wpms) / len(recent_wpms) if recent_wpms else 0
        difficulty = cfg.difficulty if cfg.manual_difficulty else adaptive.current_level
        return app.lesson_engine.get_lesson(
            content_type=cfg.content_type,
            difficulty=difficulty,
            custom_text=self._custom_text,
            weak_bigrams=weak,
            language=cfg.language,
            storage=storage,
            recent_wpm=recent_wpm,
            session_duration=cfg.session_duration,
            word_count_override=cfg.word_count_override,
            selected_book_id=cfg.selected_book_id,
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="stats-bar"):
                yield Label("⚡ WPM: ", classes="stat-label")
                yield Label("0", id="wpm-val", classes="stat-value wpm-value")
                yield Label("  ✓ ACC: ", classes="stat-label")
                yield Label("100%", id="acc-val", classes="stat-value acc-value")
                yield Label("  ⏱ TIME: ", classes="stat-label")
                yield Label("0:00", id="time-val", classes="stat-value time-value")
                yield Label("  ✗ ERR: ", classes="stat-label")
                yield Label("0", id="err-val", classes="stat-value err-value")
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            yield Label("", id="book-progress-val", classes="stat-label")
            with VerticalScroll(id="text-scroll"):
                yield Static("", id="text-display")
            yield Label("", id="hint-bar", classes="hint-bar")
            yield Static("ESC pause  ·  Ctrl+R restart  ·  Ctrl+Q quit  ·  Ctrl+E menu", classes="stat-label")

    def on_mount(self) -> None:
        self._start_lesson()

    def _start_lesson(self) -> None:
        app = self.app      # type: ignore[attr-defined]
        text = self._load_lesson_text()
        engine = app.lesson_engine
        self._book_id = engine._last_chunk_book_id
        self._book_chunk_start_offset = engine._last_chunk_start_offset
        self._book_total_chars = 0
        if self._book_id:
            book = app.storage.get_book(self._book_id)
            self._book_total_chars = book["total_chars"] if book else 0

        if text == BOOK_COMPLETE_SENTINEL:
            self._scorer = None
            self.query_one("#text-display", Static).update("🎉 You've finished this book!")
            self.query_one("#hint-bar", Label).update("")
            self._update_book_progress_label()
            return

        self._scorer = Scorer(text, strict_mode=app.config.strict_mode)
        self._scorer.start()
        self._render_text()
        self._timer = self.set_interval(0.25, self._tick)
        self._update_book_progress_label()
        reason = app.lesson_engine.last_fallback_reason
        if reason:
            self.query_one("#hint-bar", Label).update(f"⚠ {reason}")

    def _update_book_progress_label(self) -> None:
        label = self.query_one("#book-progress-val", Label)
        if not self._book_id or self._book_total_chars <= 0:
            label.update("")
            return
        current_offset = self._book_chunk_start_offset + (self._scorer.position if self._scorer else 0)
        page, total_pages, pct = page_info(self._book_total_chars, current_offset)
        bar = horizontal_bar("Progress", pct, 100, width=24, value_fmt=lambda v: f"page {page}/{total_pages}")
        label.update(bar)

    def _persist_book_progress(self) -> None:
        if not self._book_id or self._scorer is None:
            return
        app = self.app      # type: ignore[attr-defined]
        absolute_pos = self._book_chunk_start_offset + self._scorer.position
        app.storage.update_book_progress(
            self._book_id, absolute_pos, datetime.datetime.now().isoformat()
        )

    def _tick(self) -> None:
        if self._paused or self._scorer is None:
            return
        s = self._scorer
        elapsed = s.elapsed_seconds
        mins, secs = divmod(int(elapsed), 60)
        self.query_one("#wpm-val", Label).update(f"{s.wpm:.0f}")
        self.query_one("#acc-val", Label).update(f"{s.accuracy:.1f}%")
        self.query_one("#time-val", Label).update(f"{mins}:{secs:02d}")
        self.query_one("#err-val", Label).update(str(s.error_count))
        pct = int((s.position / max(len(s.target), 1)) * 100)
        self.query_one("#progress-bar", ProgressBar).update(progress=pct)
        self._maybe_extend_text()
        if self._book_id:
            self._update_book_progress_label()
            self._book_tick_counter += 1
            if self._book_tick_counter >= BOOK_PROGRESS_PERSIST_TICKS:
                self._book_tick_counter = 0
                self._persist_book_progress()

    def _maybe_extend_text(self) -> None:
        app = self.app      # type: ignore[attr-defined]
        s = self._scorer
        if s is None:
            return
        cfg = app.config
        time_remaining = cfg.session_duration - s.elapsed_seconds
        chars_remaining = len(s.target) - s.position
        near_end = chars_remaining <= max(20, len(s.target) * 0.15)
        if near_end and time_remaining > 5 and cfg.content_type in ("literature", "random_sentences"):
            if self._book_id:
                # keep the book's stored offset in sync with what's already been fetched (end of
                # target, not just what's been typed) so the next chunk continues contiguously
                app.storage.update_book_progress(
                    self._book_id, self._book_chunk_start_offset + len(s.target),
                    datetime.datetime.now().isoformat(),
                )
            try:
                more_text = app.lesson_engine.get_lesson(
                    content_type=cfg.content_type,
                    difficulty=app.adaptive.current_level,
                    language=cfg.language,
                    storage=app.storage,
                    recent_wpm=s.wpm,
                    session_duration=max(int(time_remaining), 15),
                    selected_book_id=cfg.selected_book_id,
                )
            except Exception:
                more_text = ""
            reason = app.lesson_engine.last_fallback_reason
            if reason:
                self.query_one("#hint-bar", Label).update(f"⚠ {reason}")
            if more_text and more_text != BOOK_COMPLETE_SENTINEL:
                # book-mode chunks continue at an exact character offset in the book's text, so no
                # separator is inserted; non-book modes join separate excerpts with a space
                s.extend(more_text if self._book_id else " " + more_text)

    def _render_text(self) -> None:
        if self._scorer is None:
            return
        s = self._scorer
        target = s.target
        pos = s.position
        typed = f"[bold green]{target[:pos]}[/]"
        cursor = ""
        rest = ""
        if pos < len(target):
            cursor = f"[bold on red]{target[pos]}[/]"
            rest = f"[dim]{target[pos+1:]}[/]"
        display = self.query_one("#text-display", Static)
        display.update(typed + cursor + rest)
        self._scroll_to_cursor(pos, len(target))

    def _scroll_to_cursor(self, position: int, target_length: int) -> None:
        if target_length == 0:
            return
        scroll_container = self.query_one("#text-scroll", VerticalScroll)
        display = self.query_one("#text-display", Static)
        width = display.size.width or scroll_container.size.width
        if width <= 0:
            return
        content_height = display.get_content_height(scroll_container.size, self.size, width)
        if content_height <= 0:
            return
        progress_ratio = position / target_length
        target_scroll_y = max(0, int(content_height * progress_ratio) - int(scroll_container.size.height / 3))
        scroll_container.scroll_to(y=target_scroll_y, animate=False)

    def on_key(self, event) -> None:
        if self._scorer is None or self._paused or self._scorer.is_complete:
            return
        key = event.character
        if key is None or len(key) != 1:
            return
        correct = self._scorer.process_key(key)
        self._render_text()
        app = self.app          # type: ignore[attr-defined]
        if app.config.key_sounds:
            if correct:
                app.sound.play_correct()
            else:
                app.sound.play_error()
        if app.config.show_hints:
            weak = app.adaptive.detect_weak_bigrams(self._scorer.keystrokes)
            if weak:
                self.query_one("#hint-bar", Label).update(
                    f"💡 Struggling with '{weak[0]}' — slow down slightly to build accuracy"
                )
            else:
                self.query_one("#hint-bar", Label).update("")
        if self._scorer.is_complete:
            self._finish()

    def _finish(self) -> None:
        if self._timer:
            self._timer.stop()
        self._persist_book_progress()
        s = self._scorer
        app = self.app          # type: ignore[attr-defined]
        if app.config.manual_difficulty:
            session_difficulty = app.config.difficulty
        else:
            session_difficulty = app.adaptive.update_level(s.wpm, s.accuracy)
            app.config.difficulty = session_difficulty
        rec = SessionRecord(
            timestamp=datetime.datetime.now().isoformat(),
            content_type=app.config.content_type,
            difficulty=session_difficulty,
            duration_seconds=int(s.elapsed_seconds),
            wpm=round(s.wpm, 2),
            accuracy=round(s.accuracy, 2),
            error_count=s.error_count,
            strict_mode=app.config.strict_mode,
        )
        session_id = app.storage.insert_session(rec)
        app.storage.insert_keystrokes(session_id, s.keystrokes)
        from typingapp.screens.results import ResultsScreen
        self.app.switch_screen(ResultsScreen(scorer=s, session_id=session_id))

    def action_pause(self) -> None:
        self._paused = not self._paused
        hint = self.query_one("#hint-bar", Label)
        hint.update("⏸ PAUSED — press ESC to resume" if self._paused else "")

    def action_restart(self) -> None:
        if self._timer:
            self._timer.stop()
        self._start_lesson()

    def action_quit_lesson(self) -> None:
        if self._timer:
            self._timer.stop()
        self._persist_book_progress()
        self.app.pop_screen()

    def action_go_menu(self) -> None:
        if self._timer:
            self._timer.stop()
        self._persist_book_progress()
        from typingapp.screens.menu import MenuScreen
        self.app.switch_screen(MenuScreen())
