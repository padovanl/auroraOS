"""The on-screen keyboard: a keyboard at the bottom of the screen, for touch
screens and for people who can't use a physical one.

It never takes the keyboard focus, so what you tap goes to the app you were
typing in, sent with wtype (Wayland's virtual keyboard). Shift for capitals
(tap twice for Caps), a layer for numbers and symbols, Ctrl and arrows for
editing, and × to hide it. Shown from the Control Center tile, and at login
when Settings → Accessibility → Screen keyboard is on."""

import shutil
import subprocess

from gi.repository import GLib, Gtk

from aurora import settings
from aurora.i18n import _
from aurora.shell.layer import Keyboard, Layer, LayerWindow

# Rows of keys. A plain string is typed as text; (label, key, width) sends a
# named key ("BackSpace") or switches a state ("shift", "symbols", "ctrl", "hide").
LETTERS = [
    list("qwertyuiop") + [("⌫", "BackSpace", 1.5)],
    [("Tab", "Tab", 1.3)] + list("asdfghjkl") + [("⏎", "Return", 1.7)],
    [("⇧", "shift", 1.8)] + list("zxcvbnm,.") + [("⇧", "shift", 1.2)],
    [("Ctrl", "ctrl", 1.3), ("?123", "symbols", 1.4), (" ", "space", 5.6), ("←", "Left", 1),
     ("→", "Right", 1), ("↑", "Up", 1), ("↓", "Down", 1), ("✕", "hide", 1.2)],
]
SYMBOLS = [
    list("1234567890") + [("⌫", "BackSpace", 1.5)],
    [("Esc", "Escape", 1.3)] + list("@#€$%&-+(") + [("⏎", "Return", 1.7)],
    [("=\\<", "more", 1.8)] + list("*\"':;!?/") + [("_", "_", 1.2)],
    [("Ctrl", "ctrl", 1.3), ("ABC", "symbols", 1.4), (" ", "space", 5.6), ("←", "Left", 1),
     ("→", "Right", 1), ("↑", "Up", 1), ("↓", "Down", 1), ("✕", "hide", 1.2)],
]
MORE = [
    list("~`|\\^{}[]<") + [("⌫", "BackSpace", 1.5)],
    [("Esc", "Escape", 1.3)] + list(">£¥°§¿¡«»") + [("⏎", "Return", 1.7)],
    [("123", "more", 1.8)] + list("©®™±×÷µ¶·") + [("…", "…", 1.2)],
    [("Ctrl", "ctrl", 1.3), ("ABC", "symbols", 1.4), (" ", "space", 5.6), ("←", "Left", 1),
     ("→", "Right", 1), ("↑", "Up", 1), ("↓", "Down", 1), ("✕", "hide", 1.2)],
]
STATES = ("shift", "symbols", "more", "ctrl", "hide")

from aurora.shell.osk_themes import THEMES  # noqa: E402


def wtype_args(key, text=None, ctrl=False):
    """The wtype command for a key press: text, a named key, or Ctrl+key."""
    cmd = ["wtype"]
    if ctrl:
        cmd += ["-M", "ctrl"]
    if text is not None:
        cmd += ["-k", text] if ctrl and len(text) == 1 else ["--", text]
    else:
        cmd += ["-k", key]
    if ctrl:
        cmd += ["-m", "ctrl"]
    return cmd


class ScreenKeyboard(LayerWindow):
    def __init__(self, shell):
        super().__init__(shell, "aurora-osk", layer=Layer.OVERLAY,
                         anchors=("bottom", "left", "right"), exclusive=True,
                         keyboard=Keyboard.NONE)
        self.add_css_class("aurora-osk")
        self.shell = shell
        self.shift = 0          # 0 off, 1 next letter, 2 caps lock
        self.ctrl = False
        self.layer = "letters"
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                           css_classes=["osk-box"], halign=Gtk.Align.CENTER)
        self.set_child(self.box)
        self.available = shutil.which("wtype") is not None
        s = settings.get()
        self._theme = None
        self.apply_theme(s.get_string("screen-keyboard-theme") if s else "classic")
        if s is not None:
            s.connect("changed::screen-keyboard-theme",
                      lambda st, k: self.apply_theme(st.get_string(k)))
        self._build()

    def apply_theme(self, name):
        if name not in dict(THEMES):
            name = "classic"
        if self._theme:
            self.remove_css_class(f"osk-theme-{self._theme}")
        self._theme = name
        self.add_css_class(f"osk-theme-{name}")

    # --- drawing -----------------------------------------------------------------

    def _rows(self):
        return {"letters": LETTERS, "symbols": SYMBOLS, "more": MORE}[self.layer]

    def _build(self):
        while (row := self.box.get_first_child()) is not None:
            self.box.remove(row)
        for keys in self._rows():
            row = Gtk.Box(spacing=6, homogeneous=False, halign=Gtk.Align.CENTER)
            for key in keys:
                label, name, width = (key, None, 1) if isinstance(key, str) else key
                if isinstance(key, str) and self.layer == "letters" and self.shift:
                    label = label.upper()
                button = Gtk.Button(label=label, focusable=False, css_classes=["osk-key"])
                button.set_size_request(int(56 * width), 52)
                if name in STATES or name in ("BackSpace", "Return", "Tab", "Escape"):
                    button.add_css_class("osk-special")
                if (name == "shift" and self.shift) or (name == "ctrl" and self.ctrl):
                    button.add_css_class("osk-on")
                if name == "shift" and self.shift == 2:
                    button.add_css_class("osk-locked")
                button.connect("clicked", lambda _b, l=label, n=name: self._press(l, n))
                row.append(button)
            self.box.append(row)

    # --- keys --------------------------------------------------------------------

    def _press(self, label, name):
        if name == "hide":
            self.hide_keyboard()
            return
        if name == "shift":
            self.shift = {0: 1, 1: 2, 2: 0}[self.shift]
            self._build()
            return
        if name == "ctrl":
            self.ctrl = not self.ctrl
            self._build()
            return
        if name == "symbols":
            self.layer = "symbols" if self.layer == "letters" else "letters"
            self._build()
            return
        if name == "more":
            self.layer = "more" if self.layer == "symbols" else "symbols"
            self._build()
            return
        if name == "space":
            self._send(wtype_args(None, " ", self.ctrl))
        elif name is None or len(name) == 1 or name in ("…",):
            self._send(wtype_args(None, label, self.ctrl))
        else:
            self._send(wtype_args(name, None, self.ctrl))
        changed = False
        if self.shift == 1 and name is None:
            self.shift = 0
            changed = True
        if self.ctrl:
            self.ctrl = False
            changed = True
        if changed:
            self._build()

    def _send(self, cmd):
        if not self.available:
            return
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as err:
            print(f"aurora: screen keyboard: {err}")

    # --- showing ---------------------------------------------------------------------

    @property
    def showing(self):
        return self.get_visible()

    def show_keyboard(self):
        self.layer, self.shift, self.ctrl = "letters", 0, False
        self._build()
        self.present()
        self.shell.osk_changed()

    def hide_keyboard(self):
        self.set_visible(False)
        self.shell.osk_changed()

    def toggle(self):
        self.hide_keyboard() if self.showing else self.show_keyboard()


__all__ = ["ScreenKeyboard", "wtype_args", "_"]
