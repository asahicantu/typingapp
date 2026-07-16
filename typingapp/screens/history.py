from __future__ import annotations
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import Vertical, ScrollableContainer

from typingapp.engine.recommender import Recommender


def _bar_chart(values: list[float], width: int = 30) -> str:
    if not values:
        return "(no data yet)"
    max_val = max(values) or 1
    lines = []
    for v in values:
        bar_len = int((v / max_val) * width)
        bar = "▓" * bar_len
        lines.append(f"{v:5.0f} {bar}")
    return "\n".join(lines)


def _heatmap_line(bigrams: list[dict]) -> str:
    if not bigrams:
        return "(no data)"
    colors = ["red", "orange3", "yellow3", "white"]
    parts = []
    for i, b in enumerate(bigrams[:8]):
        color = colors[min(i, len(colors) - 1)]
        parts.append(f"[{color}]{b['bigram']}({b['errors']})[/]")
    return "  ".join(parts)


class HistoryScreen(Screen):
    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        app = self.app          # type: ignore[attr-defined]
        sessions = app.storage.fetch_recent_sessions(limit=30)
        wpms = app.storage.fetch_last_n_wpm(n=14)
        summary = app.storage.fetch_summary()
        bigrams = app.storage.fetch_bigram_heatmap(limit=8)
        weak = [b["bigram"] for b in bigrams]
        recommendation = Recommender().recommend(sessions, bigrams=weak)

        with ScrollableContainer():
            yield Static("📊  Progress Dashboard", classes="menu-title")
            yield Static("")

            yield Static("WPM — LAST 14 SESSIONS", classes="stat-label")
            yield Static(_bar_chart(wpms), id="wpm-chart")
            yield Static("")

            yield Static("SUMMARY", classes="stat-label")
            yield Label(f"  Best WPM:       {summary['best_wpm'] or 0:.0f}", classes="wpm-value")
            yield Label(f"  Avg Accuracy:   {summary['avg_accuracy'] or 0:.1f}%", classes="acc-value")
            yield Label(f"  Total Sessions: {summary['total']}", classes="time-value")
            yield Static("")

            yield Static("MISTAKE HEATMAP (cumulative)", classes="stat-label")
            yield Static(_heatmap_line(bigrams), id="heatmap")
            yield Static("")

            yield Static("🤖  RECOMMENDATION", classes="stat-label")
            yield Label(recommendation, id="rec-label", classes="hint-bar")
            yield Static("")

            yield Button("← Back", id="btn-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()

    def action_go_back(self) -> None:
        self.app.pop_screen()
