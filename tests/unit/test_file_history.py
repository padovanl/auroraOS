import pytest

from aurora.files.history import Entry, History


def test_copy_undo_redo(tmp_path):
    src = tmp_path / "main.py"
    dst = tmp_path / "main (2).py"
    src.write_text("print(1)")
    dst.write_text("print(1)")
    history = History()
    history.record("copy", [(str(src), str(dst))])
    history.undo()
    assert src.exists() and not dst.exists()
    history.redo()
    assert dst.read_text() == "print(1)"


def test_modified_copy_cannot_be_undone(tmp_path):
    src, dst = tmp_path / "a", tmp_path / "b"
    src.write_text("original")
    dst.write_text("original")
    history = History()
    history.record("copy", [(str(src), str(dst))])
    dst.write_text("edited")
    with pytest.raises(OSError):
        history.undo()
    assert dst.read_text() == "edited"
    assert len(history.undo_stack) == 1


def test_move_undo_redo_never_overwrites(tmp_path):
    src, dst = tmp_path / "old", tmp_path / "new"
    dst.write_text("content")
    history = History()
    history.record("move", [(str(src), str(dst))])
    src.write_text("occupant")
    with pytest.raises(FileExistsError):
        history.undo()
    assert src.read_text() == "occupant" and dst.read_text() == "content"
    src.unlink()
    history.undo()
    assert src.read_text() == "content" and not dst.exists()
    history.redo()
    assert dst.read_text() == "content" and not src.exists()


@pytest.mark.parametrize("kind,name", [("create-file", "new.js"),
                                      ("create-folder", "Project")])
def test_create_undo_redo(tmp_path, kind, name):
    dst = tmp_path / name
    if kind == "create-file":
        dst.touch()
    else:
        dst.mkdir()
    history = History()
    history.record(kind, [(None, str(dst))])
    history.undo()
    assert not dst.exists()
    history.redo()
    assert dst.exists()


def test_nonempty_created_folder_is_preserved(tmp_path):
    dst = tmp_path / "Project"
    dst.mkdir()
    history = History()
    history.record("create-folder", [(None, str(dst))])
    (dst / "notes").touch()
    with pytest.raises(OSError):
        history.undo()
    assert (dst / "notes").exists()


def test_trash_undo_redo_uses_gio_and_refreshes_uri(tmp_path, monkeypatch):
    from gi.repository import Gio
    from aurora.files import history as module

    original = str(tmp_path / "note.txt")
    restored = []
    trashed = []

    class FakeFile:
        def __init__(self, value):
            self.value = value

        def query_exists(self, _cancel):
            return True

        def move(self, destination, _flags, _cancel, _progress):
            restored.append((self.value, destination.value))

        def trash(self, _cancel):
            trashed.append(self.value)

    monkeypatch.setattr(Gio.File, "new_for_uri", lambda uri: FakeFile(uri))
    monkeypatch.setattr(Gio.File, "new_for_path", lambda path: FakeFile(path))
    monkeypatch.setattr(module.os.path, "lexists", lambda path: bool(restored) if path == original else False)
    monkeypatch.setattr(module, "signature", lambda path: ((path, "unchanged"),))
    monkeypatch.setattr(module, "trashed_uri", lambda path: "trash:///new-note.txt")

    entry = Entry("trash", [(original, "trash:///note.txt")])
    entry.undo()
    assert restored == [("trash:///note.txt", original)]
    entry.redo()
    assert trashed == [original]
    assert entry.pairs == [(original, "trash:///new-note.txt")]


def test_modified_restored_trash_item_cannot_be_redone(tmp_path, monkeypatch):
    from gi.repository import Gio

    original = tmp_path / "note.txt"
    original.write_text("edited after restore")
    entry = Entry("trash", [(str(original), "trash:///note.txt")])
    entry.snapshots = (((str(original), "before edit"),),)
    called = []

    class FakeFile:
        def trash(self, _cancel):
            called.append(True)

    monkeypatch.setattr(Gio.File, "new_for_path", lambda _path: FakeFile())
    with pytest.raises(OSError, match="Changed since restore"):
        entry.redo()
    assert not called
    assert original.read_text() == "edited after restore"
