"""Small per-user activity journal shared by Files and Aurora Shell.

Each job owns one JSON file, so concurrent applications never overwrite each
other's progress. The runtime directory is private to the user; logind removes
it after that user's last session ends.
"""

import json
import math
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
           cancellable=cancellable, owner_pid=os.getpid(),
           owner_start=_process_start(os.getpid()))
    return ident


def _process_start(pid):
    try:
        # comm can contain spaces or parentheses: fields start after its last ).
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19] if fields[0] != "Z" else None
    except (OSError, IndexError, ValueError):
        return None


def _read(path):
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or item.get("id") != path.stem:
            return None
        if item.get("status") not in ("running", "finished", "failed", "cancelled"):
            return None
        updated = item.get("updated", 0)
        if not isinstance(updated, (int, float)) or not math.isfinite(updated):
            return None
        for field in ("label", "kind", "item", "error"):
            if field in item and not isinstance(item[field], str):
                return None
        progress = item.get("progress", 0)
        if not isinstance(progress, (int, float)) or not math.isfinite(progress):
            item["progress"] = 0
        if item["status"] == "running" and item.get("owner_start"):
            pid = item.get("owner_pid")
            if not isinstance(pid, int) or pid <= 0 or _process_start(pid) != item["owner_start"]:
                item["status"] = "failed"
                item["interrupted"] = True
        return item
    except (OSError, ValueError):
        return None


def update(ident, **fields):
    if not ident.isalnum():
        raise ValueError("invalid activity id")
    folder = directory()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / f"{ident}.json"
    try:
        current = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            current = {"id": ident}
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
    out = [item for path in directory().glob("*.json") if (item := _read(path)) is not None]
    out.sort(key=lambda item: (item["status"] != "running", -item.get("updated", 0)))
    return out if limit is None else out[:limit]


def clear_finished():
    """Remove completed records and cancel markers, keeping active work."""
    for item in list_recent(limit=None):
        if item["status"] != "running":
            for suffix in ("json", "cancel"):
                try:
                    (directory() / f"{item['id']}.{suffix}").unlink()
                except FileNotFoundError:
                    pass


def cancel(ident):
    if not ident.isalnum():
        return
    folder = directory()
    item = _read(folder / f"{ident}.json")
    if item is None or item["status"] != "running" or not item.get("cancellable", True):
        return
    (folder / f"{ident}.cancel").touch(mode=0o600)


def cancelled(ident):
    return (directory() / f"{ident}.cancel").exists()
