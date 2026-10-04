"""Render Aurora's Wayfire configuration from shared desktop preferences.

The labwc XML remains the editable source for Aurora Settings and the fallback
session. Wayfire's INI is generated atomically on login and after changes.
"""

import configparser
import os
import re
import shlex
import xml.etree.ElementTree as ET

from aurora import config_path, data_path, settings
from aurora.labwcconf import path as labwc_path


def path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "aurora", "wayfire.ini")


def _binding(key):
    if not key or key in ("Super_L", "Super_R"):
        return None
    parts = key.split("-")
    modifiers = {"W": "<super>", "C": "<ctrl>", "A": "<alt>", "S": "<shift>"}
    names = {"Return": "ENTER", "space": "SPACE", "period": "DOT",
             "equal": "EQUAL", "minus": "MINUS", "Print": "PRINT",
             "XF86AudioRaiseVolume": "VOLUMEUP", "XF86AudioLowerVolume": "VOLUMEDOWN",
             "XF86AudioMute": "MUTE", "XF86MonBrightnessUp": "BRIGHTNESSUP",
             "XF86MonBrightnessDown": "BRIGHTNESSDOWN"}
    if any(part not in modifiers for part in parts[:-1]):
        return None
    name = names.get(parts[-1], parts[-1].upper())
    if not re.fullmatch(r"[A-Z0-9_]+", name):
        return None
    return " ".join([*(modifiers[p] for p in parts[:-1]), f"KEY_{name}"])


def _xml(root, path, fallback):
    node = root.find(path) if root is not None else None
    return node.text.strip() if node is not None and node.text else fallback


def _bool(value):
    return "true" if value in ("yes", "on", "true", "1") else "false"


def _source_xml():
    for candidate in (labwc_path(), data_path("labwc", "rc.xml")):
        try:
            return ET.parse(candidate).getroot()
        except (OSError, ET.ParseError):
            continue
    return None


def display_outputs(text):
    """Wayfire [output:NAME] options from the wlr-randr commands Settings →
    Displays saves (displays.sh). Wayfire re-reads its configuration whenever
    it is rewritten, and an output it has no section for goes back to its
    preferred mode at scale 1: so the choices live here too."""
    outputs = {}
    for line in text.splitlines():
        try:
            words = shlex.split(line)
        except ValueError:
            continue
        if len(words) < 4 or words[0] != "wlr-randr" or words[1] != "--output":
            continue
        options = outputs.setdefault(words[2], {})
        flag, value = words[3], words[4] if len(words) > 4 else ""
        if flag == "--off":
            options["mode"] = "off"
        elif flag == "--on":
            if options.get("mode") == "off":
                options["mode"] = "auto"
        elif flag == "--mode":
            m = re.fullmatch(r"(\d+)x(\d+)(?:@([\d.]+)Hz)?", value)
            if m:
                refresh = f"@{round(float(m.group(3)) * 1000)}" if m.group(3) else ""
                options["mode"] = f"{m.group(1)}x{m.group(2)}{refresh}"
        elif flag == "--scale" and re.fullmatch(r"[\d.]+", value):
            options["scale"] = value
        elif flag == "--transform" and value in ("normal", "90", "180", "270"):
            options["transform"] = value
    return outputs


