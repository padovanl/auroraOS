from types import SimpleNamespace
from aurora.shell.previews import visible_geometry


def test_partly_offscreen_window_is_cropped_at_both_edges():
    screen = SimpleNamespace(x=0, y=0, width=1280, height=800)
    assert visible_geometry(dict(x=-100, y=700, width=1500, height=200),
                            [screen]) == (0, 700, 1280, 100)


def test_monitor_left_of_primary_keeps_its_negative_coordinates():
    screens = [SimpleNamespace(x=-1280, y=0, width=1280, height=800),
               SimpleNamespace(x=0, y=0, width=1920, height=1080)]
    assert visible_geometry(dict(x=-1000, y=100, width=800, height=600),
                            screens) == (-1000, 100, 800, 600)
    assert visible_geometry(dict(x=-100, y=100, width=300, height=600),
                            screens) == (-100, 100, 300, 600)


def test_fully_offscreen_windows_are_not_captured():
    screen = SimpleNamespace(x=0, y=0, width=1280, height=800)
    assert visible_geometry(dict(x=1300, y=0, width=800, height=600), [screen]) is None
