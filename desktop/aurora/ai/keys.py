"""API keys for cloud providers, kept in the login keyring (libsecret).

The keyring is unlocked by the login password and encrypted on disk, the same
place GNOME apps keep passwords. AURORA_AI_KEY overrides it (for tests).
"""

import os

try:
    import gi
    gi.require_version("Secret", "1")
    from gi.repository import Secret
except (ValueError, ImportError):
    Secret = None

SCHEMA = None


def _schema():
    global SCHEMA
    if SCHEMA is None and Secret is not None:
        SCHEMA = Secret.Schema.new("org.aurora.AI", Secret.SchemaFlags.NONE,
                                   {"provider": Secret.SchemaAttributeType.STRING})
    return SCHEMA


def get(provider):
    if os.environ.get("AURORA_AI_KEY"):
        return os.environ["AURORA_AI_KEY"]
    if _schema() is None:
        return ""
    try:
        return Secret.password_lookup_sync(_schema(), {"provider": provider}, None) or ""
    except Exception:  # noqa: BLE001 - no keyring (e.g. a bare session): no key
        return ""


def set(provider, key):
    if _schema() is None:
        raise RuntimeError("the keyring is not available")
    if key:
        Secret.password_store_sync(_schema(), {"provider": provider}, Secret.COLLECTION_DEFAULT,
                                   f"Aurora AI: {provider} API key", key, None)
    else:
        Secret.password_clear_sync(_schema(), {"provider": provider}, None)
