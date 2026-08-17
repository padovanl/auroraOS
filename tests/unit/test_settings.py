"""Settings shows shortcuts in words and text exactly as written."""

import os
import xml.etree.ElementTree as ET

from aurora.settingsapp.inputs import describe_shortcut

RC = os.path.join(os.path.dirname(__file__), "..", "..", "desktop", "data", "labwc", "rc.xml")


def keybinds():
    for kb in ET.parse(RC).getroot().iter():
        if kb.tag.endswith("keybind"):
            action = kb.find("action")
            yield kb.get("key"), action.get("name"), action.get("command"), kb


def test_every_built_in_shortcut_has_a_description():
    for key, action, command, element in keybinds():
        text = describe_shortcut(action, command, element)
        assert text, key
        # No raw commands or compositor action names shown to people.
        assert "aurora-shell" not in text and text != action, (key, text)


def test_workspaces_and_regions_read_naturally():
    kb = ET.fromstring('<keybind key="W-3"><action name="GoToDesktop" to="3" /></keybind>')
    assert describe_shortcut("GoToDesktop", None, kb) == "Go to workspace 3"
    kb = ET.fromstring('<keybind key="W-C-u"><action name="SnapToRegion" region="top-left" /></keybind>')
    assert describe_shortcut("SnapToRegion", None, kb) == "Move window to the top-left quarter"


def test_custom_shortcuts_show_their_command():
    kb = ET.fromstring('<keybind key="W-g" aurora-custom="yes">'
                       '<action name="Execute" command="gimp" /></keybind>')
    assert describe_shortcut("Execute", "gimp", kb) == "gimp"
