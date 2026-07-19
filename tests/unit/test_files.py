import os

from gi.repository import GLib

from aurora.files.operations import Job, unique_destination


def run_job(kind, sources, target):
    loop = GLib.MainLoop()
    result = {}
    job = Job(kind, sources, target)
    job.connect("finished", lambda _j, err: (result.setdefault("error", err), loop.quit()))
    job.start()
    GLib.timeout_add_seconds(10, loop.quit)
    loop.run()
    return result.get("error")


def test_unique_destination_adds_counter(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "a (2).txt").write_text("x")
    assert unique_destination(str(tmp_path), "a.txt") == str(tmp_path / "a (3).txt")
    assert unique_destination(str(tmp_path), "new.txt") == str(tmp_path / "new.txt")


def test_unique_destination_hidden_file(tmp_path):
    (tmp_path / ".bashrc").write_text("x")
    assert unique_destination(str(tmp_path), ".bashrc") == str(tmp_path / ".bashrc (2)")


def test_copy_folder_recursively(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "f.txt").write_text("hello")
    dst = tmp_path / "dst"
    dst.mkdir()
    assert run_job("copy", [str(src)], str(dst)) == ""
    assert (dst / "src" / "sub" / "f.txt").read_text() == "hello"
    assert (src / "sub" / "f.txt").exists()


def test_move_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    dst = tmp_path / "dst"
    dst.mkdir()
    assert run_job("move", [str(f)], str(dst)) == ""
    assert not f.exists()
    assert (dst / "f.txt").exists()


def test_copy_into_itself_is_refused(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    err = run_job("copy", [str(src)], str(src))
    assert err
    assert not os.path.exists(src / "src" / "src")
