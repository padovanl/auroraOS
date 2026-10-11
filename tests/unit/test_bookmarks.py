"""Favorites use the shared GTK format and preserve concurrent edits."""
from pathlib import Path

import pytest
from gi.repository import Gio, GLib
from aurora.files import bookmarks


def test_bookmarks_roundtrip_and_deduplicate(home):
    folder = home / "Project Photos"
    folder.mkdir()
    location = Gio.File.new_for_path(str(folder))
    bookmarks.add(location, "Foto di città")
    bookmarks.add(location)
    assert [(f.get_path(), label) for f, label in bookmarks.read()] == [(str(folder), "Foto di città")]
    assert "%20" in Path(bookmarks.path()).read_text()
    bookmarks.rename(location, "Work")
    assert bookmarks.read()[0][1] == "Work"
    bookmarks.remove(location)
    assert bookmarks.read() == []


def test_network_and_legacy_favorites_survive_updates(home):
    (home / ".gtk-bookmarks").write_text("sftp://user@server/projects Projects\nfile:///gone Missing\n")
    assert len(bookmarks.read()) == 2
    bookmarks.add(Gio.File.new_for_path(str(home / "local")))
    assert [f.get_uri() for f, _label in bookmarks.read()] == [
        "sftp://user@server/projects", "file:///gone", (home / "local").as_uri()]
    bookmarks.remove(Gio.File.new_for_uri("file:///gone"))
    assert len(bookmarks.read()) == 2


@pytest.mark.parametrize("label", ["", " ", "a\nb", "a\rb", "a\0b"])
def test_bookmark_labels_cannot_create_extra_entries(home, label):
    with pytest.raises(ValueError):
        bookmarks.add(Gio.File.new_for_path(str(home)), label)
    assert not Path(bookmarks.path()).exists()


def test_concurrent_edit_is_reloaded_instead_of_lost(home, monkeypatch):
    location = Gio.File.new_for_path(str(home / "first"))
    bookmarks.add(location)
    original = bookmarks._load
    first = True

    def load():
        nonlocal first
        entries, etag = original()
        if first:
            first = False
            path = Path(bookmarks.path())
            # Force a different file identity and etag, including on filesystems
            # with low timestamp precision.
            path.unlink()
            path.write_text(location.get_uri() + "\nfile:///other External\n")
        return entries, etag
    monkeypatch.setattr(bookmarks, "_load", load)
    bookmarks.rename(location, "Mine")
    assert [(f.get_uri(), label) for f, label in bookmarks.read()] == [
        (location.get_uri(), "Mine"), ("file:///other", "External")]
