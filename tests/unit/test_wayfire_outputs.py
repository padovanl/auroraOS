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
