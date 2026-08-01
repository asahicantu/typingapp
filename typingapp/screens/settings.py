from __future__ import annotations
import datetime
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Switch, Select, Label, Input
from textual.containers import Vertical, Horizontal, ScrollableContainer
from typingapp.config import save_config
from typingapp.engine.book_text import page_info, CONTENT_TYPE_LABELS, fetch_and_cache_book
from typingapp.engine.epub_source import scan_epub_folder


def _book_display_text(app) -> str:
    cfg = app.config
    if not cfg.selected_book_id:
        return "(none — random excerpts)"
    book = app.storage.get_book(cfg.selected_book_id)
    if book is None:
        return f'⚠ "{cfg.selected_book_id}" isn\'t cached — pick a book via Find a New Book or My Books'
    offset = app.storage.fetch_book_progress(cfg.selected_book_id)
    page, total_pages, pct = page_info(book["total_chars"], offset)
    return f"{book['title']} — {book['author']}  ({pct:.0f}% · page {page}/{total_pages})"


def _book_mismatch_warning(app, content_type: str) -> str:
    if app.config.selected_book_id and content_type != "literature":
        label = CONTENT_TYPE_LABELS.get(content_type, content_type)
        return f'⚠ Content type is "{label}" — switch to "Literature" to read this book'
    return ""


def _epub_folder_status(folder: str) -> str:
    if not folder:
        return ""
    books = scan_epub_folder(folder)
    if not books:
        return f"⚠ No .epub files found in {folder}"
    return f"✓ {len(books)} EPUB file(s) found"


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
                    options=[("English", "en"), ("Espanol", "es"), ("Francais", "fr"), ("Norsk", "no")],
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

            yield Static("📖  E-BOOK READING  (applies when Content type = Literature)", classes="stat-label")
            yield Static(
                "Search Project Gutenberg or import from a local folder — pick one book "
                "to read from start to finish, one typing session at a time.",
                classes="section-desc",
            )
            with Horizontal(classes="setting-row"):
                yield Label("Local EPUB folder")
                yield Input(value=cfg.epub_folder, placeholder="/path/to/epub/folder", id="input-epub-folder")
            yield Static(_epub_folder_status(cfg.epub_folder), id="epub-folder-status", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Label("Currently reading")
                yield Static(_book_display_text(self.app), id="selected-book-val")
            yield Static(_book_mismatch_warning(self.app, cfg.content_type), id="book-mismatch-warning", classes="stat-label")
            with Horizontal(classes="setting-row"):
                yield Button("🔎  Find a New Book", id="btn-browse-books", variant="primary")
                yield Button("📚  My Books", id="btn-open-library")
                yield Button("✕  Stop Reading This Book", id="btn-clear-book")
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
            with Horizontal(classes="setting-row"):
                yield Label("Highlight previously mistyped words")
                yield Switch(value=cfg.highlight_past_mistakes, id="sw-highlight-mistakes")
            yield Static("")

            yield Button("💾  Save & Back", id="btn-save", variant="primary")
            yield Button("✕  Cancel", id="btn-cancel")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "sw-sound" and event.value:
            app = self.app          # type: ignore[attr-defined]
            app.sound.play_correct()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sel-content" and event.value != Select.BLANK:
            self._refresh_book_mismatch_warning(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "input-epub-folder":
            self.query_one("#epub-folder-status", Static).update(_epub_folder_status(event.value))

    def on_screen_resume(self) -> None:
        # My Books may have changed the currently-reading book while this screen was
        # suspended underneath it — on_mount only fires once, on_show doesn't re-fire on resume.
        app = self.app       # type: ignore[attr-defined]
        self.query_one("#selected-book-val", Static).update(_book_display_text(app))
        self._refresh_book_mismatch_warning(self.query_one("#sel-content", Select).value)

    def _refresh_book_mismatch_warning(self, content_type: str) -> None:
        self.query_one("#book-mismatch-warning", Static).update(
            _book_mismatch_warning(self.app, content_type)
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            cfg = self.app.config       # type: ignore[attr-defined]
            cfg.strict_mode = self.query_one("#sw-strict", Switch).value
            cfg.show_live_wpm = self.query_one("#sw-wpm", Switch).value
            cfg.show_hints = self.query_one("#sw-hints", Switch).value
            cfg.key_sounds = self.query_one("#sw-sound", Switch).value
            cfg.highlight_past_mistakes = self.query_one("#sw-highlight-mistakes", Switch).value
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
            cfg.epub_folder = self.query_one("#input-epub-folder", Input).value
            save_config(cfg)
            self.app.pop_screen()
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()
        elif event.button.id == "btn-browse-books":
            from typingapp.screens.book_search import BookSearchScreen
            self.app.push_screen(BookSearchScreen(on_select=self._pin_book))
        elif event.button.id == "btn-open-library":
            from typingapp.screens.library import LibraryScreen
            self.app.push_screen(LibraryScreen())
        elif event.button.id == "btn-clear-book":
            app = self.app          # type: ignore[attr-defined]
            app.config.selected_book_id = ""
            save_config(app.config)
            self.query_one("#selected-book-val", Static).update(_book_display_text(app))
            self._refresh_book_mismatch_warning(self.query_one("#sel-content", Select).value)

    def _pin_book(self, result: dict) -> None:
        app = self.app          # type: ignore[attr-defined]
        ok = fetch_and_cache_book(app.storage, app.config.language, result, datetime.datetime.now().isoformat())
        if not ok:
            self.query_one("#selected-book-val", Static).update(
                f"⚠ Couldn't load '{result['title']}' — book not cached"
            )
            self.app.pop_screen()
            return
        app.config.selected_book_id = result["book_id"]
        save_config(app.config)
        self.app.pop_screen()
        self.query_one("#selected-book-val", Static).update(_book_display_text(app))
        self._refresh_book_mismatch_warning(self.query_one("#sel-content", Select).value)

    def action_go_back(self) -> None:
        self.app.pop_screen()
