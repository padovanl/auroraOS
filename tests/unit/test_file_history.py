import pytest

from aurora.files.history import History


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
