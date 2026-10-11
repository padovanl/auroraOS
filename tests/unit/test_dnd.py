"""What a dropped file list means: its paths, the chosen action, the trash."""

import os
import subprocess
import sys
from pathlib import Path

from gi.repository import Gdk, Gio

from aurora import dnd


class FakeDrop:
    def __init__(self, actions):
        self._actions = actions

    def get_actions(self):
        return self._actions

    def get_drag(self):
        return None


class FakeTarget:
    def __init__(self, actions):
        self._drop = FakeDrop(actions) if actions is not None else None

    def get_current_drop(self):
        return self._drop


def filelist(*paths):
    return Gdk.FileList.new_from_list([Gio.File.new_for_path(p) for p in paths])


def test_paths_keep_their_order_without_repeats():
    assert dnd.file_paths(filelist("/tmp/b", "/tmp/a", "/tmp/b")) == ["/tmp/b", "/tmp/a"]
    # A file on a share has no local path, so there is nothing to hand to an app.
    remote = Gdk.FileList.new_from_list([Gio.File.new_for_uri("sftp://host/x")])
    assert dnd.file_paths(remote) == []
    mixed = Gdk.FileList.new_from_list([Gio.File.new_for_uri("sftp://host/x"),
                                        Gio.File.new_for_path("/tmp/a")])
    assert dnd.file_paths(mixed) == ["/tmp/a"]


def test_the_answer_to_a_drag_is_an_action_it_offered():
    both = Gdk.DragAction.COPY | Gdk.DragAction.MOVE
    # What we want, when it is on offer.
    assert dnd.preferred_action(FakeTarget(both), Gdk.DragAction.COPY) == Gdk.DragAction.COPY
    assert dnd.preferred_action(FakeTarget(both), Gdk.DragAction.MOVE) == Gdk.DragAction.MOVE
    # An external source can offer MOVE alone: answering COPY would call the
    # drop off, so a dock icon that opens files still says MOVE.
    assert dnd.preferred_action(FakeTarget(Gdk.DragAction.MOVE),
                                Gdk.DragAction.COPY) == Gdk.DragAction.MOVE
    assert dnd.preferred_action(FakeTarget(Gdk.DragAction.COPY),
                                Gdk.DragAction.MOVE) == Gdk.DragAction.COPY
    assert dnd.preferred_action(FakeTarget(None), Gdk.DragAction.MOVE) == Gdk.DragAction.MOVE


def test_a_drop_on_the_trash_moves_the_files_there(home):
    kept, gone = home / "kept.txt", home / "gone.txt"
    kept.write_text("here")
    gone.write_text("away")
    # GTK can cache GLib's home/data directories before the home fixture runs.
    # A fresh process keeps this real GIO trash operation inside the test home.
    env = dict(os.environ, XDG_DATA_HOME=str(home / ".local/share"),
               PYTHONPATH=str(Path(__file__).parents[2] / "desktop"))
    subprocess.run([sys.executable, "-c", "from aurora import dnd; import sys; "
                    "assert dnd.to_trash(sys.argv[1:]) == 1", str(gone),
                    str(home / "never-existed")], env=env, check=True)
    assert kept.exists() and not gone.exists()
    trashed = home / ".local" / "share" / "Trash" / "files"
    assert os.path.exists(trashed / "gone.txt")


def test_external_file_drop_respects_ctrl_copy_and_shift_move():
    target = FakeTarget(Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
    target.get_current_event_state = lambda: Gdk.ModifierType.CONTROL_MASK
    assert dnd.file_action(target) == Gdk.DragAction.COPY
    assert not dnd.is_move(target)
    target.get_current_event_state = lambda: Gdk.ModifierType.SHIFT_MASK
    assert dnd.file_action(target) == Gdk.DragAction.MOVE and dnd.is_move(target)


def test_copy_only_drag_source_cannot_be_negotiated_into_a_move():
    target = FakeTarget(Gdk.DragAction.COPY)
    target.get_current_event_state = lambda: Gdk.ModifierType.SHIFT_MASK
    assert dnd.file_action(target) == Gdk.DragAction.COPY and not dnd.is_move(target)


def test_external_drop_keeps_its_copy_action_while_data_arrives():
    target = FakeTarget(Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
    target.get_current_event_state = lambda: Gdk.ModifierType.CONTROL_MASK
    assert dnd.file_action(target) == Gdk.DragAction.COPY
    target.get_current_event_state = lambda: 0
    assert not dnd.is_move(target)
