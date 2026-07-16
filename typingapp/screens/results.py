from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import Vertical, Horizontal

from typingapp.engine.scorer import Scorer


class ResultsScreen(Screen):
    BINDINGS = [("escape", "go_menu", "Menu")]

    def __init__(self, scorer: Scorer, session_id: int) -> None:
        super().__init__()
        self._scorer = scorer
        self._session_id = session_id

    def compose(self) -> ComposeResult:
        s = self._scorer
        app = self.app          # type: ignore[attr-defined]
        bigrams = app.storage.fetch_bigram_heatmap(limit=5)
        mins, secs = divmod(int(s.elapsed_seconds), 60)

        with Vertical():
            yield Static("🏁  Session Complete", classes="menu-title")
            yield Static("")
            with Horizontal():
                yield Label("⚡ WPM:      ", classes="stat-label")
                yield Label(f"{s.wpm:.0f}", classes="stat-value wpm-value")
            with Horizontal():
                yield Label("✓  Accuracy: ", classes="stat-label")
                yield Label(f"{s.accuracy:.1f}%", classes="stat-value acc-value")
            with Horizontal():
                yield Label("⏱  Time:     ", classes="stat-label")
                yield Label(f"{mins}:{secs:02d}", classes="stat-value time-value")
            with Horizontal():
                yield Label("✗  Errors:   ", classes="stat-label")
                yield Label(str(s.error_count), classes="stat-value err-value")
            yield Static("")
            if bigrams:
                yield Static("TOP MISTAKE BIGRAMS", classes="stat-label")
                for b in bigrams:
                    yield Label(f"  '{b['bigram']}' — {b['errors']} errors", classes="err-value")
            yield Static("")
            yield Button("▶  Retry Same", id="btn-retry", variant="primary")
            yield Button("🔀  New Lesson", id="btn-new")
            yield Button("📊  View History", id="btn-history")
            yield Button("🏠  Menu", id="btn-menu")

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
