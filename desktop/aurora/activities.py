"""Small per-user activity journal shared by Files and Aurora Shell.

Each job owns one JSON file, so concurrent applications never overwrite each
other's progress. The runtime directory is private and disappears on logout.
"""

import json
import os
import tempfile
import time
import uuid
from pathlib import Path


def directory():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        base = Path(runtime)
    else:
        base = Path.home() / ".cache"
    return base / "aurora-activities"


def create(label, kind, cancellable=True):
    ident = uuid.uuid4().hex
    update(ident, label=label, kind=kind, status="running", progress=0.0, item="",
           cancellable=cancellable)
    return ident


def update(ident, **fields):
    if not ident.isalnum():
        raise ValueError("invalid activity id")
    folder = directory()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / f"{ident}.json"
    try:
        current = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = {"id": ident}
    current.update(fields)
    current["updated"] = time.time()
    fd, name = tempfile.mkstemp(prefix=".activity-", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(current, stream, ensure_ascii=False)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def list_recent(limit=20):
    out = []
    for path in directory().glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(item, dict) and item.get("id") == path.stem:
                out.append(item)
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda item: item.get("updated", 0), reverse=True)[:limit]


def cancel(ident):
    if not ident.isalnum():
        return
    folder = directory()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    (folder / f"{ident}.cancel").touch(mode=0o600)


def cancelled(ident):
    return (directory() / f"{ident}.cancel").exists()
