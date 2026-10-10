"""Clipboard history, kept on disk for Spotlight (Super+V).

The shell runs `wl-paste --type text --watch aurora-clipboard store`: every
time something is copied, wl-paste starts `store` with the text on stdin.
Passwords stay out: password managers mark their copies as sensitive and
wl-paste passes that on in CLIPBOARD_STATE. The history lives in
~/.local/share/aurora/clipboard.json, readable only by the user.

    aurora-clipboard store     read a new entry from stdin
    aurora-clipboard list      print the history, newest first
    aurora-clipboard show      open the Clipboard window (clipboardapp.py)
    aurora-clipboard clear     forget everything
"""

import fcntl
import hashlib
import json
import os
import sys
import time

LIMIT = 100                 # entries kept
MAX_BYTES = 64 * 1024       # larger copies are not remembered
EXPIRE_SECONDS = 7 * 24 * 60 * 60
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def history_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "aurora", "clipboard.json")


def _meta_path():
    return history_path() + ".meta"


def _image_dir():
    return os.path.join(os.path.dirname(history_path()), "clipboard-images")


def image_paths():
    try:
        paths = [os.path.join(_image_dir(), name) for name in os.listdir(_image_dir())
                 if name.endswith(".png")]
        paths.sort(key=os.path.getmtime, reverse=True)
        now = time.time()
        return [path for path in paths[:20]
                if now - os.path.getmtime(path) < EXPIRE_SECONDS]
    except OSError:
        return []


def store_image(stdin=sys.stdin):
    if os.environ.get("CLIPBOARD_STATE", "data") in ("sensitive", "clear", "nil"):
        return
    data = stdin.buffer.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    directory = _image_dir()
    os.makedirs(directory, mode=0o700, exist_ok=True)
    path = os.path.join(directory, hashlib.sha256(data).hexdigest() + ".png")
    with open(path, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
    os.utime(path)
    for old in [os.path.join(directory, name) for name in os.listdir(directory)
                if name.endswith(".png") and name != os.path.basename(path)]:
        try:
            age = time.time() - os.path.getmtime(old)
            if old not in image_paths() or age >= EXPIRE_SECONDS:
                os.remove(old)
        except OSError:
            pass


def _key(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _meta():
    try:
        with open(_meta_path(), encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_meta(meta):
    path = _meta_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".new"
    with open(temporary, "w", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(meta, stream)
    os.replace(temporary, path)


def pinned(text):
    return bool(_meta().get(_key(text), {}).get("pinned"))


def info(text, meta=None):
    """What is known about one entry: whether it is pinned and when it arrived.
    Pass meta from _meta() when asking about a whole list, to read it once."""
    entry = (meta if meta is not None else _meta()).get(_key(text), {})
    return {"pinned": bool(entry.get("pinned")), "time": entry.get("time", 0)}


def entries():
    """The history as (text, info) pairs, in the order load() gives them."""
    meta = _meta()
    return [(text, info(text, meta)) for text in load()]


def pin(text, value=True):
    if text not in load():
        return False
    meta = _meta()
    key = _key(text)
    entry = meta.get(key, {})
    entry["pinned"] = bool(value)
    entry["time"] = time.time()
    meta[key] = entry
    _save_meta(meta)
    return True


def delete(text):
    items = [item for item in load() if item != text]
    _save(items)
    meta = _meta()
    meta.pop(_key(text), None)
    _save_meta(meta)


def load():
    try:
        with open(history_path()) as f:
            items = json.load(f)
        meta = _meta()
        now = time.time()
        valid = [i for i in items if isinstance(i, str) and
                 (meta.get(_key(i), {}).get("pinned") or
                  now - meta.get(_key(i), {}).get("time", now) < EXPIRE_SECONDS)]
        return sorted(valid, key=lambda i: not meta.get(_key(i), {}).get("pinned", False))
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
        meta = _meta()
        meta[_key(data)] = {"time": time.time(),
                            "pinned": bool(meta.get(_key(data), {}).get("pinned"))}
        _save_meta(meta)


def clear():
    for path in (history_path(), _meta_path()):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    try:
        for name in os.listdir(_image_dir()):
            if name.endswith(".png"):
                os.remove(os.path.join(_image_dir(), name))
    except OSError:
        pass


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "store":
        store()
    elif cmd == "store-image":
        store_image()
    elif cmd == "list":
        for item in load():
            print(item.replace("\n", "⏎"))
    elif cmd == "show":
        from aurora.clipboardapp import main as window
        return window()
    elif cmd == "clear":
        clear()
    else:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    return 0
