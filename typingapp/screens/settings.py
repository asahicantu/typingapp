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
                    options=[
                        ("Words", "words"), ("Sentences", "sentences"),
                        ("Random Sentences", "random_sentences"), ("Literature", "literature"),
                        ("Code", "code"), ("Custom", "custom"),
                    ],
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
            with Horizontal(classes="setting-row"):
                yield Label("Language")
                yield Select(
                    options=[("English", "en"), ("Espanol", "es"), ("Francais", "fr")],
                    value=cfg.language,
                    id="sel-language",
                )
            yield Static("")

            yield Static("DIFFICULTY & WORD COUNT", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Manual difficulty (disable auto-adaptive)")
                yield Switch(value=cfg.manual_difficulty, id="sw-manual-difficulty")
            with Horizontal(classes="setting-row"):
                yield Label("Difficulty level")
                yield Select(
                    options=[(str(n), n) for n in range(1, 11)],
                    value=cfg.difficulty if cfg.difficulty else 1,
                    id="sel-difficulty",
                )
            with Horizontal(classes="setting-row"):
                yield Label("Words per lesson")
                yield Select(
                    options=[("Auto (by difficulty)", 0)] + [(str(n), n) for n in (10, 15, 20, 25, 30, 40, 50, 60, 80, 100)],
                    value=cfg.word_count_override,
                    id="sel-word-count",
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
            sel_lang = self.query_one("#sel-language", Select)
            if sel_lang.value != Select.BLANK:
                cfg.language = sel_lang.value
            cfg.manual_difficulty = self.query_one("#sw-manual-difficulty", Switch).value
            sel_difficulty = self.query_one("#sel-difficulty", Select)
            if sel_difficulty.value != Select.BLANK:
                cfg.difficulty = sel_difficulty.value
            sel_word_count = self.query_one("#sel-word-count", Select)
            if sel_word_count.value != Select.BLANK:
                cfg.word_count_override = sel_word_count.value
            save_config(cfg)
            self.app.pop_screen()
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
