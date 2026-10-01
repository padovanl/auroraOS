"""The volume mixer's rows: one per app playing sound, with its own slider and
mute button (Settings → Sound and the Control Center use the same rows)."""

from gi.repository import Gtk, Pango

from aurora.i18n import _


def _icon(name):
    from aurora import apps
    app = apps.find_app(name) if name else None
    if app is not None and app.get_icon() is not None:
        return Gtk.Image(gicon=app.get_icon(), pixel_size=24)
    return Gtk.Image(icon_name=name or "audio-x-generic", pixel_size=24)


class MixerRow(Gtk.Box):
    def __init__(self, stream, maximum=1.0):
        super().__init__(spacing=10, css_classes=["mixer-row"])
        from aurora.shell.services import get_volume, set_stream_volume, toggle_stream_mute
        self.stream = stream
        self.append(_icon(stream["icon"]))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=False)
        text.set_size_request(120, -1)
        text.append(Gtk.Label(label=stream["app"], xalign=0, ellipsize=Pango.EllipsizeMode.END,
                              css_classes=["heading"], max_width_chars=16))
        if stream["title"]:
            text.append(Gtk.Label(label=stream["title"], xalign=0, max_width_chars=18,
                                  ellipsize=Pango.EllipsizeMode.END,
                                  css_classes=["dim-label", "caption"]))
        self.append(text)
        volume, muted = get_volume(str(stream["id"]))
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, maximum, 0.01)
        self.scale.set_draw_value(False)
        self.scale.set_hexpand(True)
        self.scale.set_value(volume)
        self.scale.connect("value-changed",
                           lambda s: set_stream_volume(stream["id"], s.get_value()))
        self.append(self.scale)
        self.mute = Gtk.ToggleButton(icon_name="audio-volume-muted-symbolic" if muted
                                     else "audio-volume-high-symbolic",
                                     active=muted, valign=Gtk.Align.CENTER,
                                     css_classes=["flat", "circular"], tooltip_text=_("Mute"))

        def toggled(button):
            toggle_stream_mute(stream["id"])
            button.set_icon_name("audio-volume-muted-symbolic" if button.get_active()
                                 else "audio-volume-high-symbolic")
        self.mute.connect("toggled", toggled)
        self.append(self.mute)


def fill(box, streams, empty_text=None, maximum=1.0):
    """Rebuild a box of mixer rows, keeping rows of streams still playing (so a
    slider being dragged isn't replaced)."""
    have = {}
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        if isinstance(child, MixerRow):
            have[child.stream["id"]] = child
        else:
            box.remove(child)
        child = nxt
    ids = {s["id"] for s in streams}
    for sid, row in list(have.items()):
        if sid not in ids:
            box.remove(row)
    for stream in streams:
        if stream["id"] not in have:
            box.append(MixerRow(stream, maximum))
    if not streams and empty_text:
        box.append(Gtk.Label(label=empty_text, css_classes=["dim-label"], margin_top=6,
                             margin_bottom=6))
