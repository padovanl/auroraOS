"""labwc config editing, GTK stylesheet management, autostart filtering."""

import importlib.machinery
import importlib.util
import os
import xml.etree.ElementTree as ET

import pytest

from aurora import labwcconf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def no_reconfigure(monkeypatch):
    monkeypatch.setattr(labwcconf.subprocess, "run", lambda *a, **k: None)


def test_config_is_seeded_from_defaults(home, no_reconfigure):
    cfg = labwcconf.Config()
    assert os.path.exists(labwcconf.path())
    assert cfg.get("theme", "name") == "Aurora"


def test_set_and_device_values_persist(home, no_reconfigure):
    cfg = labwcconf.Config()
    cfg.set("core", "gap", value=10)
    cfg.device_set("touchpad", "tap", "no")
    cfg.save()
    again = labwcconf.Config()
    assert again.get("core", "gap") == "10"
    assert again.device_get("touchpad", "tap") == "no"
    ET.parse(labwcconf.path())  # still valid XML


def test_custom_keybind_roundtrip(home, no_reconfigure):
    cfg = labwcconf.Config()
    before = len(cfg.keybinds())
    cfg.add_command_keybind("W-C-x", "echo hi")
    cfg.save()
    cfg = labwcconf.Config()
    custom = [k for k in cfg.keybinds() if k[3].get("aurora-custom") == "yes"]
    assert custom and custom[0][0] == "W-C-x" and custom[0][2] == "echo hi"
    cfg.remove(custom[0][3])
    cfg.save()
    assert len(labwcconf.Config().keybinds()) == before


def test_gtk_css_keeps_user_rules(home):
    from aurora import look
    path = os.path.join(str(home), ".config", "gtk-4.0", "gtk.css")
    os.makedirs(os.path.dirname(path))
    with open(path, "w") as f:
        f.write("label { color: red; }\n")
    look._write_gtk_css("4", ["/x/a.css"])
    look._write_gtk_css("4", ["/x/b.css"])
    text = open(path).read()
    assert "label { color: red; }" in text
    assert "b.css" in text and "a.css" not in text


def load_script(name):
    path = os.path.join(ROOT, "desktop", "bin", name)
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.mark.parametrize("content, wanted", [
    ("", True),
    ("Hidden=true\n", False),
    ("OnlyShowIn=GNOME;\n", False),
    ("OnlyShowIn=GNOME;Aurora;\n", True),
    ("NotShowIn=Aurora;\n", False),
    ("TryExec=definitely-not-installed-xyz\n", False),
    ("X-GNOME-Autostart-enabled=false\n", False),
])
def test_autostart_filter(tmp_path, content, wanted):
    autostart = load_script("aurora-autostart")
    f = tmp_path / "x.desktop"
    f.write_text("[Desktop Entry]\nType=Application\nName=X\nExec=true\n" + content)
    assert autostart.wanted(str(f), ["aurora", "wlroots"]) is wanted
