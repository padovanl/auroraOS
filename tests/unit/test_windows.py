"""Window names in the dock and top bar, and the order of desktop icons."""

from aurora.shell.toplevels import window_labels


class Win:
    def __init__(self, title, serial):
        self.title, self.serial = title, serial
        self.focus_serial = 0


def win(title, serial):
    return Win(title, serial)


def test_same_titles_are_numbered_oldest_first():
    a, b, c, d = win("Terminal", 3), win("Terminal", 1), win("Notes", 2), win("", 4)
    labels = window_labels([a, b, c, d], "Window")
    assert labels[b] == "Terminal 1" and labels[a] == "Terminal 2"
    assert labels[c] == "Notes" and labels[d] == "Window"


def test_desktop_icons_sort_numbers_naturally():
    from aurora.shell.desktopicons import natural_key
    names = ["file-10.txt", "File-2.txt", "file-1.txt"]
    assert sorted(names, key=natural_key) == ["file-1.txt", "File-2.txt", "file-10.txt"]


def test_focusing_a_window_does_not_change_panel_order(monkeypatch):
    from aurora.shell import toplevels

    monkeypatch.setattr(toplevels, "HAVE_BINDINGS", False)
    tracker = toplevels.ToplevelTracker()
    a, b = win("Editor", 0), win("Terminal", 0)
    tracker.added(a)
    tracker.added(b)
    tracker.bump(a)
    assert [w.title for w in sorted(tracker.toplevels, key=lambda w: w.serial)] == [
        "Editor", "Terminal"]
    assert a.focus_serial > b.focus_serial


def test_drop_move_prefers_selected_action_over_possible_actions():
    from gi.repository import Gdk
    from aurora.dnd import is_move

    class Drag:
        def get_selected_action(self):
            return Gdk.DragAction.MOVE

    class Drop:
        def get_drag(self):
            return Drag()

        def get_actions(self):
            return Gdk.DragAction.COPY | Gdk.DragAction.MOVE

    class Target:
        def get_current_drop(self):
            return Drop()

    assert is_move(Target())
