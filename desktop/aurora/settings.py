"""Access to Aurora and GNOME interface GSettings."""

from gi.repository import Gio

AURORA_SCHEMA = "org.aurora.desktop"
INTERFACE_SCHEMA = "org.gnome.desktop.interface"


def _load(schema_id):
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup(schema_id, True) is None:
        return None
    return Gio.Settings.new(schema_id)


_cache = {}


def get(schema_id=AURORA_SCHEMA):
    """Return a Gio.Settings for schema_id, or None if it is not installed."""
    if schema_id not in _cache:
        _cache[schema_id] = _load(schema_id)
    return _cache[schema_id]


def interface():
    return get(INTERFACE_SCHEMA)
