"""The background that moves: what it draws, and when it refuses to."""

import pytest

from aurora.shell import livingwallpaper as living


def test_a_band_of_light_spans_the_screen_and_stays_in_the_top_half():
    points = living.ribbon(phase=0.0, index=0, width=1920, height=1080)
    assert points[0][0] == 0 and points[-1][0] == 1920
    assert len(points) == 25
    assert all(0 < y < 540 for _x, y in points), "a band must not wander down the screen"


def test_the_bands_are_stacked_and_move_with_time():
    first = living.ribbon(0.0, 0, 1920, 1080)
    second = living.ribbon(0.0, 1, 1920, 1080)
    assert second[0][1] > first[0][1], "each band hangs below the one before"
    later = living.ribbon(3.0, 0, 1920, 1080)
    assert later != first, "the same band at another moment is in another place"
    # The same moment always gives the same picture.
    assert living.ribbon(3.0, 0, 1920, 1080) == later


def test_an_unknown_setting_leaves_the_background_still(monkeypatch):
    class Fake:
        def __init__(self, value):
            self.value = value

        def get_string(self, _key):
            return self.value
    monkeypatch.setattr(living.settings, "get", lambda *a: Fake("aurora"))
    assert living.style() == "aurora"
    monkeypatch.setattr(living.settings, "get", lambda *a: Fake("zoom"))
    assert living.style() == "zoom"
    monkeypatch.setattr(living.settings, "get", lambda *a: Fake("disco"))
    assert living.style() == "off"
    monkeypatch.setattr(living.settings, "get", lambda *a: None)
    assert living.style() == "aurora"
