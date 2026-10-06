"""Overview (like Mission Control / Exposé): every open window at a glance.

Super+W, a hot corner or the dock opens it. It shows a card per window over a
blurred picture of the screen; type to filter, arrows and Enter to pick,
middle-click or the × to close a window. "Show Desktop" minimizes everything.

labwc doesn't expose window contents to other clients yet, so cards show the
app icon and title rather than live thumbnails.
"""

import os
import subprocess

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from aurora import apps
from aurora.i18n import _
from aurora.shell.layer import Keyboard, Layer, LayerWindow


def blurred_screenshot(path, width=1920):
    """A cheap blur: shrink the screenshot a lot, then let GTK scale it up."""
    try:
        pix = GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.Error:
        return None
    small = pix.scale_simple(max(1, width // 24), max(1, pix.get_height() * width // 24 //
                                                        max(1, pix.get_width())),
                             GdkPixbuf.InterpType.BILINEAR)
    return Gdk.Texture.new_for_pixbuf(small)


class WindowCard(Gtk.FlowBoxChild):
    def __init__(self, overview, toplevel):
        super().__init__(css_classes=["overview-card"])
        self.toplevel = toplevel
        app = apps.find_app(toplevel.app_id)
        self.app_name = app.get_display_name() if app else (toplevel.app_id or "")
        self.search_text = f"{self.app_name} {toplevel.title}".lower()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_top=18, margin_bottom=14, margin_start=14, margin_end=14)
        top = Gtk.Box()
        top.append(Gtk.Box(hexpand=True))
        close = Gtk.Button(icon_name="window-close-symbolic", tooltip_text=_("Close Window"),
                           css_classes=["circular", "overview-close"], valign=Gtk.Align.START)
        close.connect("clicked", lambda *_: overview.close_window(self))
        top.append(close)
        over = Gtk.Overlay()
        icon = Gtk.Image(pixel_size=96)
        if app and app.get_icon():
            icon.set_from_gicon(app.get_icon())
        else:
            icon.set_from_icon_name("application-x-executable")
        over.set_child(icon)
        over.add_overlay(top)
        box.append(over)
        box.append(Gtk.Label(label=toplevel.title or self.app_name, ellipsize=Pango.EllipsizeMode.END,
                             max_width_chars=26, css_classes=["overview-title"]))
        sub = self.app_name
        if toplevel.minimized:
            sub += " · " + _("Minimized")
            self.add_css_class("minimized")
        if toplevel.activated:
            self.add_css_class("current")
        box.append(Gtk.Label(label=sub, css_classes=["dim-label", "caption"],
                             ellipsize=Pango.EllipsizeMode.END, max_width_chars=30))
        self.set_child(box)
        middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle.connect("released", lambda *_: overview.close_window(self))
        self.add_controller(middle)


class Overview(LayerWindow):
    def __init__(self, shell):
        super().__init__(shell, "aurora-overview", layer=Layer.OVERLAY,
                         anchors=("top", "bottom", "left", "right"),
                         keyboard=Keyboard.EXCLUSIVE, exclusive=-1)
        self.add_css_class("aurora-overview")
        self.shell = shell

        self.background = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        dim = Gtk.Box(css_classes=["overview-dim"])
        overlay = Gtk.Overlay(child=self.background)
        overlay.add_overlay(dim)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24,
                       margin_top=56, margin_bottom=56, margin_start=64, margin_end=64)
        head = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        self.entry = Gtk.SearchEntry(placeholder_text=_("Type to filter windows"),
                                     width_chars=34, css_classes=["overview-search"])
        self.entry.connect("search-changed", lambda *_: self.flow.invalidate_filter())
        self.entry.connect("activate", lambda *_: self._activate_first())
        self.entry.connect("stop-search", lambda *_: self.hide_overview())
        head.append(self.entry)
        desk = Gtk.Button(label=_("Show Desktop"), css_classes=["pill", "overview-desktop"])
        desk.connect("clicked", lambda *_: self.show_desktop())
        head.append(desk)
        root.append(head)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, homogeneous=True,
                                max_children_per_line=5, min_children_per_line=2,
                                row_spacing=24, column_spacing=24, valign=Gtk.Align.CENTER,
                                halign=Gtk.Align.CENTER, activate_on_single_click=True)
        self.flow.set_filter_func(self._filter)
        self.flow.connect("child-activated", lambda _f, card: self._pick(card))
        self.empty = Gtk.Label(label=_("No open windows"), css_classes=["title-2", "dim-label"],
                               vexpand=True)
        scroller = Gtk.ScrolledWindow(child=self.flow, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        root.append(scroller)
        root.append(self.empty)
        overlay.add_overlay(root)
        self.set_child(overlay)

        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        dim.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.entry.set_key_capture_widget(self)

    # --- content ---

    def _populate(self):
        self.flow.remove_all()
        windows = sorted(self.shell.toplevels.toplevels,
                         key=lambda t: getattr(t, "serial", 0), reverse=True)
        for t in windows:
            self.flow.append(WindowCard(self, t))
        self.empty.set_visible(not windows)
        first = self.flow.get_child_at_index(0)
        if first is not None:
            self.flow.select_child(first)

    def _filter(self, card):
        q = self.entry.get_text().strip().lower()
        return not q or q in card.search_text

    # --- actions ---

    def _pick(self, card):
        self.hide_overview()
        card.toplevel.activate()
        self.shell.toplevels.flush()

    def _activate_first(self):
        selected = self.flow.get_selected_children()
        visible = [c for c in self._cards() if c.get_child_visible()]
        card = selected[0] if selected and selected[0] in visible else (visible[0] if visible else None)
        if card is not None:
            self._pick(card)

    def _cards(self):
        out, i = [], 0
        while (c := self.flow.get_child_at_index(i)) is not None:
            out.append(c)
            i += 1
        return out

    def close_window(self, card):
        card.toplevel.close()
        self.shell.toplevels.flush()
        self.flow.remove(card)
        self.empty.set_visible(not self._cards())

    def show_desktop(self):
        self.hide_overview()
        for t in list(self.shell.toplevels.toplevels):
            if not t.minimized:
                t.minimize()
        self.shell.toplevels.flush()

    def _on_click(self, *_a):
        self.hide_overview()

    def _on_key(self, _ctrl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.hide_overview()
            return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down) \
                and self.entry.has_focus():
            first = self.flow.get_selected_children() or [self.flow.get_child_at_index(0)]
            if first and first[0] is not None:
                first[0].grab_focus()
            return False
        return False

    # --- visibility ---

    def toggle(self):
        if self.get_visible():
            self.hide_overview()
        else:
            self.show_overview()

    def show_overview(self):
        self.shell.close_overlays(self)
        shot = os.path.join(GLib.get_user_runtime_dir(), "aurora-overview.png")
        texture = None
        try:
            if subprocess.run(["grim", "-s", "0.5", shot], timeout=3).returncode == 0:
                texture = blurred_screenshot(shot)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.background.set_paintable(texture)
        self.entry.set_text("")
        self._populate()
        self.present()
        self.entry.grab_focus()

    def hide_overview(self):
        self.set_visible(False)
