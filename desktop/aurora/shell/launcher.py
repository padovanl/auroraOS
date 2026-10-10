"""App launcher: Spotlight-style search bar and Launchpad-style app grid."""

import os
import shutil

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.shell import appfolders, search
from aurora.shell.layer import Keyboard, Layer, LayerWindow


def _icon_image(icon, size):
    img = Gtk.Image(pixel_size=size)
    if isinstance(icon, Gdk.Paintable):
        img.set_from_paintable(icon)
    elif isinstance(icon, Gio.Icon):
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
        # Dropped on another app, the two become a folder — the one gesture
        # everyone already knows from a phone.
        source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        source.connect("prepare", lambda *_a: Gdk.ContentProvider.new_for_value(
            app.get_id() or ""))
        source.connect("drag-begin", self._drag_begin)
        self.add_controller(source)
        target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        target.connect("enter", lambda *_a: self._lit(True) or Gdk.DragAction.MOVE)
        target.connect("leave", lambda *_a: self._lit(False))
        target.connect("drop", self._dropped)
        self.add_controller(target)

    def _drag_begin(self, source, _drag):
        picture = self.get_first_child().get_first_child()
        if picture is not None:
            source.set_icon(Gtk.WidgetPaintable.new(picture), 32, 32)

    def _lit(self, on):
        (self.add_css_class if on else self.remove_css_class)("tile-drop-target")

    def _dropped(self, _target, app_id, _x, _y):
        self._lit(False)
        if not app_id or app_id == (self.app.get_id() or ""):
            return False
        self.shell.launcher.make_folder(self.app.get_id() or "", app_id)
        return True

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


class FolderTile(Gtk.FlowBoxChild):
    """A folder in Launchpad: the first four icons inside it, and its name.
    Clicking opens it where it stands; dropping an app on it puts that app in."""

    def __init__(self, folder, members, shell):
        super().__init__(css_classes=["launcher-tile", "launcher-folder"])
        self.folder = folder
        self.members = members
        self.shell = shell
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      halign=Gtk.Align.CENTER)
        preview = Gtk.Grid(row_spacing=4, column_spacing=4, halign=Gtk.Align.CENTER,
                           css_classes=["launcher-folder-preview"])
        for i, app in enumerate(members[:4]):
            preview.attach(_icon_image(app.get_icon() or "application-x-executable", 24),
                           i % 2, i // 2, 1, 1)
        box.append(preview)
        box.append(Gtk.Label(label=folder["name"], wrap=True, lines=2,
                             justify=Gtk.Justification.CENTER, ellipsize=3,
                             max_width_chars=12, width_chars=12))
        self.set_child(box)
        self.name = folder["name"].lower()
        self.set_tooltip_text(", ".join(app.get_display_name() for app in members))
        target = Gtk.DropTarget.new(str, Gdk.DragAction.MOVE)
        target.connect("enter", lambda *_a: self._lit(True) or Gdk.DragAction.MOVE)
        target.connect("leave", lambda *_a: self._lit(False))
        target.connect("drop", self._dropped)
        self.add_controller(target)

    def _lit(self, on):
        (self.add_css_class if on else self.remove_css_class)("tile-drop-target")

    def _dropped(self, _target, app_id, _x, _y):
        self._lit(False)
        if not app_id or not self.members:
            return False
        self.shell.launcher.make_folder(self.members[0].get_id() or "", app_id)
        return True

    def open_folder(self):
        """The apps inside, where the folder is, with its name editable."""
        pop = Gtk.Popover(has_arrow=True, css_classes=["launcher-folder-open"])
        pop.set_parent(self)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
        name = Gtk.Entry(text=self.folder["name"], css_classes=["launcher-folder-name"],
                         halign=Gtk.Align.CENTER, xalign=0.5, width_chars=16,
                         tooltip_text=_("Rename this folder"))
        name.connect("activate", lambda entry: (
            self.shell.launcher.rename_folder(self.folder["name"], entry.get_text()),
            pop.popdown()))
        box.append(name)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=4, min_children_per_line=2,
                           row_spacing=8, column_spacing=12,
                           activate_on_single_click=True)
        for app in self.members:
            tile = AppTile(app, self.shell)
            flow.append(tile)
        flow.connect("child-activated", lambda _f, child: (pop.popdown(),
                                                           self.shell.launcher._on_tile(_f, child)))
        box.append(flow)
        out = Gtk.Button(label=_("Take Everything Out"), css_classes=["flat"])
        out.connect("clicked", lambda *_a: (pop.popdown(),
                                            self.shell.launcher.dissolve_folder(self.folder)))
        box.append(out)
        pop.set_child(box)
        pop.popup()
        name.grab_focus()


