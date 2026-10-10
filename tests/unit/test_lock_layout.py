"""The custom GTK3 layout must preserve every control gtklock binds to."""

from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]


def test_lock_layout_keeps_gtklock_contract():
    path = ROOT / "desktop/data/style/lock.ui"
    tree = ET.parse(path)
    objects = {node.attrib["id"]: node for node in tree.findall(".//object[@id]")}
    expected = {
        "window-box": "GtkBox", "body-revealer": "GtkRevealer", "body-grid": "GtkGrid",
        "info-box": "GtkBox", "time-box": "GtkBox", "clock-label": "GtkLabel",
        "date-label": "GtkLabel", "input-label": "GtkLabel", "input-field": "GtkEntry",
        "message-revealer": "GtkRevealer", "message-scrolled-window": "GtkScrolledWindow",
        "message-box": "GtkBox", "unlock-button": "GtkButton", "error-label": "GtkLabel",
        "warning-label": "GtkLabel",
    }
    for ident, klass in expected.items():
        assert objects[ident].attrib["class"] == klass
    assert not objects["window-box"].findall("property[@name='margin']")
    signals = [node.attrib["handler"] for node in tree.findall(".//signal")]
    assert signals.count("window_pw_check") == 2
    assert signals.count("window_pw_toggle_vis") == 1
    script = (ROOT / "desktop/bin/aurora-lock").read_text()
    # The layout and the style come from where Aurora is installed: /usr on a
    # real system, the session's own tree when the desktop is run from one.
    assert 'prefix=${AURORA_PREFIX:-/usr}' in script
    assert 'style_dir="$prefix/share/aurora/style"' in script
    assert '--layout "$run/lock.ui"' in script
    text = path.read_text()
    assert "@NAME@" in text and "@INITIAL@" in text
