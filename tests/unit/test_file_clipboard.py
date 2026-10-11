"""File clipboard parsing and cut ownership recovery."""
import pytest
from gi.repository import Gio
from aurora.files import clipboard


def test_gnome_cut_supports_spaces_and_deduplicates():
    mode, files = clipboard.decode(b"cut\nfile:///tmp/Project%20Photos\nfile:///tmp/a\nfile:///tmp/a\n")
    assert mode == "move"
    assert [f.get_path() for f in files] == ["/tmp/Project Photos", "/tmp/a"]
    assert clipboard.decode(b"copy\nfile:///tmp/a\n")[0] == "copy"


@pytest.mark.parametrize("data", [b"text", b"copy\n", b"cut\nfile:///a b\n", b"delete\nfile:///a",
                                     b"copy\n\xff", b"copy\nfile:///a\0b"])
def test_invalid_clipboard_does_not_start_a_transfer(data):
    assert clipboard.decode(data) is None


def test_a_new_clipboard_cannot_be_cleared_by_an_old_move(monkeypatch):
    provider = object()
    new_provider = object()
    monkeypatch.setitem(clipboard.STATE, "provider", new_provider)

    class Clip:
        def get_content(self):
            return new_provider
        def set_content(self, _value):
            pytest.fail("old move replaced a newer clipboard")
    clipboard.complete_move(Clip(), provider, {"/tmp/a"})


def test_only_completed_cut_files_are_removed(monkeypatch):
    provider = object()
    files = [Gio.File.new_for_path(p) for p in ("/tmp/a", "/tmp/b")]
    monkeypatch.setitem(clipboard.STATE, "provider", provider)
    monkeypatch.setitem(clipboard.STATE, "files", files)
    published = []
    monkeypatch.setattr(clipboard, "publish", lambda clip, mode, remaining:
                        published.append((mode, [f.get_path() for f in remaining])))

    class Clip:
        def get_content(self):
            return provider
    clipboard.complete_move(Clip(), provider, {"/tmp/a"})
    assert published == [("move", ["/tmp/b"])]
