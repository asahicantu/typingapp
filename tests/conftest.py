"""Shared pytest fixtures.

CRITICAL: this fixture exists to guarantee that no test in this suite can ever
write to (or read from) the real ~/.typingapp/config.json on the developer's
machine, now or in the future.

Naively monkeypatching typingapp.config.DEFAULT_CONFIG_PATH is NOT sufficient:
save_config/load_config declare it as a *default parameter value*

    def save_config(cfg: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:

which Python binds once, at function-definition time (i.e. at module import),
into the function's __defaults__ tuple. Reassigning the module-level name
typingapp.config.DEFAULT_CONFIG_PATH afterwards does not touch that already-bound
default, so callers that rely on the default (e.g.
LessonScreen.action_toggle_strict_mode / action_toggle_key_sounds, which call
save_config(app.config) with no explicit path) would keep writing to the real
path even with DEFAULT_CONFIG_PATH monkeypatched. Verified empirically: patching
the module attribute alone left save_config.__defaults__ pointing at the
original ~/.typingapp/config.json.

The fix is to patch the bound default directly via __defaults__ (a mutable
attribute on the function object). Because `from typingapp.config import
save_config` (used in typingapp/screens/lesson.py) binds the *same* function
object, patching it once here redirects every call site regardless of how it
was imported.
"""
import pytest

import typingapp.config as config_module


@pytest.fixture(autouse=True)
def isolate_default_config_path(tmp_path, monkeypatch):
    fake_path = tmp_path / "isolated_config" / "config.json"

    monkeypatch.setattr(config_module, "DEFAULT_CONFIG_PATH", fake_path)
    monkeypatch.setattr(
        config_module.save_config,
        "__defaults__",
        (fake_path,),
    )
    monkeypatch.setattr(
        config_module.load_config,
        "__defaults__",
        (fake_path,),
    )
    yield
