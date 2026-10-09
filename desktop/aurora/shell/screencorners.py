"""Rounded screen corners, the way a 2026 screen is shaped.

Four tiny layer surfaces, one per corner of each monitor, painted black
outside a quarter circle and taking no pointer input at all, so a window, a
desktop icon or a hot corner underneath still answers the pointer. The radius
comes from Settings → Desktop & Dock → Screen (0 turns them off).
"""

import cairo
from gi.repository import Gtk

from aurora import settings
from aurora.shell.layer import Layer, LayerWindow

CORNERS = {
    "top-left": ("top", "left"),
    "top-right": ("top", "right"),
    "bottom-left": ("bottom", "left"),
    "bottom-right": ("bottom", "right"),
}


def radius():
    s = settings.get()
    return s.get_int("screen-corner-radius") if s else 0


class ScreenCorner(LayerWindow):
    def __init__(self, shell, monitor, corner, size):
        super().__init__(shell, "aurora-screen-corner", layer=Layer.OVERLAY,
                         anchors=CORNERS[corner], monitor=monitor, exclusive=-1)
        self.add_css_class("aurora-screen-corner")
        fill = Gtk.Box(css_classes=["screen-corner", f"screen-corner-{corner}"])
        fill.set_size_request(size, size)
        self.set_default_size(size, size)
        self.set_child(fill)
        self.connect("map", lambda *_a: self._ignore_pointer())

    def _ignore_pointer(self):
        """Paint only: the corner must never take a click or a hot corner."""
        surface = self.get_surface()
        if surface is not None:
            surface.set_input_region(cairo.Region())


class ScreenCorners:
    """The four corners of one monitor, or nothing when the radius is 0."""

    def __init__(self, shell, monitor):
        size = radius()
        self.windows = [ScreenCorner(shell, monitor, corner, size)
                        for corner in CORNERS] if size > 0 else []

    def present(self):
        for w in self.windows:
            w.present()

    def destroy(self):
        for w in self.windows:
            w.destroy()
