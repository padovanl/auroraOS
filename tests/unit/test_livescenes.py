"""The animated backgrounds: that they paint something, that a given moment
always paints the same thing, and that they move."""

import cairo
import pytest

from aurora.shell import livescenes

ACCENT = (0.66, 0.44, 1.0)


def frame(name, phase=3.0, width=160, height=90):
    surface = livescenes.still(name, width, height, ACCENT, phase=phase)
    return bytes(surface.get_data())


@pytest.mark.parametrize("name", livescenes.SCENES)
def test_a_scene_paints_a_picture(name):
    data = frame(name)
    assert len(data) > 0
    # Not one flat colour: a background that is a single colour is not a scene.
    assert len(set(data[i:i + 4] for i in range(0, len(data), 4))) > 200


@pytest.mark.parametrize("name", livescenes.SCENES)
def test_the_same_moment_always_paints_the_same_picture(name):
    assert frame(name, phase=2.5) == frame(name, phase=2.5)


@pytest.mark.parametrize("name", livescenes.SCENES)
def test_a_scene_moves(name):
    assert frame(name, phase=0.0) != frame(name, phase=9.0)


def test_an_unknown_scene_paints_the_aurora():
    assert frame("disco") == frame("aurora")


def test_every_scene_has_a_name_in_settings():
    from aurora.settingsapp.backgrounds import SCENE_LABELS, MODES
    assert set(SCENE_LABELS) == set(livescenes.SCENES)
    assert "animated" in MODES


def test_the_schema_offers_exactly_those_scenes():
    import xml.etree.ElementTree as ET
    from pathlib import Path
    schema = Path(__file__).resolve().parents[2] / "desktop" / "data" / "schemas" / \
        "org.aurora.desktop.gschema.xml"
    tree = ET.fromstring(schema.read_text(encoding="utf-8"))
    key = [k for k in tree.iter("key") if k.get("name") == "wallpaper-live-scene"][0]
    choices = {c.get("value") for c in key.iter("choice")}
    assert choices == set(livescenes.SCENES) | {""}
    assert key.find("default").text.strip("'") == ""
