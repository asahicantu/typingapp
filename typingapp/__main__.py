import datetime
import traceback
from pathlib import Path

from typingapp.app import TypingApp

CRASH_LOG_PATH = Path.home() / ".typingapp" / "crash.log"


def main():
    app = TypingApp()
    try:
        app.run()
    except Exception:
        CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CRASH_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"\n=== crash at {datetime.datetime.now().isoformat()} ===\n")
            f.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
