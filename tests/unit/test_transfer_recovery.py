"""Transfers preserve sources and fail promptly on unsafe destinations/files."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from aurora.files import operations
from test_files import run_job


def test_folder_cannot_be_copied_into_itself_through_a_symlink(tmp_path, monkeypatch):
    source = tmp_path / "source"
    child = source / "child"
    child.mkdir(parents=True)
    alias = tmp_path / "alias"
    alias.symlink_to(child, target_is_directory=True)
    copied = []

    def forbidden_copy(*args, **kwargs):
        copied.append(True)
        raise OSError("recursive copy started")
    monkeypatch.setattr(operations.shutil, "copytree", forbidden_copy)
    assert run_job("copy", [str(source)], str(alias))
    assert copied == [] and not (child / "source").exists()


def test_move_to_an_alias_of_the_same_folder_is_a_noop(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    item = source / "notes.txt"
    item.write_text("original")
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    assert run_job("move", [str(item)], str(alias)) == ""
    assert item.read_text() == "original"
    assert list(source.iterdir()) == [item]


def test_move_preserves_a_destination_created_after_name_selection(tmp_path, monkeypatch):
    source = tmp_path / "notes.txt"
    source.write_text("source")
    folder = tmp_path / "target"
    folder.mkdir()
    destination = folder / source.name

    def occupied(*args):
        destination.write_text("occupant")
        return str(destination)
    monkeypatch.setattr(operations, "unique_destination", occupied)
    assert run_job("move", [str(source)], str(folder))
    assert source.read_text() == "source" and destination.read_text() == "occupant"


def test_copy_fifo_returns_an_error_without_waiting_for_a_writer(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    destination = tmp_path / "copy"
    script = """
import sys
from aurora.files.operations import Job
try:
    Job('copy', [], '')._copy_file(sys.argv[1], sys.argv[2])
except OSError:
    sys.exit(0)
sys.exit(1)
"""
    result = subprocess.run([sys.executable, "-c", script, str(fifo), str(destination)],
                            capture_output=True, text=True, timeout=3,
                            env=dict(os.environ, PYTHONPATH=str(Path(__file__).parents[2] / "desktop")))
    assert result.returncode == 0, result.stderr
    assert not destination.exists()


def test_move_folder_to_another_filesystem_keeps_its_contents_and_links(tmp_path):
    if not os.path.isdir("/dev/shm") or os.stat(tmp_path).st_dev == os.stat("/dev/shm").st_dev:
        pytest.skip("needs a second filesystem")
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes").write_text("original")
    (source / "link").symlink_to("notes")
    with tempfile.TemporaryDirectory(prefix="aurora-transfer-", dir="/dev/shm") as folder:
        assert run_job("move", [str(source)], folder) == ""
        copied = Path(folder) / "source"
        assert (copied / "notes").read_text() == "original"
        assert (copied / "link").is_symlink() and os.readlink(copied / "link") == "notes"
        assert not source.exists()
