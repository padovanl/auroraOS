"""App launcher: Spotlight-style search bar and Launchpad-style app grid."""

import os
import shutil

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
    def __init__(self, app, shell):
        super().__init__(css_classes=["launcher-tile"])
        self.app = app
        self.shell = shell
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
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", self._show_menu)
        self.add_controller(right)

    def _show_menu(self, _gesture, _n, x, y):
        pop = Gtk.Popover(has_arrow=True, css_classes=["aurora-context-menu"])
        pop.set_parent(self)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.set_margin_top(5)
        box.set_margin_bottom(5)
        box.set_margin_start(5)
        box.set_margin_end(5)

        def row(label, callback):
            button = Gtk.Button(label=label, css_classes=["flat", "context-action"])
            button.get_child().set_xalign(0)
            button.connect("clicked", lambda *_: (pop.popdown(), callback()))
            box.append(button)

        row(_("Open"), lambda: self.shell.launcher._run(
            lambda: self.shell.launch_app(self.app)))
        actions = list(self.app.list_actions())
        new_window = next((a for a in actions if a.replace("_", "-").lower()
                           in ("new-window", "new-window-action", "window")), None)
        row(_("New Window"), lambda: self.shell.launcher._run(
            lambda: self.shell.launch_app(self.app, action=new_window)))
        box.append(Gtk.Separator())
        key = self.app.get_id()
        s = settings.get()
        favs = list(s.get_strv("dock-favorites")) if s else []
        if key in favs:
            row(_("Remove from Dock"), lambda: s.set_strv(
                "dock-favorites", [f for f in favs if f != key]))
        else:
            row(_("Keep in Dock"), lambda: s.set_strv("dock-favorites", favs + [key])
                if s else None)
        row(_("Add to Desktop"), self._add_to_desktop)
        row(_("Show in Files"), lambda: apps.spawn(
            ["aurora-files", os.path.dirname(self.app.get_filename())]))
        pop.set_child(box)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.popup()

    def _add_to_desktop(self):
        from aurora.files.operations import unique_destination
        from aurora.shell.desktopicons import desktop_dir
        source = self.app.get_filename()
        if not source or not os.path.isfile(source):
            return
        try:
            os.makedirs(desktop_dir(), exist_ok=True)
            shutil.copy2(source, unique_destination(desktop_dir(), os.path.basename(source)))
        except OSError as err:
            print(f"aurora: cannot add app to desktop: {err}")


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, result, shell=None):
        super().__init__(css_classes=["launcher-result"])
        self.result = result
        self.app = result.app
        self.shell = shell
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
        if (self.app is not None and shell is not None) or result.path:
            right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
            right.connect("pressed", self._show_menu)
            self.add_controller(right)

    def _show_menu(self, gesture, n, x, y):
        if self.app is not None:
            return AppTile._show_menu(self, gesture, n, x, y)
        pop = Gtk.Popover(has_arrow=True, css_classes=["aurora-context-menu"])
        pop.set_parent(self)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                      margin_top=5, margin_bottom=5, margin_start=5, margin_end=5)

        def row(label, callback):
            button = Gtk.Button(label=label, css_classes=["flat", "context-action"])
            button.get_child().set_xalign(0)
            button.connect("clicked", lambda *_: (pop.popdown(), callback()))
            box.append(button)

        path = self.result.path
        row(_("Open"), self.result.activate)
        row(_("Show in Files"), lambda: apps.spawn(["aurora-files", os.path.dirname(path)]))
        row(_("Copy Path"), lambda: Gdk.Display.get_default().get_clipboard().set(path))
        if os.path.isdir(path):
            from aurora import projectworkspaces
            row(_("Open Workspace"), lambda: projectworkspaces.open_workspace(path))
            row(_("Open in Terminal"), lambda: apps.spawn(
                ["ptyxis", "--new-window", "--working-directory", path]))
        else:
            row(_("Ask Aurora about this file"), lambda: apps.spawn(
                ["aurora-assistant", "--file", path]))
        pop.set_child(box)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.popup()

    def _add_to_desktop(self):
        return AppTile._add_to_desktop(self)


class Launcher(LayerWindow):
    """Two faces: "spotlight" (a search bar) and "grid" (Launchpad, all apps)."""

    def __init__(self, shell):
        super().__init__(shell, "aurora-launcher", layer=Layer.OVERLAY,
                         anchors=("top", "bottom", "left", "right"),
                         keyboard=Keyboard.EXCLUSIVE)
        self.add_css_class("aurora-launcher")
        self.shell = shell

        self.mode = "grid"
        self._semantic_source = 0
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                       halign=Gtk.Align.CENTER, margin_top=64, margin_bottom=48,
                       css_classes=["launcher-root"])
        root.set_size_request(760, -1)
        self.root = root

        self.entry = Gtk.SearchEntry(placeholder_text=_("Search apps, files, projects, math, 10 km in mi, :emoji, clip:, ? ask Aurora"),
                                     css_classes=["launcher-search"], hexpand=True)
        self.entry.connect("search-changed", self._on_search)
        self.entry.connect("activate", self._on_activate)
        self.entry.connect("stop-search", lambda *_: self.hide_launcher())
        root.append(self.entry)

        # Not homogeneous: Spotlight must shrink to its results, not the app grid.
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                               vexpand=True, vhomogeneous=False, interpolate_size=True)

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
            self.grid.append(AppTile(app, self.shell))

    def _on_search(self, entry):
        text = entry.get_text()
        if not text.strip():
            self.stack.set_visible_child_name("grid" if self.mode == "grid" else "empty")
            return
        self.results.remove_all()
        for r in search.search(text, self.shell.open_settings,
                               refresh=lambda: self._on_search(self.entry)):
            self.results.append(ResultRow(r, self.shell))
        self.results.select_row(self.results.get_row_at_index(0))
        self.stack.set_visible_child_name("results")
        # Documents by meaning arrive later (a local model computes them).
        if self._semantic_source:
            GLib.source_remove(self._semantic_source)
        self._semantic_source = GLib.timeout_add(400, self._start_semantic, text)

    def _start_semantic(self, text):
        self._semantic_source = 0
        search.search_semantic(text, self._add_semantic)
        return GLib.SOURCE_REMOVE

    def _add_semantic(self, query, results):
        if self.entry.get_text() != query:
            return
        for r in results:
            row = ResultRow(r, self.shell)
            # Insert before the web-search fallback at the end.
            self.results.insert(row, max(0, self._count_rows() - 1))

    def _count_rows(self):
        n = 0
        while self.results.get_row_at_index(n) is not None:
            n += 1
        return n

    # --- activation ---

    def _run(self, fn):
        self.hide_launcher()
        GLib.idle_add(lambda: (fn(), False)[1])

    def _on_tile(self, _grid, tile):
        self._run(lambda: self.shell.launch_app(tile.app))

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

    def search_for(self, text):
        """Open Spotlight with a query already typed."""
        self.show_launcher("spotlight")
        self.entry.set_text(text)
        self.entry.set_position(-1)

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
        self.root.set_valign(Gtk.Align.START if spotlight else Gtk.Align.FILL)
        self.root.set_size_request(680 if spotlight else 900, -1)
        self.stack.set_vexpand(not spotlight)
        self.entry.set_text("")
        self.stack.set_visible_child_name("empty" if spotlight else "grid")
        self.present()
        self.entry.grab_focus()

    def hide_launcher(self):
        self.set_visible(False)
