# Typing Tutor

A terminal-based typing tutor built with [Textual](https://textual.textualize.io/). Practice words, sentences, or code snippets, track your WPM/accuracy over time, and get adaptive difficulty that responds to your performance.

## Requirements

| Tool | Version | Notes |
|------|---------|-------|
| [Python](https://www.python.org/downloads/) | 3.10+ | Must be on your `PATH` as `python` (Windows) or `python3` (macOS/Linux). |
| `pip` | bundled with Python | Used to install dependencies. |

### Python packages

| Package | Purpose |
|---------|---------|
| [`textual`](https://pypi.org/project/textual/) (>=0.80.0) | TUI framework — screens, widgets, layout, keyboard input |
| [`pytest`](https://pypi.org/project/pytest/) | Test runner (only needed for development) |

Runtime dependencies are declared in `pyproject.toml`; `pytest` is a dev-only addition installed alongside it. No other third-party dependencies — SQLite session storage and JSON config use the Python standard library.

## Quick Start (one command)

The `onboard` script creates an isolated virtual environment, installs everything needed, and launches the app — no manual steps required.

**Windows (PowerShell):**
```powershell
.\onboard.ps1
```

**macOS/Linux (bash):**
```bash
./onboard.sh
```

Re-running the script later just reuses the existing environment and launches the app — safe to use as your everyday "start the app" command too.

## Manual Install

If you'd rather install by hand instead of using the onboard script:

```bash
# 1. Create and activate a virtual environment (optional but recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 2. Install the app and its dependencies (editable install, uses pyproject.toml)
pip install -e .
pip install pytest

# 3. Run the app
python -m typingapp
# or, since pyproject.toml registers a console script:
typingtutor
```

## Running Tests

```bash
pytest              # run the full suite
pytest tests/test_scorer.py -v   # run a single test file
```

## Data & Config Locations

| Path | Contents |
|------|----------|
| `~/.typingapp/history.db` | SQLite session and keystroke history |
| `~/.typingapp/config.json` | User settings (strict mode, content type, difficulty, etc.) |

Both are created automatically on first run.
