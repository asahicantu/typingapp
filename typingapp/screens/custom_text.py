from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, TextArea, Label
from textual.containers import Vertical


class CustomTextScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, on_confirm) -> None:
        super().__init__()
        self._on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📝  Enter Custom Text", classes="menu-title")
            yield Label("Paste or type the text you want to practice:", classes="stat-label")
            yield TextArea(id="custom-input")
            yield Label("", id="error-label", classes="err-value")
            yield Button("▶  Start Lesson", id="btn-confirm", variant="primary")
            yield Button("✕  Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            text = self.query_one("#custom-input", TextArea).text.strip()
            if not text:
                self.query_one("#error-label", Label).update("Please enter some text first.")
                return
            self._on_confirm(text)
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
