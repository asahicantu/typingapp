from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import Center, Middle, Vertical

from typingapp.engine.book_text import page_info, CONTENT_TYPE_LABELS


def _next_lesson_preview(app) -> str:
    cfg = app.config
    label = CONTENT_TYPE_LABELS.get(cfg.content_type, cfg.content_type)
    if cfg.content_type == "literature" and cfg.selected_book_id:
        book = app.storage.get_book(cfg.selected_book_id)
        if book is not None:
            offset = app.storage.fetch_book_progress(cfg.selected_book_id)
            page, total_pages, pct = page_info(book["total_chars"], offset)
            return f"Next: Literature — {book['title']}, page {page}/{total_pages} ({pct:.0f}%)"
        return f"Next: Literature — {cfg.selected_book_id} (not cached yet, will fetch)"
    return f"Next: {label}"


class MenuScreen(Screen):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "jump_start", "Start Lesson"),
        ("2", "jump_history", "History"),
        ("3", "jump_settings", "Settings"),
        ("4", "jump_library", "My Books"),
        ("5", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                with Vertical(id="menu-box"):
                    yield Static("⌨  TYPING TUTOR", classes="menu-title")
                    yield Static("", classes="spacer")
                    yield Label("", id="next-lesson-label", classes="stat-label")
                    yield Static("", classes="spacer")
                    yield Button("1  ▶  Start Lesson", id="btn-start", variant="primary")
                    yield Button("2  📊  History & Progress", id="btn-history")
                    yield Button("3  ⚙  Settings", id="btn-settings")
                    yield Button("4  📚  My Books", id="btn-library")
                    yield Button("5  ✕  Quit", id="btn-quit", variant="error")
                    yield Static("", classes="spacer")
                    yield Label("", id="last-session-label", classes="stat-label")
                    yield Static(
                        "↑↓/Tab move · Enter select · 1-5 jump · Q quit",
                        classes="nav-hint",
                    )

    def on_mount(self) -> None:
        storage = self.app.storage          # type: ignore[attr-defined]
        sessions = storage.fetch_recent_sessions(limit=1)
        if sessions:
            s = sessions[0]
            self.query_one("#last-session-label", Label).update(
                f"Last session: {s['wpm']:.0f} WPM · {s['accuracy']:.1f}% accuracy"
            )

    def on_screen_resume(self) -> None:
        # Settings may have changed content type/selected book while this screen was
        # suspended underneath it. Unlike on_mount (fires once ever), on_screen_resume
        # fires both at initial mount and every time this screen is revealed again via
        # pop_screen() — on_show does NOT re-fire on resume, only at first mount.
        self._refresh_next_lesson_preview()

    def _refresh_next_lesson_preview(self) -> None:
        self.query_one("#next-lesson-label", Label).update(_next_lesson_preview(self.app))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            self._start_lesson()
        elif event.button.id == "btn-history":
            self._open_history()
        elif event.button.id == "btn-settings":
            self._open_settings()
        elif event.button.id == "btn-library":
            self._open_library()
        elif event.button.id == "btn-quit":
            self.app.exit()

    def _start_lesson(self) -> None:
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

    def _open_history(self) -> None:
        from typingapp.screens.history import HistoryScreen
        self.app.push_screen(HistoryScreen())

    def _open_settings(self) -> None:
        from typingapp.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen())

    def _open_library(self) -> None:
        from typingapp.screens.library import LibraryScreen
        self.app.push_screen(LibraryScreen())

    def action_quit(self) -> None:
        self.app.exit()

    def action_jump_start(self) -> None:
        self._start_lesson()

    def action_jump_history(self) -> None:
        self._open_history()

    def action_jump_settings(self) -> None:
        self._open_settings()

    def action_jump_library(self) -> None:
        self._open_library()
