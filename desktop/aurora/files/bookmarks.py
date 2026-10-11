"""Folder favorites shared with GTK file choosers, including network locations."""
import os

from gi.repository import Gio, GLib


def path():
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(config, "gtk-3.0", "bookmarks")


def _load():
    file = Gio.File.new_for_path(path())
    try:
        _ok, data, etag = file.load_contents(None)
    except GLib.Error as err:
        if not err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND):
            raise
        etag = None
        try:
            _ok, data, _legacy_etag = Gio.File.new_for_path(
                os.path.expanduser("~/.gtk-bookmarks")).load_contents(None)
        except GLib.Error as legacy_error:
            if not legacy_error.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_FOUND):
                raise
            data = b""
    entries = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        uri, _sep, label = line.partition(" ")
        if not uri or ":" not in uri or "\ufffd" in line or any(c.isspace() for c in uri):
            continue
        location = Gio.File.new_for_uri(uri)
        if not any(location.equal(old) for old, _label in entries):
            entries.append((location, label))
    return entries, etag


def read():
    return _load()[0]


def _change(location, label=None, remove=False):
    if label is not None and (not label.strip() or any(c in label for c in "\n\r\0")):
        raise ValueError("invalid bookmark label")
    file = Gio.File.new_for_path(path())
    try:
        file.get_parent().make_directory_with_parents(None)
    except GLib.Error as err:
        if not err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.EXISTS):
            raise
    # The etag detects concurrent edits by other apps. Re-read those edits and
    # apply just this change rather than overwriting another app's favorites.
    for attempt in range(3):
        entries, etag = _load()
        index = next((i for i, (old, _name) in enumerate(entries) if old.equal(location)), None)
        if remove:
            if index is None:
                return
            entries.pop(index)
        elif index is None:
            entries.append((location, label or ""))
        elif label is None:
            return
        else:
            entries[index] = (location, label.strip())
        content = "".join(item.get_uri() + (" " + name if name else "") + "\n"
                          for item, name in entries).encode("utf-8")
        try:
            file.replace_contents(content, etag, False, Gio.FileCreateFlags.PRIVATE, None)
            return
        except GLib.Error as err:
            if attempt == 2 or not err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.WRONG_ETAG):
                raise


def add(location, label=None):
    _change(location, label)


def remove(location):
    _change(location, remove=True)


def rename(location, label):
    _change(location, label)
