"""Real GTK transfers to a mounted SFTP fixture, with GVFS's standard FUSE bridge."""
import sys
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gio, GLib
from aurora.files.app import FilesApp
from aurora.files import bookmarks


def wait(predicate, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError("Network file operation timed out")


uri, directory = sys.argv[1:]
root = Path(directory)
source = root / "local"
source.mkdir(exist_ok=True)
(source / "notes.txt").write_text("network copy\n")
(source / "move.txt").write_text("network move\n")
app = FilesApp()
app.register(None)
local = app.open_window(Gio.File.new_for_path(str(source)))
remote_file = Gio.File.new_for_uri(uri)
remote = app.open_window(remote_file)
wait(lambda: remote.current is not None and remote.current.equal(remote_file)
     and not remote.dirlist.is_loading() and not local.dirlist.is_loading())
path = remote.current.get_path()
assert path and Path(path).is_dir(), "mounted network location must have a GVFS FUSE path"
assert not remote.current.is_native()
print("ok: SFTP opens without blocking and exposes a normal filesystem path", flush=True)


def select(window, name):
    wait(lambda: any(window.model.get_item(i).get_name() == name for i in range(window.model.get_n_items())))
    index = next(i for i in range(window.model.get_n_items()) if window.model.get_item(i).get_name() == name)
    window.selection.select_item(index, True)


select(local, "notes.txt")
local.to_clipboard("copy")
remote.paste()
wait(lambda: (Path(path) / "notes.txt").exists() and not remote.jobs)
assert (Path(path) / "notes.txt").read_text() == "network copy\n"
remote.undo()
wait(lambda: not (Path(path) / "notes.txt").exists() and not remote._history_busy)
remote.redo()
wait(lambda: (Path(path) / "notes.txt").exists() and not remote._history_busy)
print("ok: copy to SFTP, undo and redo preserve local sources", flush=True)
select(local, "move.txt")
local.to_clipboard("move")
remote.paste()
wait(lambda: (Path(path) / "move.txt").exists() and not (source / "move.txt").exists() and not remote.jobs)
remote.undo()
wait(lambda: (source / "move.txt").exists() and not (Path(path) / "move.txt").exists() and not remote._history_busy)
print("ok: cut to SFTP and undo restore the local file", flush=True)
(source / "dropped.txt").write_text("drop\n")
assert remote._drop_on_location(Gdk.FileList.new_from_list([
    Gio.File.new_for_path(str(source / "dropped.txt"))]), remote.current)
wait(lambda: (Path(path) / "dropped.txt").exists() and not remote.jobs)
assert (Path(path) / "dropped.txt").read_text() == "drop\n"
print("ok: file drop to the network folder completes", flush=True)
select(remote, "notes.txt")
remote.to_clipboard("copy")
local.paste()
wait(lambda: (source / "notes (2).txt").exists() and not local.jobs)
assert (source / "notes (2).txt").read_text() == "network copy\n"
print("ok: copy from SFTP preserves the existing local filename", flush=True)
remote.selection.unselect_all()
remote.add_to_sidebar()
wait(lambda: any(file.equal(remote_file) for file, label in bookmarks.read()))
bookmarks.remove(remote_file)
remote.close()
local.close()
print("ALL NETWORK FILE CHECKS PASSED", flush=True)
