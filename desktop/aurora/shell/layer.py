"""Thin wrapper around gtk4-layer-shell."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gtk4LayerShell as LS  # noqa: E402

Layer = LS.Layer
Edge = LS.Edge
Keyboard = LS.KeyboardMode

EDGES = {"top": Edge.TOP, "bottom": Edge.BOTTOM, "left": Edge.LEFT, "right": Edge.RIGHT}


def supported():
    return LS.is_supported()


class LayerWindow(Gtk.Window):
    """A Gtk.Window turned into a layer-shell surface."""

    def __init__(self, app, namespace, layer=Layer.TOP, anchors=(), monitor=None,
                 margins=None, exclusive=False, keyboard=Keyboard.NONE, **kwargs):
        super().__init__(application=app, **kwargs)
        self.add_css_class("aurora-layer")
        LS.init_for_window(self)
        LS.set_namespace(self, namespace)
        LS.set_layer(self, layer)
        for name in anchors:
            LS.set_anchor(self, EDGES[name], True)
        for name, px in (margins or {}).items():
            LS.set_margin(self, EDGES[name], px)
        if monitor is not None:
            LS.set_monitor(self, monitor)
        if exclusive is True:
            LS.auto_exclusive_zone_enable(self)
        elif exclusive is not False:
            LS.set_exclusive_zone(self, exclusive)
        LS.set_keyboard_mode(self, keyboard)

    def set_keyboard(self, mode):
        LS.set_keyboard_mode(self, mode)

    def set_layer(self, layer):
        LS.set_layer(self, layer)

    def set_margin(self, edge, px):
        LS.set_margin(self, EDGES[edge], px)
