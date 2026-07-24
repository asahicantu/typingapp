#!/usr/bin/env bash
# One-shot installer + launcher for Typing Tutor.
#
# Creates a local virtual environment (if missing), installs the app and
# its dependencies into it, then launches the app. Safe to re-run — it
# reuses the existing environment on subsequent runs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

step() {
    printf '\033[1;36m==>\033[0m %s\n' "$1"
}

find_python() {
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            local version major minor
            version="$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -n1)"
            major="${version%%.*}"
            minor="${version##*.}"
            if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

step "Checking for Python 3.10+"
if ! PYTHON_CMD="$(find_python)"; then
    echo "Python 3.10+ was not found on your PATH." >&2
    echo "Install it from https://www.python.org/downloads/ (or via your OS package manager), then re-run this script." >&2
    exit 1
fi
echo "Using '$PYTHON_CMD' ($("$PYTHON_CMD" --version))"

VENV_DIR="$REPO_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    step "Creating virtual environment in .venv"
    "$PYTHON_CMD" -m venv "$VENV_DIR"
else
    step "Reusing existing virtual environment (.venv)"
fi

step "Installing dependencies"
"$VENV_PYTHON" -m pip install --upgrade pip --quiet
"$VENV_PYTHON" -m pip install -e . --quiet
"$VENV_PYTHON" -m pip install pytest --quiet

step "Launching Typing Tutor"
exec "$VENV_PYTHON" -m typingapp
