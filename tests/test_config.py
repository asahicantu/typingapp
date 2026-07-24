import json
import pytest
from pathlib import Path
from typingapp.config import AppConfig, load_config, save_config


def test_default_config():
    cfg = AppConfig()
    assert cfg.strict_mode is False
    assert cfg.content_type == "words"
    assert cfg.session_duration == 60
    assert cfg.difficulty == 0
    assert cfg.show_live_wpm is True
    assert cfg.show_hints is True
    assert cfg.key_sounds is True


def test_save_and_load_roundtrip(tmp_path):
    cfg = AppConfig(strict_mode=True, session_duration=30)
    path = tmp_path / "config.json"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.strict_mode is True
    assert loaded.session_duration == 30


def test_load_missing_file_returns_defaults(tmp_path):
    path = tmp_path / "nonexistent.json"
    cfg = load_config(path)
    assert cfg == AppConfig()
