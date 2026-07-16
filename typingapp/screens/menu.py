from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import Center, Middle, Vertical


class MenuScreen(Screen):
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="menu-box"):
                    yield Static("⌨  TYPING TUTOR", classes="menu-title")
                    yield Static("", classes="spacer")
                    yield Button("▶  Start Lesson", id="btn-start", variant="primary")
                    yield Button("📊  History & Progress", id="btn-history")
                    yield Button("⚙  Settings", id="btn-settings")
                    yield Button("✕  Quit", id="btn-quit", variant="error")
                    yield Static("", classes="spacer")
                    yield Label("", id="last-session-label", classes="stat-label")

    def on_mount(self) -> None:
        storage = self.app.storage          # type: ignore[attr-defined]
        sessions = storage.fetch_recent_sessions(limit=1)
        if sessions:
            s = sessions[0]
            self.query_one("#last-session-label", Label).update(
                f"Last session: {s['wpm']:.0f} WPM · {s['accuracy']:.1f}% accuracy"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            cfg = self.app.config       # type: ignore[attr-defined]
            if cfg.content_type == "custom":
                from typingapp.screens.custom_text import CustomTextScreen
                from typingapp.screens.lesson import LessonScreen
                def start_with_text(text: str) -> None:
                    self.app.pop_screen()
                    self.app.push_screen(LessonScreen(custom_text=text))
                self.app.push_screen(CustomTextScreen(on_confirm=start_with_text))
            else:
                from typingapp.screens.lesson import LessonScreen
                self.app.push_screen(LessonScreen())
        elif event.button.id == "btn-history":
            from typingapp.screens.history import HistoryScreen
            self.app.push_screen(HistoryScreen())
        elif event.button.id == "btn-settings":
            from typingapp.screens.settings import SettingsScreen
            self.app.push_screen(SettingsScreen())
        elif event.button.id == "btn-quit":
            self.app.exit()

    def action_quit(self) -> None:
        self.app.exit()
