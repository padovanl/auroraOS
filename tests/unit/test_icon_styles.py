"""The icon styles: five themes from one generator, and the setting that picks
one. The stars and filaments must be the same picture on every build, or an
icon would change under people for no reason."""

import importlib.util
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def generator():
    path = ROOT / "branding" / "icons" / "generate.py"
    spec = importlib.util.spec_from_file_location("aurora_icons", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def themes(generator, tmp_path_factory):
    out = tmp_path_factory.mktemp("icons")
    generator.generate(str(out))
    return out


def test_every_style_is_a_theme_of_its_own(generator, themes):
    assert generator.DEFAULT_STYLE == "galaxy"
    assert set(generator.STYLES) == {"galaxy", "ribbon", "glass", "clay", "bolt"}
    assert generator.STYLE_THEMES["galaxy"] == "Aurora"
    for style, theme in generator.STYLE_THEMES.items():
        for name in (theme, theme + "-Dark"):
            index = themes / name / "index.theme"
            assert index.exists(), f"{name} has no index.theme"
            text = index.read_text(encoding="utf-8")
            assert f"Name={name}\n" in text
            if name not in ("Aurora", "Aurora-Dark"):
                # The styles beside the default carry only their app icons.
                assert "Inherits=Aurora" in text
                assert not (themes / name / "scalable" / "mimetypes").exists()


def test_the_styles_draw_the_same_apps_differently(themes, generator):
    for theme in generator.STYLE_THEMES.values():
        apps = themes / theme / "scalable" / "apps"
        assert (apps / "org.aurora.Files.svg").exists()
        assert (apps / "aurora-logo.svg").exists()
    drawings = {theme: (themes / theme / "scalable" / "apps" / "aurora-logo.svg")
                .read_text(encoding="utf-8") for theme in generator.STYLE_THEMES.values()}
    assert len(set(drawings.values())) == len(drawings), "two styles drew the same icon"
    # ...but the glyph inside is the one glyph, in every one of them.
    for svg in drawings.values():
        assert "M26 98C40 58 58 32 64 28c6 4 24 30 38 70" in svg


def test_an_icon_is_the_same_picture_every_time(generator):
    """The galaxy's stars and the discharge's filaments come from the icon's
    place in the set, not from chance."""
    for style in ("galaxy", "bolt"):
        once = generator.app("#fff", "#000", "<g/>", style=style, seed=3)
        twice = generator.app("#fff", "#000", "<g/>", style=style, seed=3)
        assert once == twice
        assert generator.app("#fff", "#000", "<g/>", style=style, seed=4) != once


def test_every_icon_is_valid_xml(themes, generator):
    for theme in generator.STYLE_THEMES.values():
        apps = themes / theme / "scalable" / "apps"
        for icon in sorted(apps.glob("*.svg")):
            if icon.is_symlink():
                continue
            ET.fromstring(icon.read_text(encoding="utf-8"))


def test_the_brand_icons_are_also_in_hicolor(themes):
    hicolor = themes / "hicolor" / "scalable" / "apps"
    for name in ("aurora-logo", "aurora-assistant", "aurora-devhub", "aurora-gamehub",
                 "org.aurora.Files", "org.aurora.Clipboard"):
        assert (hicolor / f"{name}.svg").exists()


def test_the_setting_chooses_the_theme(generator, monkeypatch):
    from aurora import look
    assert set(look.ICON_STYLES) == set(generator.STYLES)
    assert look.ICON_STYLES["galaxy"] == "Aurora"
    for style, theme in look.ICON_STYLES.items():
        assert theme == generator.STYLE_THEMES[style]

    class FakeSettings:
        def __init__(self, style):
            self.style = style

        def get_string(self, _key):
            return self.style

    monkeypatch.setattr(look.settings, "get", lambda *a: FakeSettings("clay"))
    monkeypatch.setattr(look, "is_dark", lambda: False)
    assert look.icon_theme() == "Aurora-Clay"
    monkeypatch.setattr(look, "is_dark", lambda: True)
    assert look.icon_theme() == "Aurora-Clay-Dark"
    monkeypatch.setattr(look.settings, "get", lambda *a: FakeSettings("nonsense"))
    assert look.icon_theme() == "Aurora-Dark"


def test_the_schema_offers_exactly_those_styles(generator):
    schema = (ROOT / "desktop" / "data" / "schemas" / "org.aurora.desktop.gschema.xml")
    tree = ET.fromstring(schema.read_text(encoding="utf-8"))
    key = [k for k in tree.iter("key") if k.get("name") == "icon-style"]
    assert key, "no icon-style key"
    choices = {c.get("value") for c in key[0].iter("choice")}
    assert choices == set(generator.STYLES)
    assert key[0].find("default").text.strip("'") == generator.DEFAULT_STYLE
