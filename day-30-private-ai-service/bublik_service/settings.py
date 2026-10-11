"""Only storage settings are executable at stages 1–2."""
import os
from pathlib import Path
import sys


def default_database():
    if value := os.getenv("BUBLIK_DATA_DIR"):
        directory = Path(value).expanduser()
    elif sys.platform == "darwin":
        directory = Path.home() / "Library/Application Support/BublikPrivateAI"
    else:
        directory = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share")) / "bublik-private-ai"
    return directory / "chats.sqlite3"
