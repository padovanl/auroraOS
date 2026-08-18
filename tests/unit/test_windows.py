"""Windows that share a title are told apart by number, in the dock and the top bar."""

from aurora.shell.toplevels import window_labels


class Win:
    def __init__(self, title, serial):
        self.title, self.serial = title, serial


def win(title, serial):
    return Win(title, serial)


def test_same_titles_are_numbered_oldest_first():
    a, b, c, d = win("Terminal", 3), win("Terminal", 1), win("Notes", 2), win("", 4)
    labels = window_labels([a, b, c, d], "Window")
    assert labels[b] == "Terminal 1" and labels[a] == "Terminal 2"
    assert labels[c] == "Notes" and labels[d] == "Window"