def highlight(text, query):
    """The letters you typed, in bold, inside the rest of the title.

    Every piece is escaped on its own, so a result called "Tom & Jerry" or
    "<draft>" comes out whole instead of blank."""
    needle = (query or "").strip().lower()
    if not needle:
        return GLib.markup_escape_text(text)
    low, parts, at = text.lower(), [], 0
    while (found := low.find(needle, at)) >= 0:
        parts.append(GLib.markup_escape_text(text[at:found]))
        parts.append("<b>" + GLib.markup_escape_text(text[found:found + len(needle)]) + "</b>")
        at = found + len(needle)
    if not parts:
        return GLib.markup_escape_text(text)
    parts.append(GLib.markup_escape_text(text[at:]))
    return "".join(parts)


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, result, shell=None, query=""):
        super().__init__(css_classes=["launcher-result"])
        self.result = result
        self.app = result.app
        self.shell = shell
        box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6,
                      margin_start=10, margin_end=10)
        box.append(_icon_image(result.icon, 32))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        title = Gtk.Label(xalign=0, ellipsize=3, css_classes=["result-title"])
        title.set_markup(highlight(result.title, query))
        text.append(title)
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
        # exclusive=-1: the whole screen, under the top bar and under the strip
        # the dock reserves. Without it the backdrop stopped at them and a band
        # of wallpaper was left under the app grid.
        super().__init__(shell, "aurora-launcher", layer=Layer.OVERLAY,
                         anchors=("top", "bottom", "left", "right"),
                         keyboard=Keyboard.EXCLUSIVE, exclusive=-1)
        self.add_css_class("aurora-launcher")
        self.shell = shell

        self.mode = "grid"
        self._semantic_source = 0
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                       halign=Gtk.Align.CENTER, margin_top=64, margin_bottom=48,
                       css_classes=["launcher-root"])
        root.set_size_request(760, -1)
        self.root = root

        self.entry = Gtk.SearchEntry(placeholder_text=_("Search apps, files and settings, or type ? to ask Aurora"),
                                     css_classes=["launcher-search"], hexpand=True)
        self.entry.connect("search-changed", self._on_search)
        self.entry.connect("activate", self._on_activate)
        self.entry.connect("stop-search", lambda *_: self.hide_launcher())
        root.append(self.entry)

        # Not homogeneous: Spotlight must shrink to its results, not the app grid.
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                               vexpand=True, vhomogeneous=False, interpolate_size=True)

        # Launchpad: either the apps used most then a section per kind of app,
        # or pages of tiles with folders in them (Settings → Super Key).
        self.sections = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                                valign=Gtk.Align.START, css_classes=["launcher-sections"])
        self.grid_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.stack.add_named(self.grid_area, "grid")

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

    def _flow(self, members):
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=7, min_children_per_line=3,
                           row_spacing=8, column_spacing=12, valign=Gtk.Align.START,
                           activate_on_single_click=True)
        flow.connect("child-activated", self._on_tile)
        for app in members:
            flow.append(AppTile(app, self.shell))
        return flow

    def layout(self):
        s = settings.get()
        value = s.get_string("launchpad-layout") if s is not None else "pages"
        return value if value in ("pages", "sections") else "pages"

    def folders(self):
        s = settings.get()
        return appfolders.load(s.get_string("launchpad-folders") if s is not None else "")

    def _save_folders(self, folders):
        s = settings.get()
        if s is not None:
            s.set_string("launchpad-folders", appfolders.dump(folders))
        self._populate()

    # --- making and unmaking folders ---

    def make_folder(self, onto_id, moved_id):
        from aurora.shell import appgroups
        folders = self.folders()
        app = apps.app_by_id(onto_id)
        name = _(appgroups.section_of(app.get_categories() if app else "")) \
            if app is not None else _("Folder")
        existing = {f["name"] for f in folders}
        wanted, n = name, 2
        while wanted in existing and appfolders.folder_of(folders, onto_id) is None:
            wanted, n = f"{name} {n}", n + 1
        self._save_folders(appfolders.put_together(folders, onto_id, moved_id, wanted))

    def rename_folder(self, old, new):
        self._save_folders(appfolders.rename(self.folders(), old, new))

    def dissolve_folder(self, folder):
        folders = self.folders()
        for app_id in list(folder["apps"]):
            folders = appfolders.take_out(folders, app_id)
        self._save_folders(folders)

    def _populate(self):
        while (child := self.grid_area.get_first_child()) is not None:
            self.grid_area.remove(child)
        self.grid = None
        if self.layout() == "pages":
            self._populate_pages()
        else:
            self._populate_sections()

    def _populate_sections(self):
        from aurora.shell import appgroups
        while (child := self.sections.get_first_child()) is not None:
            self.sections.remove(child)
        everything = apps.all_apps()
        groups = [(_("Frequently Used"), appgroups.frequent(everything))]
        groups += [(_(title), members) for title, members in appgroups.group(everything).items()]
        for title, members in groups:
            if not members:
                continue
            self.sections.append(Gtk.Label(label=title, xalign=0,
                                           css_classes=["launcher-section-title"]))
            flow = self._flow(members)
            self.grid = self.grid or flow       # the first, for keyboard focus
            self.sections.append(flow)
        self.grid_area.append(Gtk.ScrolledWindow(child=self.sections, vexpand=True,
                                                 hscrollbar_policy=Gtk.PolicyType.NEVER))

    def _populate_pages(self):
        """Every app on pages you move through sideways, folders among them."""
        from aurora.shell import appgroups
        everything = apps.all_apps()
        ordered = []
        for _title, members in appgroups.group(everything).items():
            ordered.extend(members)
        items = appfolders.arrange(ordered, self.folders())
        self.carousel = Adw.Carousel(vexpand=True, allow_long_swipes=True)
        for page in appfolders.paginate(items, self._per_page()):
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                               max_children_per_line=self._columns, min_children_per_line=3,
                               row_spacing=8, column_spacing=12, valign=Gtk.Align.START,
                               halign=Gtk.Align.CENTER, activate_on_single_click=True)
            flow.connect("child-activated", self._on_tile)
            for item in page:
                if item[0] == "app":
                    flow.append(AppTile(item[1], self.shell))
                else:
                    flow.append(FolderTile(item[1], item[2], self.shell))
            self.grid = self.grid or flow
            self.carousel.append(flow)
        self.grid_area.append(self.carousel)
        if self.carousel.get_n_pages() > 1:
            dots = Adw.CarouselIndicatorDots(carousel=self.carousel,
                                             halign=Gtk.Align.CENTER)
            self.grid_area.append(dots)

    GRID_WIDTH = 900        # what show_launcher() gives the grid to live in

    def _per_page(self):
        """How many tiles fit: the width Launchpad itself has, not the screen's,
        or the last column is drawn half outside it."""
        monitor = self.shell.get_primary_monitor()
        area = monitor.get_geometry() if monitor is not None else None
        width = min(self.GRID_WIDTH, area.width - 80) if area is not None else self.GRID_WIDTH
        height = (area.height - 320) if area is not None else 520
        count, self._columns = appfolders.fits(width - 40, height, 120, 128)
        return count

    def _on_search(self, entry):
        text = entry.get_text()
        if not text.strip():
            self.stack.set_visible_child_name("grid" if self.mode == "grid" else "empty")
            return
        self.results.remove_all()
        for r in search.search(text, self.shell.open_settings,
                               refresh=lambda: self._on_search(self.entry)):
            self.results.append(ResultRow(r, self.shell, text))
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
            row = ResultRow(r, self.shell, query)
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
        if isinstance(tile, FolderTile):
            tile.open_folder()
            return
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
        if keyval == Gdk.KEY_Down and self.entry.has_focus() and self.grid is not None:
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
        self.shell.close_overlays(self)
        self.mode = mode
        spotlight = mode == "spotlight"
        for cls, on in (("mode-spotlight", spotlight), ("mode-grid", not spotlight)):
            (self.add_css_class if on else self.remove_css_class)(cls)
        # The launcher fills the screen once shown: its own height is right
        # even when GDK's monitor size is stale after a scale change.
        monitor_h = self.get_height()
        surface_monitor = self.get_display().get_monitors().get_item(0)
        if monitor_h <= 0:
            monitor_h = surface_monitor.get_geometry().height if surface_monitor else 900
        self.root.set_margin_top(int(monitor_h * 0.2) if spotlight else 64)
        self.root.set_valign(Gtk.Align.START if spotlight else Gtk.Align.FILL)
        self.root.set_size_request(680 if spotlight else self.GRID_WIDTH, -1)
        self.stack.set_vexpand(not spotlight)
        self.entry.set_text("")
        if not spotlight:
            self._populate()        # "Frequently Used" follows what you use
        self.stack.set_visible_child_name("empty" if spotlight else "grid")
        self.present()
        self.entry.grab_focus()
        # After the launcher is on screen: whatever maps later lands on top.
        GLib.timeout_add(120, lambda: (self._chrome_on_top(self.get_visible()), False)[1])

    def hide_launcher(self):
        self.set_visible(False)
        self._chrome_on_top(False)

    def _chrome_on_top(self, on):
        """Launchpad covers the screen in the overlay layer; the dock and the
        top bar join it there (above it: they move last), and go back to the
        top layer after.

        The dock so its magnified icons aren't drawn under the launcher's
        backdrop; the top bar because it stays usable while Launchpad is open
        (its exclusive zone keeps the backdrop below it), and a menu opened
        from it is a surface of the bar's layer: left in the top layer it
        opened underneath the launcher, where it could be used but not seen."""
        for group in ("docks", "panels"):
            windows = getattr(self.shell, group, None)
            if windows is None:
                continue
            for window in windows.windows():
                window.set_layer(Layer.OVERLAY if on else Layer.TOP)
                if on:
                    window.queue_draw()
                if hasattr(window, "hold_open"):
                    window.hold_open(on)
