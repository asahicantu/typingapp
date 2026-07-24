from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import ScrollableContainer, Horizontal, VerticalScroll

from typingapp.engine.scorer import Scorer
from typingapp.engine.charts import horizontal_bar, ranked_bars


def _accuracy_color(accuracy: float) -> str:
    if accuracy < 80:
        return "red"
    if accuracy < 95:
        return "yellow"
    return "green"


class ResultsScreen(Screen):
    BINDINGS = [
        ("escape", "go_menu", "Menu"),
        ("p", "jump_performance", "Performance"),
        ("b", "jump_bigrams", "Bigrams"),
        ("w", "jump_words", "Words"),
        ("right", "focus_next_card", "Next Card"),
        ("left", "focus_previous_card", "Previous Card"),
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
        section_hint = "Jump to: " + "  ·  ".join(hint_parts) + "  ·  ←→ switch card  ·  ↑↓ scroll"

        with ScrollableContainer():
            yield Static("🏁  Session Complete", classes="menu-title")
            yield Static("Here's how this session went and where to focus next.", classes="section-desc")
            yield Static(section_hint, classes="nav-hint")
            yield Static("")

            with Horizontal(id="results-cards"):
                with VerticalScroll(id="section-performance", classes="result-card", can_focus=True):
                    yield Static("PERFORMANCE", classes="section-title")
                    yield Static("Your speed and accuracy for this lesson.", classes="section-desc")
                    cfg = self.app.config       # type: ignore[attr-defined]
                    yield Label(f"⚡ WPM: {s.wpm:.0f}", classes="stat-value wpm-value")
                    yield Static(
                        horizontal_bar("Accuracy", s.accuracy, 100, value_fmt="{:.1f}%",
                                       color=_accuracy_color(s.accuracy)),
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

                if session_bigrams:
                    with VerticalScroll(id="section-bigrams", classes="result-card", can_focus=True):
                        yield Static("MISTAKE BIGRAMS", classes="section-title")
                        yield Static("Two-letter combinations you mistyped most in this session.", classes="section-desc")
                        yield Static(ranked_bars(session_bigrams), id="bigram-chart")

                if mistaken_words:
                    with VerticalScroll(id="section-words", classes="result-card", can_focus=True):
                        yield Static("MISTAKEN WORDS", classes="section-title")
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
        target.focus()

    def _card_ids(self) -> list[str]:
        return [card.id for card in self.query(".result-card") if card.id]

    def action_focus_next_card(self) -> None:
        self._shift_card_focus(1)

    def action_focus_previous_card(self) -> None:
        self._shift_card_focus(-1)

    def _shift_card_focus(self, direction: int) -> None:
        card_ids = self._card_ids()
        if not card_ids:
            return
        focused = self.focused
        current_id = focused.id if focused and focused.id in card_ids else None
        if current_id is None:
            next_id = card_ids[0]
        else:
            idx = card_ids.index(current_id)
            next_id = card_ids[(idx + direction) % len(card_ids)]
        self.query_one(f"#{next_id}").focus()
