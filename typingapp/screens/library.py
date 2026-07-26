from __future__ import annotations
import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Label, ListView, ListItem, Button
from textual.containers import Vertical

from typingapp.config import save_config
from typingapp.engine.book_text import page_info, fetch_and_cache_book
from typingapp.engine.charts import horizontal_bar

SOURCE_ICON = {"gutenberg": "🌐", "epub": "📖"}


class LibraryScreen(Screen):
    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("enter", "read_selected", "Read"),
        ("d", "delete_selected", "Delete"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._books: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📚  My Books", classes="menu-title")
            yield Static(
                "Every book you've searched or imported, with your reading progress.",
                classes="section-desc",
            )
            yield Label("", id="library-status", classes="stat-label")
            yield ListView(id="library-list")
            with Vertical(id="library-commands"):
                yield Static("[Enter] Read this book   ·   [D] Delete   ·   [Esc] Back", classes="nav-hint")
            yield Button("📚  Browse for more books", id="btn-browse-more")
            yield Button("✕  Back", id="btn-back")

    def on_mount(self) -> None:
        self._reload()

    def on_screen_resume(self) -> None:
        self._reload()

    def _reload(self) -> None:
        app = self.app       # type: ignore[attr-defined]
        self._books = app.storage.list_books_with_progress(limit=100)
        self._render_books()

    def _render_books(self) -> None:
        list_view = self.query_one("#library-list", ListView)
        list_view.clear()
        status = self.query_one("#library-status", Label)
        if not self._books:
            status.update("No books yet — browse Project Gutenberg or import local EPUBs to get started.")
            list_view.append(ListItem(Label("(your library is empty)")))
            return
        status.update(f"{len(self._books)} book(s) in your library.")
        for book in self._books:
            page, total_pages, pct = page_info(book["total_chars"], book["current_offset"])
            icon = SOURCE_ICON.get(book["source"], "📄")
            bar = horizontal_bar("Progress", pct, 100.0, width=16, value_fmt="{:.0f}%")
            title_line = f"{icon} {book['title']} — {book['author']}"
            list_view.append(ListItem(Label(
                f"{title_line}\n   {bar}   ·   page {page}/{total_pages}"
            )))
        list_view.index = 0

    def _selected_book(self) -> dict | None:
        index = self.query_one("#library-list", ListView).index
        if index is None or index >= len(self._books):
            return None
        return self._books[index]

    def action_read_selected(self) -> None:
        book = self._selected_book()
        if book is None:
            return
        app = self.app       # type: ignore[attr-defined]
        app.config.content_type = "literature"
        app.config.selected_book_id = book["book_id"]
        save_config(app.config)
        from typingapp.screens.lesson import LessonScreen
        self.app.switch_screen(LessonScreen())

    def action_delete_selected(self) -> None:
        book = self._selected_book()
        if book is None:
            return
        app = self.app       # type: ignore[attr-defined]
        app.storage.delete_book(book["book_id"])
        if app.config.selected_book_id == book["book_id"]:
            app.config.selected_book_id = ""
            save_config(app.config)
        self._reload()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.action_read_selected()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-browse-more":
            from typingapp.screens.book_search import BookSearchScreen
            self.app.push_screen(BookSearchScreen(on_select=self._pin_and_reload))

    def _pin_and_reload(self, result: dict) -> None:
        app = self.app       # type: ignore[attr-defined]
        ok = fetch_and_cache_book(app.storage, app.config.language, result, datetime.datetime.now().isoformat())
        self.app.pop_screen()  # back from BookSearchScreen to LibraryScreen
        status = self.query_one("#library-status", Label)
        if not ok:
            status.update(f"⚠ Couldn't load '{result['title']}' — try again later")
            return
        self._reload()

    def action_go_back(self) -> None:
        self.app.pop_screen()
