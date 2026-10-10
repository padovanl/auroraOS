"""The light added over the background picture: what it is made of, when it
is drawn at all, and that it is the same light at the same moment."""

import cairo
import pytest

from aurora.shell import livingwallpaper as living

ACCENT = (0.66, 0.44, 1.0)


def frame(motion, phase, width=160, height=90):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    living.paint(living.layers(motion), cairo.Context(surface), width, height, phase, ACCENT)
    return bytes(surface.get_data())


def test_only_the_motions_that_are_offered_have_layers():
    assert living.MOTIONS == ("off", "zoom", "aurora")
    assert living.layers("aurora") == ("aurora",)
    # "off" leaves the picture alone, and "zoom" is GTK's to animate, not ours.
    assert living.layers("off") == ()
    assert living.layers("zoom") == ()
    assert living.layers("disco") == ()


def test_the_aurora_is_drawn_and_moves():
    still = frame("aurora", 0.0)
    later = frame("aurora", 6.0)
    assert any(still), "nothing was drawn"
    assert still != later, "the same picture at another moment"
    # The same moment always draws the same light.
    assert frame("aurora", 6.0) == later


def test_a_motion_with_no_layers_draws_nothing():
    assert not any(frame("off", 3.0))
    assert not any(frame("zoom", 3.0))


def test_the_light_keeps_off_the_ground_of_the_picture():
    """The curtains fade out before the foot of the picture: a photograph's
    hills must not have a green wash over them."""
    width, height = 120, 120
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    living.paint(("aurora",), cairo.Context(surface), width, height, 2.0, ACCENT)
    data = bytes(surface.get_data())
    stride = surface.get_stride()

    def row_weight(y):
        row = data[y * stride:(y + 1) * stride]
        return sum(row[3::4])            # the alpha of that row

    assert row_weight(int(height * 0.25)) > 0
    assert row_weight(int(height * 0.95)) == 0


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


def test_the_schema_offers_exactly_those_motions():
    import xml.etree.ElementTree as ET
    from pathlib import Path
    schema = Path(__file__).resolve().parents[2] / "desktop" / "data" / "schemas" / \
        "org.aurora.desktop.gschema.xml"
    tree = ET.fromstring(schema.read_text(encoding="utf-8"))
    key = [k for k in tree.iter("key") if k.get("name") == "wallpaper-animation"][0]
    assert {c.get("value") for c in key.iter("choice")} == set(living.MOTIONS)
    assert key.find("default").text.strip("'") == "aurora"


def test_settings_names_every_motion():
    from aurora.settingsapp.backgrounds import MOTION_LABELS, MOTIONS
    assert set(MOTIONS) == set(living.MOTIONS) == set(MOTION_LABELS)
