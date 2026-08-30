"""Local, per-user Assistant conversations. No network or global index."""

import json
import os
import tempfile
import time
from pathlib import Path


def path():
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "aurora" / "conversations.json"


def load():
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and
                    isinstance(item.get("messages"), list)][:50]
    except (OSError, ValueError):
        pass
    return []


def save(conversations):
    target = path()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".conversations-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(conversations[:50], stream, ensure_ascii=False)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def upsert(conversations, conversation_id, messages):
    """Return newest first, without writing; callers control save timing."""
    entries = [c for c in conversations if c.get("id") != conversation_id]
    title = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    return [{"id": conversation_id, "title": title[:80], "updated": int(time.time()),
             "messages": list(messages)}, *entries][:50]
