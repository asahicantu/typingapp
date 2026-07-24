from __future__ import annotations
from typing import Callable, Union

BAR_CHARS = "▏▎▍▌▋▊▉█"


def horizontal_bar(label: str, value: float, max_value: float, width: int = 24,
                    value_fmt: Union[str, Callable[[float], str]] = "{:.0f}",
                    color: str | None = None) -> str:
    """Render a single labeled horizontal bar, e.g. 'Accuracy   [green]████████░░[/] 94%'."""
    max_value = max_value or 1
    ratio = max(0.0, min(1.0, value / max_value))
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    if color:
        bar = f"[{color}]{bar}[/]"
    text = value_fmt(value) if callable(value_fmt) else value_fmt.format(value)
    return f"{label:<12}{bar} {text}"


def ranked_bars(items: list[tuple[str, int]], width: int = 20, colors: list[str] | None = None) -> str:
    """Render a ranked list of (label, count) as horizontal bars, longest first."""
    if not items:
        return "(no data)"
    colors = colors or ["red", "orange3", "yellow3", "white"]
    max_count = max(count for _, count in items) or 1
    lines = []
    for i, (label, count) in enumerate(items):
        color = colors[min(i, len(colors) - 1)]
        filled = int((count / max_count) * width)
        bar = "█" * filled
        lines.append(f"[{color}]{label:<8}[/] {bar} {count}")
    return "\n".join(lines)
