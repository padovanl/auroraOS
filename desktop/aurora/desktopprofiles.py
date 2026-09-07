"""Named sets of desktop, wallpaper, notification and power preferences."""

import json
import os
import re
import subprocess
import tempfile

from aurora import settings

KEYS = ("dock-position", "dock-style", "dock-autohide", "dock-magnification",
        "panel-opacity", "do-not-disturb", "window-animations", "wallpaper",
        "wallpaper-dynamic", "wallpaper-slideshow")

BUILTINS = {
    "work": {"dock-position": "bottom", "dock-autohide": False,
             "do-not-disturb": False, "window-animations": True, "power": "balanced"},
    "gaming": {"dock-position": "bottom", "dock-autohide": True,
               "do-not-disturb": True, "window-animations": True,
               "power": "performance"},
    "battery": {"dock-autohide": True, "dock-magnification": False,
                "do-not-disturb": False, "window-animations": False,
                "wallpaper-dynamic": False, "wallpaper-slideshow": False,
                "power": "power-saver"},
}


def path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "aurora", "desktop-profiles.json")


def load():
    try:
        with open(path(), encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(name):
    name = name.strip()
    if not name or len(name) > 40 or not re.fullmatch(r"[^/\\\x00-\x1f]+", name):
        raise ValueError("invalid profile name")
    desktop = settings.get()
    if desktop is None:
        raise RuntimeError("settings unavailable")
    values = {key: desktop.get_value(key).unpack() for key in KEYS}
    try:
        power = subprocess.run(["powerprofilesctl", "get"], capture_output=True,
                               text=True, timeout=4)
        if power.returncode == 0:
            values["power"] = power.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    profiles = load()
    profiles[name] = values
    target = path()
    os.makedirs(os.path.dirname(target), mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".profiles-", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(profiles, stream, ensure_ascii=False)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(name):
    values = BUILTINS.get(name) or load().get(name)
    if not isinstance(values, dict):
        return False
    desktop = settings.get()
    if desktop is None:
        return False
    for key in KEYS:
        value = values.get(key)
        if isinstance(value, bool):
            desktop.set_boolean(key, value)
        elif isinstance(value, float):
            desktop.set_double(key, value)
        elif isinstance(value, str):
            desktop.set_string(key, value)
    if values.get("power") in ("performance", "balanced", "power-saver"):
        try:
            subprocess.run(["powerprofilesctl", "set", values["power"]],
                           capture_output=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return True
