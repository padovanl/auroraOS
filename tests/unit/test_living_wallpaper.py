"""The light added over the background picture: what it is made of, when it
is drawn at all, and that it is the same light at the same moment."""

import cairo
import pytest

from aurora.shell import livingwallpaper as living

ACCENT = (0.66, 0.44, 1.0)


def frame(motion, phase, width=160, height=90, path=""):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    living.paint(living.layers(motion, path), cairo.Context(surface), width, height, phase,
                 ACCENT, living.place(path))
    return bytes(surface.get_data())


def test_only_the_motions_that_are_offered_have_layers():
    assert set(living.MOTIONS) == {"off", "auto", "zoom", "aurora", "stars", "clouds", "shimmer"}
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
    assert living.style() == "auto"


def test_the_schema_offers_exactly_those_motions():
    import xml.etree.ElementTree as ET
    from pathlib import Path
    schema = Path(__file__).resolve().parents[2] / "desktop" / "data" / "schemas" / \
        "org.aurora.desktop.gschema.xml"
    tree = ET.fromstring(schema.read_text(encoding="utf-8"))
    key = [k for k in tree.iter("key") if k.get("name") == "wallpaper-animation"][0]
    assert {c.get("value") for c in key.iter("choice")} == set(living.MOTIONS)
    assert key.find("default").text.strip("'") == "auto"


def test_settings_names_every_motion():
    from aurora.settingsapp.backgrounds import MOTION_LABELS, MOTIONS
    assert set(MOTIONS) == set(living.MOTIONS) == set(MOTION_LABELS)


@pytest.mark.parametrize("scene", ["northern-lights", "wave", "nebula", "milky-way",
                                  "sunrise", "ringed-planet"])
def test_each_included_scene_has_its_own_moving_layers(scene):
    from pathlib import Path
    path = f"/usr/share/backgrounds/aurora/aurora-{scene}.png"
    assert (Path(__file__).resolve().parents[2] / "branding/wallpapers/scenes" /
            f"{scene}.png").is_file()
    assert living.layers("auto", path)
    assert set(living.layers("auto", path)) <= set(living.PAINTERS)
    assert any(frame("auto", 0, path=path))
    assert frame("auto", 0, path=path) != frame("auto", 6, path=path)
    assert frame("off", 6, path=path) == bytes(160 * 90 * 4)


def test_auto_leaves_personal_photos_and_solid_colors_still():
    assert living.layers("auto", "/home/user/Pictures/holiday.jpg") == ()
    assert living.layers("auto", "/home/user/.local/share/aurora/solid/solid-123456.png") == ()


def test_cover_keeps_light_registered_to_the_cropped_picture():
    scale, x, y = living.cover_geometry(1920, 1080, 1920, 720)
    assert scale == 1.5
    assert (x, y) == (-480, 0)
    assert (x + 1920 * scale / 2, y + 720 * scale / 2) == (960, 540)
    scale, x, y = living.cover_geometry(1920, 1080, 1000, 1000)
    assert scale == 1.92
    assert (x, y) == (0, -420)


def test_power_saver_uses_the_service_current_profile():
    from types import SimpleNamespace
    subject = SimpleNamespace(shell=SimpleNamespace(power_profiles=SimpleNamespace(current="power-saver")))
    assert living.LivingWallpaper.saving_power(subject)
    subject.shell.power_profiles.current = "balanced"
    assert not living.LivingWallpaper.saving_power(subject)


def test_only_a_visible_maximized_window_pauses_the_animation():
    from types import SimpleNamespace
    window = SimpleNamespace(minimized=False, maximized=True, fullscreen=False)
    subject = SimpleNamespace(shell=SimpleNamespace(toplevels=SimpleNamespace(toplevels=[window])))
    assert living.LivingWallpaper.covered(subject)
    window.minimized = True
    assert not living.LivingWallpaper.covered(subject)


def test_reflections_move_the_photo_only_below_the_waterline():
    width, height = 160, 90
    photo = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(photo)
    for x in range(0, width, 5):
        cr.set_source_rgb(x / width, .2, .5)
        cr.rectangle(x, 0, 5, height)
        cr.fill()
    frames = []
    for phase in (0, 2):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)
        cr.set_source_surface(photo)
        cr.paint()
        living.draw_ripples(cr, width, height, phase, photo,
                           {"ripple": .7, "ripple_strength": .025})
        frames.append(bytes(surface.get_data()))
    waterline = 63 * width * 4
    assert frames[0][:waterline] == frames[1][:waterline]
    assert frames[0][waterline:] != frames[1][waterline:]
