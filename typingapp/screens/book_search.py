from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, ListView, ListItem, Label, Button
from textual.containers import Vertical

from typingapp.engine.epub_source import scan_epub_folder, epub_book_id
from typingapp.engine.gutenberg import search_books

SEARCH_DEBOUNCE_SECONDS = 0.4


class BookSearchScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, on_select) -> None:
        super().__init__()
        self._on_select = on_select
        self._results: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📚  Browse Books", classes="menu-title")
            yield Input(placeholder="Search by title or author...", id="search-input")
            yield Label("", id="epub-warning", classes="stat-label")
            yield ListView(id="results-list")
            yield Button("✕  Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        cfg = self.app.config       # type: ignore[attr-defined]
        if cfg.epub_folder and not scan_epub_folder(cfg.epub_folder):
            self.query_one("#epub-warning", Label).update(f"⚠ No local EPUB files found in {cfg.epub_folder}")
        self._run_search("")

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value
        self.set_timer(SEARCH_DEBOUNCE_SECONDS, lambda: self._maybe_search(query))

    def _maybe_search(self, query: str) -> None:
        current = self.query_one("#search-input", Input).value
        if current != query:
            return  # a newer keystroke already superseded this debounced search
        self._run_search(query)

    def _run_search(self, query: str) -> None:
        app = self.app       # type: ignore[attr-defined]
        cfg = app.config

        results: list[dict] = []
        if cfg.epub_folder:
            for meta in scan_epub_folder(cfg.epub_folder):
                if query and query.lower() not in meta.title.lower() and query.lower() not in meta.author.lower():
                    continue
                results.append({
                    "book_id": epub_book_id(meta.path), "source": "epub",
                    "title": meta.title, "author": meta.author, "path": meta.path,
                })

        for book in search_books(language=cfg.language, limit=20, query=query):
            results.append({
                "book_id": f"gutenberg:{book.gutenberg_id}", "source": "gutenberg",
                "title": book.title, "author": book.author, "text_url": book.text_url,
            })

        self._results = results
        self._render_results()

    def _render_results(self) -> None:
        list_view = self.query_one("#results-list", ListView)
        list_view.clear()
        if not self._results:
            list_view.append(ListItem(Label("(no matches)")))
            return
        for result in self._results:
            list_view.append(ListItem(Label(f"[{result['source']}] {result['title']} — {result['author']}")))
        list_view.index = 0  # clear() resets index to None; re-highlight the first result

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = self.query_one("#results-list", ListView).index
        if index is None or index >= len(self._results):
            return
        self._on_select(self._results[index])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