def generate():
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read(data_path("wayfire", "wayfire.ini"))
    root = _source_xml()
    aurora = settings.get()
    iface = settings.interface()

    enabled = aurora is None or aurora.get_boolean("window-animations")
    plugins = config["core"]["plugins"].split()
    config["core"]["plugins"] = " ".join(p for p in plugins if enabled or p != "animate")
    try:
        count = max(1, min(9, int(root.find("desktops").get("number", "4"))))
    except (AttributeError, ValueError):
        count = 4
    config["core"]["vwidth"] = str(count)
    config["core"]["vheight"] = "1"
    config["input"] = {
        "kb_repeat_rate": _xml(root, "keyboard/repeatRate", "30"),
        "kb_repeat_delay": _xml(root, "keyboard/repeatDelay", "400"),
        "kb_numlock_default_state": _bool(_xml(root, "keyboard/numlock", "on")),
    }
    env = {}
    environment = os.path.join(os.path.dirname(labwc_path()), "environment")
    try:
        with open(environment, encoding="utf-8") as stream:
            for line in stream:
                key, sep, value = line.strip().partition("=")
                if sep and key.startswith("XKB_DEFAULT_"):
                    env[key] = value.strip().strip('"')
    except OSError:
        pass
    for name in ("LAYOUT", "VARIANT", "OPTIONS", "MODEL"):
        value = env.get(f"XKB_DEFAULT_{name}") or os.environ.get(f"XKB_DEFAULT_{name}")
        if value:
            config["input"][f"xkb_{name.lower() if name != 'OPTIONS' else 'options'}"] = value
    devices = root.find("libinput") if root is not None else None
    for category, prefix in (("default", "mouse"), ("touchpad", "touchpad")):
        device = next((d for d in devices.findall("device") if d.get("category") == category), None) \
            if devices is not None else None
        if device is None:
            continue
        values = {child.tag: child.text for child in device if child.text}
        config["input"][f"{prefix}_cursor_speed"] = values.get("pointerSpeed", "0")
        config["input"][f"{prefix}_accel_profile"] = values.get("accelProfile", "adaptive")
        if category == "default":
            config["input"]["mouse_natural_scroll"] = _bool(values.get("naturalScroll"))
            config["input"]["left_handed_mode"] = _bool(values.get("leftHanded"))
        else:
            config["input"]["tap_to_click"] = _bool(values.get("tap", "yes"))
            config["input"]["natural_scroll"] = _bool(values.get("naturalScroll", "yes"))
            config["input"]["disable_touchpad_while_typing"] = _bool(
                values.get("disableWhileTyping", "yes"))
            config["input"]["scroll_method"] = {
                "twofinger": "two-finger", "edge": "edge"}.get(
                    values.get("scrollMethod"), "two-finger")
            config["input"]["click_method"] = {
                "buttonAreas": "button-areas", "clickfinger": "clickfinger"}.get(
                    values.get("clickMethod"), "clickfinger")
    if iface is not None:
        config["input"]["cursor_theme"] = iface.get_string("cursor-theme")
        config["input"]["cursor_size"] = str(iface.get_int("cursor-size"))

    # Native Wayfire bindings supply window management. Reuse the command
    # bindings in Settings, including any user-added shortcut.
    config["command"] = {}
    keyboard = root.find("keyboard") if root is not None else None
    if keyboard is not None:
        for index, keybind in enumerate(keyboard.findall("keybind")):
            action = keybind.find("action")
            key = _binding(keybind.get("key"))
            if key and action is not None and action.get("name") == "Execute":
                name = f"aurora_{index}"
                prefix = "release_binding" if keybind.get("onRelease") == "yes" else "binding"
                config["command"][f"{prefix}_{name}"] = key
                config["command"][f"command_{name}"] = action.get("command", "")
            elif key and action is not None and action.get("name") == "SnapToRegion" \
                    and action.get("region", "").endswith("-third"):
                # Thirds: no native Wayfire slot, the shell places the window.
                name = f"aurora_{index}"
                config["command"][f"binding_{name}"] = key
                config["command"][f"command_{name}"] = \
                    f"aurora-shell snap {action.get('region')}"
            elif key and action is not None and action.get("name") == "ToggleAlwaysOnTop":
                # labwc owns this action natively. Wayfire needs Aurora's IPC
                # bridge, while keeping the same shared shortcut definition.
                name = f"aurora_{index}"
                config["command"][f"binding_{name}"] = key
                config["command"][f"command_{name}"] = "aurora-shell always-on-top"
    config["vswitch"] = {
        "binding_left": "<ctrl> <alt> KEY_LEFT",
        "binding_right": "<ctrl> <alt> KEY_RIGHT",
    }
    # Super+1…9 goes to a workspace, Super+Shift+1…9 sends the window there,
    # as in the labwc session.
    for n in range(1, 10):
        config["vswitch"][f"binding_{n}"] = f"<super> KEY_{n}"
        config["vswitch"][f"send_win_{n}"] = f"<super> <shift> KEY_{n}"
    config.setdefault("switcher", {})
    config["switcher"]["next_view"] = "<alt> KEY_TAB | <super> KEY_TAB"
    config["switcher"]["prev_view"] = "<alt> <shift> KEY_TAB"
    config["wm-actions"]["minimize"] = "<super> KEY_M"
    config["wm-actions"]["toggle_fullscreen"] = "<super> KEY_F"
    config["core"]["close_top_view"] = "<alt> KEY_F4 | <super> KEY_Q"
    config["grid"].update({"slot_l": "<super> KEY_LEFT", "slot_r": "<super> KEY_RIGHT",
                           "slot_c": "<super> KEY_UP", "restore": "<super> KEY_DOWN"})

    try:
        with open(config_path("displays.sh"), encoding="utf-8") as stream:
            for name, options in display_outputs(stream.read()).items():
                config[f"output:{name}"] = options
    except OSError:
        pass

    target = path()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temporary = target + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        config.write(stream)
    os.replace(temporary, target)
    return target
