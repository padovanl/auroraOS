"""Aurora AI: a private assistant that runs on your computer.

Nothing is installed or downloaded until the user turns a feature on in
Settings → AI. Everything then lives in ~/.local/share/aurora/ai:

- llama.cpp's `llama-server` (the runtime) and a GGUF chat model: answers in
  Spotlight (`?`), the Assistant window and the terminal (`ask`, `why`);
- an embedding model for searching documents by meaning;
- a Python venv with faster-whisper (dictation) and Piper (read aloud).

Every download is pinned in catalog.json (URL, size, SHA-256). Users can
also pick a cloud provider (Anthropic Claude, or any OpenAI-compatible API)
with their own key, kept in the login keyring.
"""

import json
import os

from aurora import settings

HERE = os.path.dirname(os.path.abspath(__file__))


def base_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "aurora", "ai")


def state_dir():
    base = os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "aurora-ai")
    os.makedirs(path, exist_ok=True)
    return path


_catalog = None


def catalog():
    global _catalog
    if _catalog is None:
        with open(os.path.join(HERE, "catalog.json")) as f:
            _catalog = json.load(f)
    return _catalog


def enabled():
    s = settings.get()
    return s is not None and s.get_boolean("ai-enabled")


def feature(name):
    """Is an AI feature switched on (and AI itself)? name: spotlight, terminal,
    dictation, read-aloud, semantic-search."""
    s = settings.get()
    return s is not None and s.get_boolean("ai-enabled") and s.get_boolean(f"ai-{name}")


def provider():
    s = settings.get()
    return s.get_string("ai-provider") if s else "local"


def is_private_host(host):
    """This computer or the local network: loopback, private and link-local
    addresses, single-label names and .local, .lan, .home.arpa names."""
    import ipaddress
    host = (host or "").strip("[]").lower()
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private or ip.is_link_local
    except ValueError:
        pass
    return (host == "localhost" or "." not in host
            or host.endswith((".local", ".lan", ".home.arpa", ".internal")))


def stays_private():
    """Does the chosen model run on this computer or the local network? Only
    then may files the user attaches be sent to it (never to a cloud service)."""
    which = provider()
    if which == "local":
        return True
    if which == "openai":
        from urllib.parse import urlparse
        s = settings.get()
        url = s.get_string("ai-openai-url") if s else ""
        return is_private_host(urlparse(url).hostname)
    return False
