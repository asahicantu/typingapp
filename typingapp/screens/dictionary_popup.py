from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button
from textual.containers import Vertical
from textual.binding import Binding


class DictionaryPopupScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss_popup", "Close"), Binding("enter", "dismiss_popup", "Close")]

    def __init__(self, word: str, definition: str | None, unavailable_reason: str = "") -> None:
        super().__init__()
        self._word = word
        self._definition = definition
        self._unavailable_reason = unavailable_reason

    def compose(self) -> ComposeResult:
        with Vertical(id="dictionary-popup-body"):
            yield Static(f"📖  {self._word}", classes="menu-title")
            if self._unavailable_reason:
                yield Static(self._unavailable_reason, id="dictionary-definition")
            elif self._definition:
                yield Static(self._definition, id="dictionary-definition")
            else:
                yield Static("No definition found.", id="dictionary-definition")
            yield Button("Close", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

    def action_dismiss_popup(self) -> None:
        self.dismiss()
