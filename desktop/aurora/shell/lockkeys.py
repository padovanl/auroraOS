"""Caps Lock and Num Lock on screen, like many laptops' Windows tools: pressing
either key shows its new state for a moment. The keyboard LEDs in
/sys/class/leds tell the state whichever app has the keyboard."""

import glob

from gi.repository import GLib

from aurora import settings
from aurora.i18n import _

POLL_MS = 250


def led_states(pattern="/sys/class/leds/input*::{}/brightness"):
    """{"capslock": bool, "numlock": bool}: on if any keyboard's LED is on."""
    out = {}
    for name in ("capslock", "numlock"):
        on = False
        for path in glob.glob(pattern.format(name)):
            try:
                with open(path) as f:
                    on = on or f.read().strip() not in ("", "0")
            except OSError:
                continue
        out[name] = on
    return out


def message(key, on):
    if key == "capslock":
        return ("input-keyboard-symbolic", _("Caps Lock On") if on else _("Caps Lock Off"))
    return ("input-dialpad-symbolic", _("Num Lock On") if on else _("Num Lock Off"))


class LockKeys:
    def __init__(self, shell):
        self.shell = shell
        self.state = led_states()
        GLib.timeout_add(POLL_MS, self._poll)

    def _poll(self):
        s = settings.get()
        now = led_states()
        if s is None or s.get_boolean("lock-keys-osd"):
            for key, on in now.items():
                if on != self.state.get(key):
                    icon, text = message(key, on)
                    self.shell.osd.show_message(icon, text, 1200)
        self.state = now
        return GLib.SOURCE_CONTINUE
