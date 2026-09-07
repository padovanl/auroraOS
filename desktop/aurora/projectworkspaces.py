"""Per-project launch preferences for Dev Hub and Spotlight."""

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path


EDITORS = ("auto", "code", "codium", "zed", "subl")


def config_path():
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "aurora" / "project-workspaces.json"


def load():
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    target = config_path()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".projects-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(data, stream, ensure_ascii=False)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def preferences(path):
    value = load().get(os.path.realpath(path), {})
    return {"editor": value.get("editor", "auto") if value.get("editor") in EDITORS else "auto",
            "terminal": bool(value.get("terminal", True)),
            "files": bool(value.get("files", True)),
            "layout": value.get("layout", []) if isinstance(value.get("layout", []), list) else []}


def configure(path, editor="auto", terminal=True, files=True):
    if editor not in EDITORS:
        raise ValueError("unsupported editor")
    data = load()
    previous = data.get(os.path.realpath(path), {})
    data[os.path.realpath(path)] = {"editor": editor, "terminal": bool(terminal),
                                    "files": bool(files), "layout": previous.get("layout", [])}
    save(data)


def capture_layout(path):
    from aurora import wayfirelayout
    layout = wayfirelayout.save_layout()
    data = load()
    key = os.path.realpath(path)
    data[key] = {**data.get(key, {}), "layout": layout}
    save(data)
    return len(layout)


def open_workspace(path):
    """Launch only installed, known applications; never evaluate project files."""
    from aurora import apps
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    prefs = preferences(path)
    try:
        from aurora import wayfirelayout
        before = wayfirelayout.views() if prefs["layout"] else []
    except (OSError, ValueError, ConnectionError):
        before = []
    editor = prefs["editor"]
    if editor == "auto":
        editor = next((name for name in EDITORS[1:] if shutil.which(name)), "")
    opened = False
    if editor and shutil.which(editor):
        apps.spawn([editor, path])
        opened = True
    if prefs["terminal"]:
        apps.spawn(["ptyxis", "--new-window", "--working-directory", path])
        opened = True
    if prefs["files"] or not opened:
        apps.spawn(["aurora-files", path])
    if before and prefs["layout"]:
        threading.Thread(target=wayfirelayout.restore_layout,
                         args=(prefs["layout"], before), daemon=True).start()
