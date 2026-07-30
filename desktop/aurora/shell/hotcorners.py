"""Hot corners: push the pointer into a screen corner to trigger an action.

Each corner is a tiny transparent layer surface on top of everything. The
action for each corner is chosen in Settings → Multitasking.
"""

from gi.repository import GLib, Gtk

from aurora import settings
from aurora.shell.layer import Layer, LayerWindow

CORNERS = {
    "top-left": ("top", "left"),
    "top-right": ("top", "right"),
    "bottom-left": ("bottom", "left"),
    "bottom-right": ("bottom", "right"),
}
SIZE = 2           # pixels: small enough not to steal clicks
DELAY_MS = 120     # the pointer must rest this long, so fast passes don't trigger
COOLDOWN_MS = 800


class Corner(LayerWindow):
    def __init__(self, shell, monitor, corner, action):
        super().__init__(shell, "aurora-hotcorner", layer=Layer.OVERLAY,
                         anchors=CORNERS[corner], monitor=monitor, exclusive=-1)
        self.add_css_class("aurora-hotcorner")
        self.shell = shell
        self.action = action
        self._timer = 0
        self._cool = False
        area = Gtk.Box()
        area.set_size_request(SIZE, SIZE)
        self.set_default_size(SIZE, SIZE)
        self.set_child(area)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._on_enter)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

    def _on_enter(self, *_a):
        if not self._cool and not self._timer:
            self._timer = GLib.timeout_add(DELAY_MS, self._fire)

    def _on_leave(self, *_a):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _fire(self):
        self._timer = 0
        self._cool = True
        GLib.timeout_add(COOLDOWN_MS, lambda: setattr(self, "_cool", False) or False)
        self.shell.run_corner_action(self.action)
        return GLib.SOURCE_REMOVE


class HotCorners:
    """The corner surfaces of one monitor (only the corners with an action)."""

    def __init__(self, shell, monitor):
        self.windows = []
        s = settings.get()
        for corner in CORNERS:
            action = s.get_string(f"hot-corner-{corner}") if s else "none"
            if action != "none":
                self.windows.append(Corner(shell, monitor, corner, action))

    def present(self):
        for w in self.windows:
            w.present()

    def destroy(self):
        for w in self.windows:
            w.destroy()
