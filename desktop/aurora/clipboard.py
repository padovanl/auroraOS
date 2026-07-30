"""Clipboard history, kept on disk for Spotlight (Super+V).

The shell runs `wl-paste --type text --watch aurora-clipboard store`: every
time something is copied, wl-paste starts `store` with the text on stdin.
Passwords stay out: password managers mark their copies as sensitive and
wl-paste passes that on in CLIPBOARD_STATE. The history lives in
~/.local/share/aurora/clipboard.json, readable only by the user.

    aurora-clipboard store     read a new entry from stdin
    aurora-clipboard list      print the history, newest first
    aurora-clipboard clear     forget everything
"""

import fcntl
import json
import os
import sys

LIMIT = 100                 # entries kept
MAX_BYTES = 64 * 1024       # larger copies are not remembered


def history_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "aurora", "clipboard.json")


def load():
    try:
        with open(history_path()) as f:
            items = json.load(f)
        return [i for i in items if isinstance(i, str)]
    except (OSError, ValueError):
        return []


def _save(items):
    path = history_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".new"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(items, f)
    os.replace(tmp, path)


def add(text, items=None):
    """Put text at the top of the history (moving it if already there)."""
    items = load() if items is None else items
    if not text.strip() or len(text.encode()) > MAX_BYTES:
        return items
    items = [text] + [i for i in items if i != text]
    return items[:LIMIT]


def store(stdin=sys.stdin, env=os.environ):
    if env.get("CLIPBOARD_STATE", "data") in ("sensitive", "clear", "nil"):
        return
    data = stdin.buffer.read(MAX_BYTES + 1) if hasattr(stdin, "buffer") else stdin.read()
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    lock_path = history_path() + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _save(add(data))


def clear():
    try:
        os.remove(history_path())
    except FileNotFoundError:
        pass


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "store":
        store()
    elif cmd == "list":
        for item in load():
            print(item.replace("\n", "⏎"))
    elif cmd == "clear":
        clear()
    else:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    return 0
