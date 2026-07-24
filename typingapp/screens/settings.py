from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Switch, Select, Label
from textual.containers import Vertical, Horizontal, ScrollableContainer
from typingapp.config import save_config


class SettingsScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        cfg = self.app.config       # type: ignore[attr-defined]
        with ScrollableContainer():
            yield Static("⚙  Settings", classes="menu-title")
            yield Static("")

            yield Static("TYPING BEHAVIOR", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Strict mode (block on error)")
                yield Switch(value=cfg.strict_mode, id="sw-strict")
            yield Static("When ON: you must fix each error before continuing.", classes="stat-label")
            yield Static("")

            yield Static("LESSON DEFAULTS", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Content type")
                yield Select(
                    options=[("Words", "words"), ("Sentences", "sentences"),
                             ("Code", "code"), ("Custom", "custom")],
                    value=cfg.content_type,
                    id="sel-content",
                )
            with Horizontal(classes="setting-row"):
                yield Label("Session duration (seconds)")
                yield Select(
                    options=[("30s", 30), ("60s", 60), ("120s", 120)],
                    value=cfg.session_duration,
                    id="sel-duration",
                )
            yield Static("")

            yield Static("DISPLAY", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Show live WPM")
                yield Switch(value=cfg.show_live_wpm, id="sw-wpm")
            with Horizontal(classes="setting-row"):
                yield Label("Show adaptive hints")
                yield Switch(value=cfg.show_hints, id="sw-hints")
            with Horizontal(classes="setting-row"):
                yield Label("Key sounds")
                yield Switch(value=cfg.key_sounds, id="sw-sound")
            yield Static("")

            yield Button("💾  Save & Back", id="btn-save", variant="primary")
            yield Button("✕  Cancel", id="btn-cancel")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "sw-sound" and event.value:
            app = self.app          # type: ignore[attr-defined]
            app.sound.play_correct()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            cfg = self.app.config       # type: ignore[attr-defined]
            cfg.strict_mode = self.query_one("#sw-strict", Switch).value
            cfg.show_live_wpm = self.query_one("#sw-wpm", Switch).value
            cfg.show_hints = self.query_one("#sw-hints", Switch).value
            cfg.key_sounds = self.query_one("#sw-sound", Switch).value
            sel_content = self.query_one("#sel-content", Select)
            if sel_content.value != Select.BLANK:
                cfg.content_type = sel_content.value
            sel_dur = self.query_one("#sel-duration", Select)
            if sel_dur.value != Select.BLANK:
                cfg.session_duration = sel_dur.value
            save_config(cfg)
            self.app.pop_screen()
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
