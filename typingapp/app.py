from __future__ import annotations
from textual.app import App

from typingapp.config import load_config, AppConfig
from typingapp.data.storage import Storage
from typingapp.engine.lesson import LessonEngine
from typingapp.engine.adaptive import AdaptiveEngine


class TypingApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "Typing Tutor"

    def __init__(self) -> None:
        super().__init__()
        self.config: AppConfig = load_config()
        self.storage: Storage = Storage()
        self.lesson_engine: LessonEngine = LessonEngine()
        self.adaptive: AdaptiveEngine = AdaptiveEngine(
            current_level=self.config.difficulty if self.config.difficulty > 0 else 1
        )

    def on_mount(self) -> None:
        from typingapp.screens.menu import MenuScreen
        self.push_screen(MenuScreen())

    def on_unmount(self) -> None:
        self.storage.close()
