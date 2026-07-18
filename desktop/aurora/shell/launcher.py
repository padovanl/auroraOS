"""App launcher: Spotlight-style search bar and Launchpad-style app grid."""

from gi.repository import Gdk, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.shell import search
from aurora.shell.layer import Keyboard, Layer, LayerWindow


def _icon_image(icon, size):
    img = Gtk.Image(pixel_size=size)
    if isinstance(icon, Gio.Icon):
        img.set_from_gicon(icon)
    else:
        img.set_from_icon_name(icon)
    return img


class AppTile(Gtk.FlowBoxChild):
    def __init__(self, app):
        super().__init__(css_classes=["launcher-tile"])
        self.app = app
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      halign=Gtk.Align.CENTER)
        box.append(_icon_image(app.get_icon() or "application-x-executable", 64))
        label = Gtk.Label(label=app.get_display_name(), wrap=True, lines=2,
                          justify=Gtk.Justification.CENTER, ellipsize=3,
                          max_width_chars=12, width_chars=12)
        box.append(label)
        self.set_child(box)
        self.set_tooltip_text(app.get_description())
        self.name = (app.get_display_name() or "").lower()


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, result):
        super().__init__(css_classes=["launcher-result"])
        self.result = result
        box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6,
                      margin_start=10, margin_end=10)
        box.append(_icon_image(result.icon, 32))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        text.append(Gtk.Label(label=result.title, xalign=0, ellipsize=3,
                              css_classes=["result-title"]))
        if result.subtitle:
            text.append(Gtk.Label(label=result.subtitle, xalign=0, ellipsize=3,
                                  css_classes=["dim-label", "caption"]))
        box.append(text)
        self.set_child(box)


class Launcher(LayerWindow):
    """Two faces: "spotlight" (a search bar) and "grid" (Launchpad, all apps)."""

    def __init__(self, shell):
        super().__init__(shell, "aurora-launcher", layer=Layer.OVERLAY,
                         anchors=("top", "bottom", "left", "right"),
                         keyboard=Keyboard.EXCLUSIVE)
        self.add_css_class("aurora-launcher")
        self.shell = shell

        self.mode = "grid"
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                       halign=Gtk.Align.CENTER, margin_top=64, margin_bottom=48,
                       css_classes=["launcher-root"])
        root.set_size_request(760, -1)
        self.root = root

        self.entry = Gtk.SearchEntry(placeholder_text=_("Search apps, settings, files, math, or > command"),
                                     css_classes=["launcher-search"], hexpand=True)
        self.entry.connect("search-changed", self._on_search)
        self.entry.connect("activate", self._on_activate)
        self.entry.connect("stop-search", lambda *_: self.hide_launcher())
        root.append(self.entry)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                               vexpand=True)

        self.grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                max_children_per_line=7, min_children_per_line=3,
                                row_spacing=12, column_spacing=12, valign=Gtk.Align.START,
                                activate_on_single_click=True)
        self.grid.connect("child-activated", self._on_tile)
        self.grid.set_sort_func(lambda a, b: (a.name > b.name) - (a.name < b.name))
        self.stack.add_named(Gtk.ScrolledWindow(child=self.grid,
                                                hscrollbar_policy=Gtk.PolicyType.NEVER),
                             "grid")

        self.results = Gtk.ListBox(css_classes=["launcher-results"],
                                   selection_mode=Gtk.SelectionMode.BROWSE,
                                   valign=Gtk.Align.START)
        self.results.connect("row-activated", self._on_row)
        self.stack.add_named(Gtk.ScrolledWindow(child=self.results,
                                                hscrollbar_policy=Gtk.PolicyType.NEVER,
                                                propagate_natural_height=True,
                                                max_content_height=520),
                             "results")
        self.stack.add_named(Gtk.Box(), "empty")
        root.append(self.stack)

        # Click on the dimmed backdrop (outside root) closes the launcher.
        backdrop = Gtk.Box(css_classes=["launcher-backdrop"])
        overlay = Gtk.Overlay(child=backdrop)
        overlay.add_overlay(root)
        self.set_child(overlay)
        click = Gtk.GestureClick()
        click.connect("released", self._on_backdrop_click)
        backdrop.add_controller(click)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.entry.set_key_capture_widget(self)

        Gio.AppInfoMonitor.get().connect("changed", lambda *a: self._populate())
        self._populate()

    # --- content ---

    def _populate(self):
        self.grid.remove_all()
        for app in apps.all_apps():
            self.grid.append(AppTile(app))

    def _on_search(self, entry):
        text = entry.get_text()
        if not text.strip():
            self.stack.set_visible_child_name("grid" if self.mode == "grid" else "empty")
            return
        self.results.remove_all()
        for r in search.search(text, self.shell.open_settings):
            self.results.append(ResultRow(r))
        self.results.select_row(self.results.get_row_at_index(0))
        self.stack.set_visible_child_name("results")

    # --- activation ---

    def _run(self, fn):
        self.hide_launcher()
        GLib.idle_add(lambda: (fn(), False)[1])

    def _on_tile(self, _grid, tile):
        self._run(lambda: apps.launch(tile.app))

    def _on_row(self, _list, row):
        self._run(row.result.activate)

    def _on_activate(self, *_a):
        if self.stack.get_visible_child_name() == "results":
            row = self.results.get_selected_row() or self.results.get_row_at_index(0)
            if row:
                self._on_row(None, row)

    def _on_key(self, _ctrl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.hide_launcher()
            return True
        if self.stack.get_visible_child_name() == "results" and \
                keyval in (Gdk.KEY_Down, Gdk.KEY_Up):
            row = self.results.get_selected_row()
            idx = row.get_index() if row else -1
            idx += 1 if keyval == Gdk.KEY_Down else -1
            nxt = self.results.get_row_at_index(max(0, idx))
            if nxt:
                self.results.select_row(nxt)
                nxt.grab_focus() if not self.entry.has_focus() else None
            return True
        if keyval == Gdk.KEY_Down and self.entry.has_focus():
            first = self.grid.get_child_at_index(0)
            if first:
                first.grab_focus()
            return True
        return False

    def _on_backdrop_click(self, *_a):
        self.hide_launcher()

    # --- visibility ---

    def toggle(self, mode=None):
        if mode is None:
            s = settings.get()
            mode = s.get_string("launcher-style") if s else "spotlight"
        if self.get_visible() and self.mode == mode:
            self.hide_launcher()
        else:
            self.show_launcher(mode)

    def show_launcher(self, mode="spotlight"):
        self.mode = mode
        spotlight = mode == "spotlight"
        for cls, on in (("mode-spotlight", spotlight), ("mode-grid", not spotlight)):
            (self.add_css_class if on else self.remove_css_class)(cls)
        monitor_h = 900
        surface_monitor = self.get_display().get_monitors().get_item(0)
        if surface_monitor is not None:
            monitor_h = surface_monitor.get_geometry().height
        self.root.set_margin_top(int(monitor_h * 0.2) if spotlight else 64)
        self.root.set_size_request(680 if spotlight else 900, -1)
        self.stack.set_vexpand(not spotlight)
        self.entry.set_text("")
        self.stack.set_visible_child_name("empty" if spotlight else "grid")
        self.present()
        self.entry.grab_focus()

    def hide_launcher(self):
        self.set_visible(False)
