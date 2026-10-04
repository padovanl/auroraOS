import configparser
from pathlib import Path

from aurora import wayfireconf
from aurora.wayfireconf import display_outputs


def test_display_choices_become_wayfire_outputs():
    text = """# Written by Aurora Settings
wlr-randr --output DP-1 --mode 1920x1080@59.951Hz
wlr-randr --output DP-1 --scale 1.25
wlr-randr --output DP-1 --transform 90
wlr-randr --output HDMI-A-1 --off
"""
    assert display_outputs(text) == {
        "DP-1": {"mode": "1920x1080@59951", "scale": "1.25", "transform": "90"},
        "HDMI-A-1": {"mode": "off"},
    }


def test_turning_an_output_back_on():
    text = "wlr-randr --output HDMI-A-1 --on\n"
    assert display_outputs(text) == {"HDMI-A-1": {}}
    assert display_outputs("wlr-randr --output X --bogus\nnot a command\n") == {"X": {}}


def test_always_on_top_binding_is_translated_for_wayfire(tmp_path, monkeypatch):
    data = Path(__file__).parents[2] / "desktop" / "data"
    monkeypatch.setattr(wayfireconf, "data_path",
                        lambda *parts: str(data.joinpath(*parts)))
    monkeypatch.setattr(wayfireconf, "labwc_path",
                        lambda: str(data / "labwc" / "rc.xml"))
    monkeypatch.setattr(wayfireconf, "config_path",
                        lambda name: str(tmp_path / name))
    monkeypatch.setattr(wayfireconf.settings, "get", lambda: None)
    monkeypatch.setattr(wayfireconf.settings, "interface", lambda: None)
    target = wayfireconf.generate()
    config = configparser.ConfigParser(interpolation=None)
    config.read(target)
    bindings = {key.removeprefix("binding_"): value
                for key, value in config["command"].items() if key.startswith("binding_")}
    name = next(name for name, value in bindings.items() if value == "<super> KEY_T")
    assert config["command"][f"command_{name}"] == "aurora-shell always-on-top"
