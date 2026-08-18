"""Window names in the dock and top bar, and the order of desktop icons."""

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


def test_desktop_icons_sort_numbers_naturally():
    from aurora.shell.desktopicons import natural_key
    names = ["file-10.txt", "File-2.txt", "file-1.txt"]
    assert sorted(names, key=natural_key) == ["file-1.txt", "File-2.txt", "file-10.txt"]
