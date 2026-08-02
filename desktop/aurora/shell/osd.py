"""On-screen display for volume and brightness changes."""

from gi.repository import GLib, Gtk

from aurora.shell.layer import Layer, LayerWindow


class OSD(LayerWindow):
    def __init__(self, shell):
        super().__init__(shell, "aurora-osd", layer=Layer.OVERLAY, anchors=("bottom",),
                         margins={"bottom": 110})
        self.add_css_class("aurora-osd")
        box = Gtk.Box(spacing=14, css_classes=["osd-box"])
        self.icon = Gtk.Image(pixel_size=24)
        self.bar = Gtk.LevelBar(min_value=0, max_value=1, hexpand=True,
                                valign=Gtk.Align.CENTER)
        self.bar.set_size_request(220, -1)
        self.label = Gtk.Label(visible=False, css_classes=["osd-label"])
        box.append(self.icon)
        box.append(self.bar)
        box.append(self.label)
        self.set_child(box)
        self._source = 0

    def show_message(self, icon_name, text, timeout_ms=0):
        """A message instead of a level; stays until hide() when timeout_ms is 0."""
        self.icon.set_from_icon_name(icon_name)
        self.bar.set_visible(False)
        self.label.set_label(text)
        self.label.set_visible(True)
        self.present()
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0
        if timeout_ms:
            self._source = GLib.timeout_add(timeout_ms, self._hide)

    def hide(self):
        self._hide()

    def show_level(self, icon_name, value):
        self.bar.set_visible(True)
        self.label.set_visible(False)
        self.icon.set_from_icon_name(icon_name)
        self.bar.set_value(max(0.0, min(1.0, value)))
        self.present()
        if self._source:
            GLib.source_remove(self._source)
        self._source = GLib.timeout_add(1500, self._hide)

    def _hide(self):
        self._source = 0
        self.set_visible(False)
        return GLib.SOURCE_REMOVE
