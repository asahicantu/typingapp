from __future__ import annotations
import datetime
import re
from textual import work
from textual.markup import escape
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, ProgressBar
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.timer import Timer

from typingapp.engine.scorer import Scorer, normalize_mistake_word, current_word_at, current_char_at
from typingapp.engine.keyboard_map import finger_for_char
from typingapp.engine.adaptive import AdaptiveEngine
from typingapp.engine.lesson import BOOK_COMPLETE_SENTINEL
from typingapp.engine.book_text import page_info, strip_heading_markup, CHARS_PER_PAGE
from typingapp.engine.keyboard_sanitize import sanitize_for_keyboard
from typingapp.engine.charts import horizontal_bar
from typingapp.engine.dictionary import fetch_definition
from typingapp.data.storage import SessionRecord
from typingapp.config import save_config
from typingapp.screens.dictionary_popup import DictionaryPopupScreen

BOOK_PROGRESS_PERSIST_TICKS = 80  # ~20s at the 0.25s tick interval
BOOK_LEAD_IN_WORDS = 3
WORD_RE = re.compile(r"\S+")
PUNCTUATION_SPLIT_RE = re.compile(r'([.,;:!?—"\'])')


class LessonScreen(Screen):
    BINDINGS = [
        ("escape", "pause", "Pause"),
        ("ctrl+r", "restart", "Restart"),
        ("ctrl+q", "quit_lesson", "Quit"),
        ("ctrl+e", "go_menu", "Main Menu"),
        ("ctrl+f", "finish_session", "Finish Session"),
        ("ctrl+s", "toggle_strict_mode", "Toggle Strict Mode"),
        ("ctrl+k", "toggle_key_sounds", "Toggle Key Sounds"),
        ("ctrl+right", "next_page", "Next Page"),
        ("ctrl+left", "previous_page", "Previous Page"),
        ("ctrl+home", "book_home", "Book Start"),
        ("ctrl+d", "show_definition", "Dictionary"),
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
        self._book_chunk_spans: list[tuple[str, int, int]] = []
        self._missed_words: set[str] = set()
        self._dictionary_lookup_in_progress = False

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
        text = app.lesson_engine.get_lesson(
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
        if text == BOOK_COMPLETE_SENTINEL:
            return text
        return sanitize_for_keyboard(text)

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
            yield Label("", id="finger-hint-val", classes="stat-label finger-hint-value")
            yield ProgressBar(total=100, show_eta=False, id="progress-bar")
            yield Label("", id="book-progress-val", classes="stat-label")
            with VerticalScroll(id="text-scroll"):
                yield Static("", id="text-display")
            yield Label("", id="hint-bar", classes="hint-bar")
            yield Static("ESC pause  ·  Ctrl+R restart  ·  Ctrl+Q quit  ·  Ctrl+E menu", id="footer-hint", classes="stat-label")

    def on_mount(self) -> None:
        self._start_lesson()

    def _start_lesson(self) -> None:
        app = self.app      # type: ignore[attr-defined]
        self._dictionary_lookup_in_progress = False
        if app.config.highlight_past_mistakes:
            self._missed_words = app.storage.fetch_frequently_missed_words()
        else:
            self._missed_words = set()
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
            self._book_chunk_spans = []
            self.query_one("#text-display", Static).update("🎉 You've finished this book!")
            self.query_one("#hint-bar", Label).update("")
            self._update_book_progress_label()
            self._update_finger_hint_label()
            return

        if self._book_id:
            # '# ' heading markers are markup, not text the user should have to type — strip
            # them and keep the resulting spans (in stripped-text offsets) for rendering/progress
            text, self._book_chunk_spans = strip_heading_markup(text)
        else:
            self._book_chunk_spans = []

        self._scorer = Scorer(text, strict_mode=app.config.strict_mode)
        self._scorer.start()
        self._render_text()
        self._update_finger_hint_label()
        self._timer = self.set_interval(0.25, self._tick)
        self._update_book_progress_label()
        self.query_one("#footer-hint", Static).update(self._footer_hint_text())
        reason = app.lesson_engine.last_fallback_reason
        if reason:
            self.query_one("#hint-bar", Label).update(f"⚠ {reason}")

    def _book_raw_offset(self, stripped_pos: int) -> int:
        # spans are in stripped-text offsets; each heading we've reached had a 2-char '# ' marker
        # in the original book text that isn't in the typed string, so add it back per heading
        marker_chars = sum(
            2 for kind, start, _end in self._book_chunk_spans if kind == "heading" and start <= stripped_pos
        )
        return self._book_chunk_start_offset + stripped_pos + marker_chars

    def _footer_hint_text(self) -> str:
        base = ("ESC pause  ·  Ctrl+R restart  ·  Ctrl+S strict  ·  Ctrl+K sound  ·  "
                "Ctrl+D dictionary  ·  Ctrl+Q quit  ·  Ctrl+E menu")
        if self._book_id:
            return ("ESC pause  ·  Ctrl+R restart  ·  Ctrl+F finish  ·  "
                    "Ctrl+←/→ page  ·  Ctrl+Home start  ·  "
                    "Ctrl+S strict  ·  Ctrl+K sound  ·  Ctrl+D dictionary  ·  "
                    "Ctrl+Q quit  ·  Ctrl+E menu")
        return base

    def _update_book_progress_label(self) -> None:
        label = self.query_one("#book-progress-val", Label)
        if not self._book_id or self._book_total_chars <= 0:
            label.update("")
            return
        current_offset = self._book_raw_offset(self._scorer.position if self._scorer else 0)
        page, total_pages, pct = page_info(self._book_total_chars, current_offset)
        bar = horizontal_bar("Progress", pct, 100, width=24, value_fmt=lambda v: f"page {page}/{total_pages}")
        label.update(bar)

    def _update_finger_hint_label(self) -> None:
        label = self.query_one("#finger-hint-val", Label)
        s = self._scorer
        if s is None or s.is_complete:
            label.update("")
            return
        word = current_word_at(s.target, s.position)
        if not word:
            # cursor is on whitespace (e.g. the next key to press is space/enter) --
            # show the upcoming word instead of blanking the hint.
            lookahead = s.position
            while lookahead < len(s.target) and s.target[lookahead].isspace():
                lookahead += 1
            word = current_word_at(s.target, lookahead)
        next_char_label = current_char_at(s.target, s.position)
        finger = finger_for_char(s.target[s.position])
        if not word or finger is None:
            label.update("")
            return
        hand, digit = finger
        label.update(f"Next word: {word}  ·  next key {next_char_label!r} → {hand} {digit}")

    def _persist_book_progress(self) -> None:
        if not self._book_id or self._scorer is None:
            return
        app = self.app      # type: ignore[attr-defined]
        absolute_pos = self._book_raw_offset(self._scorer.position)
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
        self._update_finger_hint_label()
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
        chars_remaining = len(s.target) - s.position
        near_end = chars_remaining <= max(20, len(s.target) * 0.15)
        if not near_end or cfg.content_type not in ("literature", "random_sentences"):
            return

        # Book mode is open-ended (the user decides when to stop, not a fixed session
        # duration), so it always tops up more text near the end regardless of the
        # configured session_duration. Non-book literature/random-sentences extension
        # still respects the session clock and stops topping up once time's nearly up.
        if self._book_id:
            time_budget = cfg.session_duration
        else:
            time_remaining = cfg.session_duration - s.elapsed_seconds
            if time_remaining <= 5:
                return
            time_budget = max(int(time_remaining), 15)

        if self._book_id:
            # keep the book's stored offset in sync with what's already been fetched (end of
            # target, not just what's been typed) so the next chunk continues contiguously
            app.storage.update_book_progress(
                self._book_id, self._book_raw_offset(len(s.target)),
                datetime.datetime.now().isoformat(),
            )
        try:
            more_text = app.lesson_engine.get_lesson(
                content_type=cfg.content_type,
                difficulty=app.adaptive.current_level,
                language=cfg.language,
                storage=app.storage,
                recent_wpm=s.wpm,
                session_duration=time_budget,
                selected_book_id=cfg.selected_book_id,
            )
        except Exception:
            more_text = ""
        reason = app.lesson_engine.last_fallback_reason
        if reason:
            self.query_one("#hint-bar", Label).update(f"⚠ {reason}")
        if more_text == BOOK_COMPLETE_SENTINEL:
            self.query_one("#hint-bar", Label).update("🎉 You've reached the end of this book!")
            return
        if more_text:
            more_text = sanitize_for_keyboard(more_text)
        if more_text:
            if self._book_id:
                # book-mode chunks continue at an exact character offset in the book's text,
                # so no separator is inserted; strip '# ' markers the same way _start_lesson
                # does, offsetting the new spans past the text already in the target
                more_stripped, more_spans = strip_heading_markup(more_text)
                base = len(s.target)
                self._book_chunk_spans.extend(
                    (kind, base + start, base + end) for kind, start, end in more_spans
                )
                s.extend(more_stripped)
            else:
                # non-book modes join separate excerpts with a space
                s.extend(" " + more_text)

    def _render_text(self) -> None:
        if self._scorer is None:
            return
        if self._book_id:
            self._render_book_text()
            return
        s = self._scorer
        target = s.target
        pos = s.position
        typed = f"[bold green]{target[:pos]}[/]"
        cursor = ""
        rest = ""
        if pos < len(target):
            cursor = f"[bold on red]{target[pos]}[/]"
            rest = self._style_rest_with_mistake_highlight(target[pos+1:])
        display = self.query_one("#text-display", Static)
        display.update(typed + cursor + rest)
        self._scroll_to_cursor(pos, len(target))

    def _style_rest_with_mistake_highlight(self, text: str) -> str:
        if not self._missed_words:
            return f"[dim]{text}[/]"
        parts: list[str] = []
        cursor = 0
        for match in WORD_RE.finditer(text):
            word = match.group()
            if cursor < match.start():
                parts.append(f"[dim]{text[cursor:match.start()]}[/]")
            if normalize_mistake_word(word) in self._missed_words:
                parts.append(f"[dim][#ffb347]{word}[/][/]")
            else:
                parts.append(f"[dim]{word}[/]")
            cursor = match.end()
        if cursor < len(text):
            parts.append(f"[dim]{text[cursor:]}[/]")
        return "".join(parts)

    def _render_book_text(self) -> None:
        s = self._scorer
        target = s.target
        pos = s.position
        typed = f"[bold green]{escape(target[:pos])}[/]"
        cursor = ""
        rest_markup = ""
        if pos < len(target):
            cursor = f"[bold on red]{escape(target[pos])}[/]"
            rest_markup = self._style_book_rest(target, pos + 1)
        display = self.query_one("#text-display", Static)
        display.update(typed + cursor + rest_markup)
        self._scroll_to_cursor(pos, len(target))

    def _style_book_rest(self, target: str, rest_start: int) -> str:
        if rest_start >= len(target):
            return ""
        parts: list[str] = []
        cursor_pos = rest_start
        for kind, start, end in self._book_chunk_spans:
            if end <= rest_start:
                continue
            if start > cursor_pos:
                parts.append(escape(target[cursor_pos:start]))
            clipped_start = max(start, rest_start)
            clipped_text = target[clipped_start:end]
            if clipped_text:
                if kind == "heading":
                    parts.append(f"[bold italic gold3]{escape(clipped_text)}[/]")
                elif clipped_start == start:
                    parts.append(self._style_paragraph_lead_in(clipped_text))
                else:
                    parts.append(self._style_paragraph_punctuation(clipped_text))
            cursor_pos = end
        if cursor_pos < len(target):
            parts.append(escape(target[cursor_pos:]))
        return "".join(parts)

    def _style_paragraph_lead_in(self, text: str) -> str:
        words = list(WORD_RE.finditer(text))
        if not words:
            return self._style_paragraph_punctuation(text)
        lead_end = words[min(BOOK_LEAD_IN_WORDS, len(words)) - 1].end()
        lead, remainder = text[:lead_end], text[lead_end:]
        remainder_markup = self._style_paragraph_punctuation(remainder) if remainder else ""
        return f"[bold white]{escape(lead)}[/]" + remainder_markup

    def _style_paragraph_punctuation(self, text: str) -> str:
        parts: list[str] = []
        for segment in PUNCTUATION_SPLIT_RE.split(text):
            if not segment:
                continue
            if PUNCTUATION_SPLIT_RE.fullmatch(segment):
                parts.append(f"[#888888]{escape(segment)}[/]")
            else:
                parts.append(self._style_words_with_mistake_highlight(segment))
        return "".join(parts)

    def _style_words_with_mistake_highlight(self, segment: str) -> str:
        parts: list[str] = []
        cursor = 0
        for match in WORD_RE.finditer(segment):
            word = match.group()
            if cursor < match.start():
                parts.append(f"[dim]{escape(segment[cursor:match.start()])}[/]")
            if normalize_mistake_word(word) in self._missed_words:
                parts.append(f"[dim][#ffb347]{escape(word)}[/][/]")
            else:
                parts.append(f"[dim]{escape(word)}[/]")
            cursor = match.end()
        if cursor < len(segment):
            parts.append(f"[dim]{escape(segment[cursor:])}[/]")
        return "".join(parts)

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
        self._update_finger_hint_label()
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
            if self._book_id:
                # Book mode is open-ended by design: reaching the end of the current chunk
                # just means _tick()'s _maybe_extend_text will fetch the next one on the
                # next tick — the user decides when to stop via Ctrl+F/Ctrl+Q/Ctrl+E. Persist
                # progress right away rather than waiting on the periodic tick timer, so it's
                # never stale even if the user quits before the next tick fires.
                self._persist_book_progress()
            else:
                # Non-book lessons are a fixed amount of text — finishing it ends the session.
                self._finish()

    def _finish(self) -> None:
        if self._timer:
            self._timer.stop()
        self._persist_book_progress()
        app = self.app          # type: ignore[attr-defined]
        if self._scorer is not None:
            app.storage.record_word_mistakes(self._scorer.word_errors)
        s = self._scorer
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
        self.app.switch_screen(ResultsScreen(scorer=s, session_id=session_id, book_id=self._book_id))

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
        self._dictionary_lookup_in_progress = False
        self.app.pop_screen()

    def action_finish_session(self) -> None:
        # Book mode never auto-finishes on chunk completion (see on_key) — this is the
        # explicit "I'm done for now" action. A no-op outside book mode: non-book lessons
        # already finish themselves when the fixed amount of text is fully typed.
        if self._book_id and self._scorer is not None:
            self._finish()

    def _jump_to_book_offset(self, new_offset: int) -> None:
        app = self.app          # type: ignore[attr-defined]
        book = app.storage.get_book(self._book_id)
        total_chars = book["total_chars"] if book else 0
        clamped_offset = max(0, min(new_offset, total_chars))
        app.storage.update_book_progress(
            self._book_id, clamped_offset, datetime.datetime.now().isoformat()
        )
        if self._timer:
            self._timer.stop()
        self._book_tick_counter = 0
        self._start_lesson()

    def _current_book_offset(self) -> int:
        # The authoritative "how far this book has progressed" is whichever is further
        # along: the last value persisted to storage, or the live cursor position.
        #
        # Storage can be AHEAD of the cursor: _maybe_extend_text persists the *chunk-end*
        # offset (_book_raw_offset(len(s.target))) every time it tops up text near the end
        # of a chunk — which happens routinely during normal reading — while the cursor
        # (s.position) hasn't caught up to that chunk end yet. Using the cursor alone here
        # would compute a stale, regressed offset (the original bug).
        #
        # But storage can also be BEHIND the cursor: right after a lesson starts, or before
        # the periodic 80-tick persist / next extension fires, the user may have typed
        # forward without any write having happened yet — storage still holds the offset
        # the chunk was seeded from. Using storage alone in that window would also regress.
        #
        # Taking the max of both is safe in all cases since neither is unconditionally
        # authoritative.
        app = self.app      # type: ignore[attr-defined]
        stored_offset = app.storage.fetch_book_progress(self._book_id) if self._book_id else 0
        cursor_offset = self._book_raw_offset(self._scorer.position if self._scorer else 0)
        return max(stored_offset, cursor_offset)

    def action_next_page(self) -> None:
        if not self._book_id:
            return
        current_offset = self._current_book_offset()
        self._jump_to_book_offset(current_offset + CHARS_PER_PAGE)

    def action_previous_page(self) -> None:
        if not self._book_id:
            return
        current_offset = self._current_book_offset()
        self._jump_to_book_offset(current_offset - CHARS_PER_PAGE)

    def action_book_home(self) -> None:
        if not self._book_id:
            return
        self._jump_to_book_offset(0)

    def action_toggle_strict_mode(self) -> None:
        app = self.app          # type: ignore[attr-defined]
        app.config.strict_mode = not app.config.strict_mode
        save_config(app.config)
        state = "ON" if app.config.strict_mode else "OFF"
        self.query_one("#hint-bar", Label).update(f"Strict mode: {state}")
        if self._scorer is not None:
            self._scorer.strict_mode = app.config.strict_mode

    def action_toggle_key_sounds(self) -> None:
        app = self.app          # type: ignore[attr-defined]
        app.config.key_sounds = not app.config.key_sounds
        save_config(app.config)
        state = "ON" if app.config.key_sounds else "OFF"
        self.query_one("#hint-bar", Label).update(f"Key sounds: {state}")

    def action_show_definition(self) -> None:
        s = self._scorer
        if s is None or s.is_complete:
            return
        if self._dictionary_lookup_in_progress or isinstance(self.app.screen, DictionaryPopupScreen):
            return
        app = self.app      # type: ignore[attr-defined]
        language = app.config.language
        word = current_word_at(s.target, s.position)
        if not word:
            lookahead = s.position
            while lookahead < len(s.target) and s.target[lookahead].isspace():
                lookahead += 1
            word = current_word_at(s.target, lookahead)
        if not word:
            return
        lookup_word = normalize_mistake_word(word)
        if not lookup_word:
            return
        if language != "en":
            self.app.push_screen(DictionaryPopupScreen(
                word=word, definition=None,
                unavailable_reason="Dictionary not available for this language yet",
            ))
            return
        self._dictionary_lookup_in_progress = True
        self._lookup_definition(word, lookup_word, language)

    @work(exclusive=True, thread=True, group="dictionary-lookup")
    def _lookup_definition(self, display_word: str, lookup_word: str, language: str) -> None:
        definition = fetch_definition(lookup_word, language)
        self.app.call_from_thread(self._show_definition_popup, display_word, definition)

    def _show_definition_popup(self, word: str, definition: str | None) -> None:
        self._dictionary_lookup_in_progress = False
        self.app.push_screen(DictionaryPopupScreen(word, definition))

    def action_go_menu(self) -> None:
        if self._timer:
            self._timer.stop()
        self._persist_book_progress()
        self._dictionary_lookup_in_progress = False
        from typingapp.screens.menu import MenuScreen
        self.app.switch_screen(MenuScreen())
