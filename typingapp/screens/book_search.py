from __future__ import annotations
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, ListView, ListItem, Label, Button
from textual.containers import Vertical

from typingapp.engine.epub_source import scan_epub_folder, epub_book_id
from typingapp.engine.gutenberg import search_books

SEARCH_DEBOUNCE_SECONDS = 0.4
MIN_QUERY_LENGTH = 2


class BookSearchScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, on_select) -> None:
        super().__init__()
        self._on_select = on_select
        self._results: list[dict] = []
        self._current_query: str = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("📚  Browse Books", classes="menu-title")
            yield Static(
                "Searches Project Gutenberg (needs internet) and your local EPUB folder, if configured.",
                classes="section-desc",
            )
            yield Input(placeholder="Search by title or author...", id="search-input")
            yield Label("", id="search-status", classes="stat-label")
            yield Label("", id="epub-warning", classes="stat-label")
            yield ListView(id="results-list")
            yield Button("✕  Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self._update_epub_folder_warning()
        self.query_one("#search-status", Label).update(
            f"Type at least {MIN_QUERY_LENGTH} characters to search…"
        )

    def _update_epub_folder_warning(self) -> None:
        cfg = self.app.config       # type: ignore[attr-defined]
        warning = self.query_one("#epub-warning", Label)
        if cfg.epub_folder and not scan_epub_folder(cfg.epub_folder):
            warning.update(f"⚠ No local EPUB files found in {cfg.epub_folder}")
        else:
            warning.update("")

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value
        self.set_timer(SEARCH_DEBOUNCE_SECONDS, lambda: self._maybe_search(query))

    def _maybe_search(self, query: str) -> None:
        current = self.query_one("#search-input", Input).value
        if current != query:
            return  # a newer keystroke already superseded this debounced search
        self._run_search(query)

    def _run_search(self, query: str) -> None:
        self._current_query = query
        app = self.app       # type: ignore[attr-defined]
        cfg = app.config
        status = self.query_one("#search-status", Label)

        if not query.strip():
            self._results = []
            self._render_results()
            self._update_epub_folder_warning()
            status.update(f"Type at least {MIN_QUERY_LENGTH} characters to search…")
            return

        if len(query.strip()) < MIN_QUERY_LENGTH:
            self._results = []
            self._render_results()
            status.update(f"Type at least {MIN_QUERY_LENGTH} characters to search… ({len(query.strip())}/{MIN_QUERY_LENGTH})")
            return

        # Local EPUB matching is fast (filesystem/zip only) — runs synchronously
        # and renders immediately so the UI never waits on it.
        local_results: list[dict] = []
        if cfg.epub_folder:
            for meta in scan_epub_folder(cfg.epub_folder):
                if query.lower() not in meta.title.lower() and query.lower() not in meta.author.lower():
                    continue
                local_results.append({
                    "book_id": epub_book_id(meta.path), "source": "epub",
                    "title": meta.title, "author": meta.author, "path": meta.path,
                })
        self._results = local_results
        self._render_results()
        status.update("🔎 Searching Project Gutenberg…")

        # Gutenberg search is a real network call (up to a few seconds) — run it in a
        # background thread so it never freezes the UI, and let a newer search cancel it.
        self._search_gutenberg(query, cfg.language)

    @work(exclusive=True, thread=True, group="gutenberg-search")
    def _search_gutenberg(self, query: str, language: str) -> None:
        books = search_books(language=language, limit=20, query=query)
        self.app.call_from_thread(self._on_gutenberg_results, query, books)

    def _on_gutenberg_results(self, query: str, books: list) -> None:
        if query != self._current_query:
            return  # a newer search superseded this one; discard stale results
        status = self.query_one("#search-status", Label)
        if not books:
            status.update("⚠ No Gutenberg matches, or Gutenberg is unreachable right now")
        else:
            status.update(f"Found {len(books)} Gutenberg match(es).")
        for book in books:
            self._results.append({
                "book_id": f"gutenberg:{book.gutenberg_id}", "source": "gutenberg",
                "title": book.title, "author": book.author, "text_url": book.text_url,
            })
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
