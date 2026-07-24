from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import ScrollableContainer

from typingapp.engine.scorer import Scorer
from typingapp.engine.charts import horizontal_bar, ranked_bars


class ResultsScreen(Screen):
    BINDINGS = [
        ("escape", "go_menu", "Menu"),
        ("p", "jump_performance", "Performance"),
        ("b", "jump_bigrams", "Bigrams"),
        ("w", "jump_words", "Words"),
    ]

    def __init__(self, scorer: Scorer, session_id: int) -> None:
        super().__init__()
        self._scorer = scorer
        self._session_id = session_id

    def compose(self) -> ComposeResult:
        s = self._scorer
        session_bigrams = self._session_mistake_bigrams()
        mistaken_words = s.top_mistaken_words(limit=5)

        hint_parts = ["P performance"]
        if session_bigrams:
            hint_parts.append("B bigrams")
        if mistaken_words:
            hint_parts.append("W words")
        section_hint = "Jump to: " + "  ·  ".join(hint_parts)

        with ScrollableContainer():
            yield Static("🏁  Session Complete", classes="menu-title")
            yield Static("Here's how this session went and where to focus next.", classes="section-desc")
            yield Static(section_hint, classes="nav-hint")
            yield Static("")

            yield Static("PERFORMANCE", id="section-performance", classes="section-title")
            yield Static("Your speed and accuracy for this lesson.", classes="section-desc")
            cfg = self.app.config       # type: ignore[attr-defined]
            yield Label(f"⚡ WPM: {s.wpm:.0f}", classes="stat-value wpm-value")
            yield Static(
                horizontal_bar("Accuracy", s.accuracy, 100, value_fmt="{:.1f}%", color="green"),
                classes="stat-value acc-value",
            )
            yield Static(
                horizontal_bar("Time", s.elapsed_seconds, cfg.session_duration,
                               value_fmt=lambda v: f"{int(v) // 60}:{int(v) % 60:02d}", color="cyan"),
                classes="stat-value time-value",
            )
            max_errors = max(s.error_count, len(s.target) // 5, 1)
            yield Static(
                horizontal_bar("Errors", s.error_count, max_errors, value_fmt="{:.0f}", color="magenta"),
                classes="stat-value err-value",
            )
            yield Static("")

            if session_bigrams:
                yield Static("MISTAKE BIGRAMS", id="section-bigrams", classes="section-title")
                yield Static("Two-letter combinations you mistyped most in this session.", classes="section-desc")
                yield Static(ranked_bars(session_bigrams), id="bigram-chart")
                yield Static("")

            if mistaken_words:
                yield Static("MISTAKEN WORDS", id="section-words", classes="section-title")
                yield Static("The words that caused the most keystroke errors this session.", classes="section-desc")
                yield Static(ranked_bars(mistaken_words), id="word-chart")
                yield Static("")

            yield Button("▶  Retry Same", id="btn-retry", variant="primary")
            yield Button("🔀  New Lesson", id="btn-new")
            yield Button("📊  View History", id="btn-history")
            yield Button("🏠  Menu", id="btn-menu")

    def _session_mistake_bigrams(self, limit: int = 5) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for ks in self._scorer.keystrokes:
            if ks.bigram and not ks.correct:
                counts[ks.bigram] = counts.get(ks.bigram, 0) + 1
        return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from typingapp.screens.lesson import LessonScreen
        from typingapp.screens.history import HistoryScreen
        from typingapp.screens.menu import MenuScreen
        if event.button.id == "btn-retry":
            self.app.switch_screen(LessonScreen())
        elif event.button.id == "btn-new":
            self.app.switch_screen(LessonScreen())
        elif event.button.id == "btn-history":
            self.app.push_screen(HistoryScreen())
        elif event.button.id == "btn-menu":
            self.app.switch_screen(MenuScreen())

    def action_go_menu(self) -> None:
        from typingapp.screens.menu import MenuScreen
        self.app.switch_screen(MenuScreen())

    def action_jump_performance(self) -> None:
        self._jump_to("#section-performance")

    def action_jump_bigrams(self) -> None:
        self._jump_to("#section-bigrams")

    def action_jump_words(self) -> None:
        self._jump_to("#section-words")

    def _jump_to(self, selector: str) -> None:
        try:
            target = self.query_one(selector)
        except Exception:
            return
        target.scroll_visible(top=True)
