from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".typingapp" / "config.json"


@dataclass
class AppConfig:
    strict_mode: bool = False
    content_type: str = "words"
    session_duration: int = 60
    difficulty: int = 0
    show_live_wpm: bool = True
    show_hints: bool = True
    key_sounds: bool = True


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()
    with path.open() as f:
        data = json.load(f)
    return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})


def save_config(cfg: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(asdict(cfg), f, indent=2)
