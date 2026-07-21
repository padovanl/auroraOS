"""Aurora Files main window."""

import os

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

from aurora import apps
from aurora.files.operations import Job, unique_destination
from aurora.i18n import _

ATTRS = ",".join([
    "standard::name", "standard::display-name", "standard::icon", "standard::type",
    "standard::size", "standard::is-hidden", "standard::is-backup", "standard::content-type",
    "standard::symbolic-icon", "time::modified", "thumbnail::path", "trash::orig-path",
    "trash::deletion-date", "access::can-write",
])

TRASH_URI = "trash:///"

# Shared by every window of the app: (mode, [Gio.File]).
CLIPBOARD = {"mode": None, "files": []}


def file_of(info):
    return info.get_attribute_object("standard::file")


def is_dir(info):
    return info.get_file_type() == Gio.FileType.DIRECTORY


def human_size(info):
    if is_dir(info):
        return ""
    return GLib.format_size(info.get_size())


def modified(info):
    dt = info.get_modification_date_time()
    if dt is None:
        return ""
    dt = dt.to_local()
    now = GLib.DateTime.new_now_local()
    if dt.get_year() == now.get_year() and dt.get_day_of_year() == now.get_day_of_year():
        return dt.format("%H:%M")
    return dt.format("%x")


def user_dir(kind):
    return GLib.get_user_special_dir(kind)


class Sidebar(Gtk.ListBox):
    __gsignals__ = {"open": (GObject.SignalFlags.RUN_FIRST, None, (Gio.File,))}

    def __init__(self):
        super().__init__(css_classes=["navigation-sidebar"])
        self.connect("row-activated", self._on_row)
        self.volumes = Gio.VolumeMonitor.get()
        for sig in ("mount-added", "mount-removed", "volume-added", "volume-removed"):
            self.volumes.connect(sig, lambda *a: self.rebuild())
        self.rebuild()

    def _add(self, icon, label, file=None, volume=None, eject=None):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(spacing=12, margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        box.append(Gtk.Image(icon_name=icon) if isinstance(icon, str) else Gtk.Image(gicon=icon))
        box.append(Gtk.Label(label=label, xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END))
        if eject is not None:
            b = Gtk.Button(icon_name="media-eject-symbolic", css_classes=["flat", "circular"])
            b.connect("clicked", lambda *_: eject.unmount_with_operation(
                Gio.MountUnmountFlags.NONE, None, None, None, None))
            box.append(b)
        row.set_child(box)
        row.file = file
        row.volume = volume
        self.append(row)

    def rebuild(self):
        self.remove_all()
        home = GLib.get_home_dir()
        self._add("user-home-symbolic", _("Home"), Gio.File.new_for_path(home))
        for kind, icon in (
            (GLib.UserDirectory.DIRECTORY_DESKTOP, "user-desktop-symbolic"),
            (GLib.UserDirectory.DIRECTORY_DOCUMENTS, "folder-documents-symbolic"),
            (GLib.UserDirectory.DIRECTORY_DOWNLOAD, "folder-download-symbolic"),
            (GLib.UserDirectory.DIRECTORY_MUSIC, "folder-music-symbolic"),
            (GLib.UserDirectory.DIRECTORY_PICTURES, "folder-pictures-symbolic"),
            (GLib.UserDirectory.DIRECTORY_VIDEOS, "folder-videos-symbolic"),
        ):
            path = user_dir(kind)
            if path and path != home and os.path.isdir(path):
                self._add(icon, os.path.basename(path), Gio.File.new_for_path(path))
        self._add("user-trash-symbolic", _("Trash"), Gio.File.new_for_uri(TRASH_URI))

        mounted_volumes = set()
        for mount in self.volumes.get_mounts():
            if mount.is_shadowed():
                continue
            vol = mount.get_volume()
            if vol:
                mounted_volumes.add(vol)
            self._add(mount.get_symbolic_icon(), mount.get_name(), mount.get_root(),
                      eject=mount if mount.can_unmount() else None)
        for vol in self.volumes.get_volumes():
            if vol not in mounted_volumes and vol.get_mount() is None:
                self._add(vol.get_symbolic_icon(), vol.get_name(), volume=vol)
        self._add("drive-harddisk-symbolic", _("Computer"), Gio.File.new_for_path("/"))

    def _on_row(self, _box, row):
        if row.file is not None:
            self.emit("open", row.file)
        elif row.volume is not None:
            def mounted(vol, res):
                try:
                    vol.mount_finish(res)
                except GLib.Error as err:
                    print(f"aurora-files: mount failed: {err.message}")
                    return
                if vol.get_mount():
                    self.emit("open", vol.get_mount().get_root())
            row.volume.mount(Gio.MountMountFlags.NONE, Gtk.MountOperation.new(self.get_root()),
                             None, mounted)

    def select_file(self, gfile):
        i = 0
        while (row := self.get_row_at_index(i)) is not None:
            if row.file is not None and row.file.equal(gfile):
                self.select_row(row)
                return
            i += 1
        self.unselect_all()


class FilesWindow(Adw.ApplicationWindow):
    def __init__(self, app, location=None):
        super().__init__(application=app, default_width=1000, default_height=640)
        self.current = None
        self.back_stack, self.forward_stack = [], []
        self.show_hidden = False
        self.search_text = ""
        self.jobs = []

        # Model: directory -> filter -> sort -> selection
        self.dirlist = Gtk.DirectoryList(attributes=ATTRS, monitored=True)
        self.dirlist.connect("notify::loading", self._on_loading)
        self.filter = Gtk.CustomFilter.new(self._filter_func)
        filtered = Gtk.FilterListModel(model=self.dirlist, filter=self.filter)
        self.sorter = Gtk.CustomSorter.new(self._sort_func)
        sorted_ = Gtk.SortListModel(model=filtered, sorter=self.sorter)
        self.selection = Gtk.MultiSelection(model=sorted_)
        self.model = sorted_
        sorted_.connect("items-changed", lambda *a: self._update_empty())

        self._build_ui()
        self._build_actions()
        self.open_location(location or Gio.File.new_for_path(GLib.get_home_dir()))

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        self.sidebar = Sidebar()
        self.sidebar.connect("open", lambda _s, f: self.open_location(f))
        sidebar_view = Adw.ToolbarView()
        sidebar_view.add_top_bar(Adw.HeaderBar(
            title_widget=Adw.WindowTitle(title=_("Files"))))
        sidebar_view.set_content(Gtk.ScrolledWindow(child=self.sidebar,
                                                    hscrollbar_policy=Gtk.PolicyType.NEVER))

        header = Adw.HeaderBar()
        nav = Gtk.Box(css_classes=["linked"])
        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text=_("Back"),
                                   action_name="win.back")
        self.fwd_btn = Gtk.Button(icon_name="go-next-symbolic", tooltip_text=_("Forward"),
                                  action_name="win.forward")
        nav.append(self.back_btn)
        nav.append(self.fwd_btn)
        header.pack_start(nav)

        self.pathbar = Gtk.Box(css_classes=["linked"])
        self.path_entry = Gtk.Entry(hexpand=True)
        self.path_entry.connect("activate", self._on_path_entry)
        self.path_stack = Gtk.Stack(hhomogeneous=False)
        path_scroller = Gtk.ScrolledWindow(child=self.pathbar, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                           hscrollbar_policy=Gtk.PolicyType.EXTERNAL)
        self.path_stack.add_named(path_scroller, "crumbs")
        self.path_stack.add_named(self.path_entry, "entry")
        self.path_stack.set_size_request(360, -1)
        header.set_title_widget(self.path_stack)

        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(_("New Folder"), "win.new-folder")
        section.append(_("Open in Terminal"), "win.terminal-here")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("Show Hidden Files"), "win.show-hidden")
        section.append(_("List View"), "win.list-view")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("New Window"), "app.new-window")
        section.append(_("About Files"), "app.about")
        menu.append_section(None, section)
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       primary=True))
        self.search_btn = Gtk.ToggleButton(icon_name="system-search-symbolic",
                                           tooltip_text=_("Search"))
        header.pack_end(self.search_btn)

        self.search_entry = Gtk.SearchEntry(hexpand=True, max_width_chars=40)
        self.search_entry.connect("search-changed", self._on_search)
        self.search_bar = Gtk.SearchBar(child=self.search_entry, show_close_button=True)
        self.search_bar.connect_entry(self.search_entry)
        self.search_btn.bind_property("active", self.search_bar, "search-mode-enabled",
                                      GObject.BindingFlags.BIDIRECTIONAL)
        self.search_bar.set_key_capture_widget(self)

        # Views
        self.grid = Gtk.GridView(model=self.selection, max_columns=12, min_columns=2,
                                 enable_rubberband=True, css_classes=["files-grid"])
        self.grid.set_factory(self._grid_factory())
        self.grid.connect("activate", lambda _v, pos: self.activate_item(pos))

        self.list = Gtk.ColumnView(model=self.selection, enable_rubberband=True,
                                   show_row_separators=False, css_classes=["files-list"])
        self.list.connect("activate", lambda _v, pos: self.activate_item(pos))
        for title, kind, expand in ((_("Name"), "name", True), (_("Size"), "size", False),
                                    (_("Modified"), "modified", False)):
            col = Gtk.ColumnViewColumn(title=title, factory=self._list_factory(kind),
                                       expand=expand, resizable=True)
            self.list.append_column(col)

        self.view_stack = Gtk.Stack()
        self.view_stack.add_named(Gtk.ScrolledWindow(child=self.grid), "grid")
        self.view_stack.add_named(Gtk.ScrolledWindow(child=self.list), "list")
        self.empty = Adw.StatusPage(icon_name="folder-symbolic", title=_("Folder is Empty"))
        self.view_stack.add_named(self.empty, "empty")

        for view in (self.grid, self.list):
            click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
            click.connect("pressed", self._on_context_click, view)
            view.add_controller(click)
        self.context_menu = Gtk.PopoverMenu(has_arrow=False, halign=Gtk.Align.START)
        self.context_menu.set_parent(self.view_stack)

        # Trash banner and progress
        self.banner = Adw.Banner(button_label=_("Empty Trash"), action_name="win.empty-trash",
                                 title=_("Items in the Trash are deleted permanently when emptied"))
        self.progress = Gtk.ProgressBar(show_text=True, css_classes=["osd"])
        self.progress_revealer = Gtk.Revealer(child=self.progress,
                                              transition_type=Gtk.RevealerTransitionType.SLIDE_UP)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.search_bar)
        content.append(self.banner)
        self.view_stack.set_vexpand(True)
        content.append(self.view_stack)
        content.append(self.progress_revealer)
        self.toast_overlay = Adw.ToastOverlay(child=content)

        content_view = Adw.ToolbarView()
        content_view.add_top_bar(header)
        content_view.set_content(self.toast_overlay)

        self.split = Adw.NavigationSplitView(
            sidebar=Adw.NavigationPage(child=sidebar_view, title=_("Files")),
            content=Adw.NavigationPage(child=content_view, title=_("Files")),
            min_sidebar_width=200, max_sidebar_width=240)
        self.set_content(self.split)
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 600sp"))
        bp.add_setter(self.split, "collapsed", True)
        self.add_breakpoint(bp)

    def _icon_for(self, info, size):
        thumb = info.get_attribute_byte_string("thumbnail::path")
        if thumb and size >= 48:
            return Gio.FileIcon.new(Gio.File.new_for_path(thumb))
        return info.get_icon() or Gio.ThemedIcon.new("text-x-generic")

    def _grid_factory(self):
        f = Gtk.SignalListItemFactory()

        def setup(_f, item):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          margin_top=8, margin_bottom=8, margin_start=4, margin_end=4)
            box.set_size_request(104, -1)
            box.append(Gtk.Image(pixel_size=64))
            box.append(Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, lines=2,
                                 ellipsize=Pango.EllipsizeMode.MIDDLE,
                                 justify=Gtk.Justification.CENTER, max_width_chars=14))
            item.set_child(box)

        def bind(_f, item):
            info = item.get_item()
            box = item.get_child()
            img, label = box.get_first_child(), box.get_last_child()
            img.set_from_gicon(self._icon_for(info, 64))
            label.set_label(info.get_display_name())
            box.set_opacity(0.6 if info.get_is_hidden() else 1.0)
            box.position = item.get_position()

        f.connect("setup", setup)
        f.connect("bind", bind)
        return f

    def _list_factory(self, kind):
        f = Gtk.SignalListItemFactory()

        def setup(_f, item):
            if kind == "name":
                box = Gtk.Box(spacing=10)
                box.append(Gtk.Image(pixel_size=24))
                box.append(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END))
                item.set_child(box)
            else:
                item.set_child(Gtk.Label(xalign=0, css_classes=["dim-label", "numeric"]))

        def bind(_f, item):
            info = item.get_item()
            w = item.get_child()
            w.position = item.get_position()
            if kind == "name":
                w.get_first_child().set_from_gicon(self._icon_for(info, 24))
                w.get_last_child().set_label(info.get_display_name())
            elif kind == "size":
                w.set_label(human_size(info))
            else:
                w.set_label(modified(info))

        f.connect("setup", setup)
        f.connect("bind", bind)
        return f

    # ----------------------------------------------------------- actions

    def _build_actions(self):
        def add(name, cb, accels=(), state=None):
            if state is None:
                action = Gio.SimpleAction.new(name, None)
                action.connect("activate", lambda *_: cb())
            else:
                action = Gio.SimpleAction.new_stateful(name, None, GLib.Variant("b", state))
                action.connect("change-state", lambda a, v: (a.set_state(v), cb(v.get_boolean())))
            self.add_action(action)
            if accels:
                self.get_application().set_accels_for_action(f"win.{name}", list(accels))
            return action

        add("back", self.go_back, ["<Alt>Left", "BackSpace"])
        add("forward", self.go_forward, ["<Alt>Right"])
        add("up", self.go_up, ["<Alt>Up"])
        add("home", lambda: self.open_location(Gio.File.new_for_path(GLib.get_home_dir())),
            ["<Alt>Home"])
        add("location", self.edit_location, ["<Ctrl>l"])
        add("open", self.open_selected, ["Return"])
        add("open-with", self.open_with)
        add("copy", lambda: self.to_clipboard("copy"), ["<Ctrl>c"])
        add("cut", lambda: self.to_clipboard("move"), ["<Ctrl>x"])
        add("paste", self.paste, ["<Ctrl>v"])
        add("rename", self.rename, ["F2"])
        add("trash", self.trash_selected, ["Delete"])
        add("delete", self.delete_selected, ["<Shift>Delete"])
        add("restore", self.restore_selected)
        add("empty-trash", self.empty_trash)
        add("new-folder", self.new_folder, ["<Ctrl><Shift>n"])
        add("properties", self.properties, ["<Alt>Return"])
        add("select-all", lambda: self.selection.select_all(), ["<Ctrl>a"])
        add("terminal-here", self.terminal_here)
        add("reload", self.reload, ["F5", "<Ctrl>r"])
        add("show-hidden", self.set_show_hidden, ["<Ctrl>h"], state=False)
        add("list-view", self.set_list_view, ["<Ctrl>1"], state=False)
        add("search", lambda: self.search_btn.set_active(True), ["<Ctrl>f"])
        self._update_nav()

    def _action(self, name):
        return self.lookup_action(name)

    # --------------------------------------------------------- navigation

    def open_location(self, gfile, record=True):
        if gfile is None:
            return
        info = None
        try:
            info = gfile.query_info("standard::type", Gio.FileQueryInfoFlags.NONE, None)
        except GLib.Error as err:
            self.toast(err.message)
            return
        if info.get_file_type() != Gio.FileType.DIRECTORY:
            self.launch(gfile)
            return
        if record and self.current is not None and not self.current.equal(gfile):
            self.back_stack.append(self.current)
            self.forward_stack.clear()
        self.current = gfile
        self.dirlist.set_file(gfile)
        self.search_btn.set_active(False)
        self._update_path()
        self._update_nav()
        self.sidebar.select_file(gfile)
        in_trash = gfile.get_uri_scheme() == "trash"
        self.banner.set_revealed(in_trash)
        self.set_title(self._display_name(gfile))
        self.split.set_show_content(True)

    def _display_name(self, gfile):
        if gfile.get_uri_scheme() == "trash":
            return _("Trash")
        path = gfile.get_path()
        if path == GLib.get_home_dir():
            return _("Home")
        if path == "/":
            return _("Computer")
        return gfile.get_basename() or gfile.get_uri()

    def _update_nav(self):
        if self._action("back") is None:
            return
        self._action("back").set_enabled(bool(self.back_stack))
        self._action("forward").set_enabled(bool(self.forward_stack))
        parent = self.current.get_parent() if self.current else None
        self._action("up").set_enabled(parent is not None)

    def _update_path(self):
        while (c := self.pathbar.get_first_child()) is not None:
            self.pathbar.remove(c)
        self.path_stack.set_visible_child_name("crumbs")
        crumbs = []
        f = self.current
        home = Gio.File.new_for_path(GLib.get_home_dir())
        while f is not None:
            crumbs.append(f)
            if f.equal(home):
                break
            f = f.get_parent()
        for f in reversed(crumbs):
            btn = Gtk.Button(label=self._display_name(f), css_classes=["flat"])
            btn.connect("clicked", lambda _b, target=f: self.open_location(target))
            self.pathbar.append(btn)
        last = self.pathbar.get_last_child()
        if last:
            last.add_css_class("heading")

    def edit_location(self):
        self.path_entry.set_text(self.current.get_path() or self.current.get_uri())
        self.path_stack.set_visible_child_name("entry")
        self.path_entry.grab_focus()

    def _on_path_entry(self, entry):
        text = os.path.expanduser(entry.get_text().strip())
        gfile = Gio.File.new_for_commandline_arg(text)
        self.open_location(gfile)
        self.path_stack.set_visible_child_name("crumbs")

    def go_back(self):
        if self.back_stack:
            self.forward_stack.append(self.current)
            self.open_location(self.back_stack.pop(), record=False)

    def go_forward(self):
        if self.forward_stack:
            self.back_stack.append(self.current)
            self.open_location(self.forward_stack.pop(), record=False)

    def go_up(self):
        parent = self.current.get_parent()
        if parent:
            self.open_location(parent)

    def reload(self):
        self.dirlist.set_file(None)
        self.dirlist.set_file(self.current)

    # --------------------------------------------------- filtering/sort

    def _filter_func(self, info):
        name = info.get_display_name()
        if not self.show_hidden and (info.get_is_hidden() or info.get_is_backup()):
            return False
        if self.search_text and self.search_text not in name.casefold():
            return False
        return True

    def _sort_func(self, a, b, *_args):
        da, db = is_dir(a), is_dir(b)
        if da != db:
            return -1 if da else 1
        na, nb = a.get_display_name().casefold(), b.get_display_name().casefold()
        return (na > nb) - (na < nb)

    def _on_search(self, entry):
        self.search_text = entry.get_text().casefold()
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_empty()

    def set_show_hidden(self, value):
        self.show_hidden = value
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self._update_empty()

    def set_list_view(self, value):
        self._view_name = "list" if value else "grid"
        self._update_empty()

    def _on_loading(self, *_a):
        if not self.dirlist.is_loading():
            err = self.dirlist.get_error()
            if err:
                self.toast(err.message)
        self._update_empty()

    def _update_empty(self):
        if not hasattr(self, "view_stack"):
            return
        name = getattr(self, "_view_name", "grid")
        if not self.dirlist.is_loading() and self.model.get_n_items() == 0:
            self.empty.set_title(_("No Results Found") if self.search_text
                                 else _("Trash is Empty") if self.in_trash()
                                 else _("Folder is Empty"))
            self.empty.set_icon_name("user-trash-symbolic" if self.in_trash()
                                     else "folder-symbolic")
            name = "empty"
        self.view_stack.set_visible_child_name(name)

    def in_trash(self):
        return self.current is not None and self.current.get_uri_scheme() == "trash"

    # ------------------------------------------------------- selection

    def selected_infos(self):
        bits = self.selection.get_selection()
        out = []
        for i in range(bits.get_size()):
            out.append(self.model.get_item(bits.get_nth(i)))
        return out

    def selected_files(self):
        return [file_of(i) for i in self.selected_infos()]

    def activate_item(self, pos):
        info = self.model.get_item(pos)
        if info is None:
            return
        f = file_of(info)
        if is_dir(info):
            self.open_location(f)
        else:
            self.launch(f)

    def open_selected(self):
        infos = self.selected_infos()
        if len(infos) == 1 and is_dir(infos[0]):
            self.open_location(file_of(infos[0]))
            return
        for info in infos:
            if is_dir(info):
                self.get_application().open_window(file_of(info))
            else:
                self.launch(file_of(info))

    def launch(self, gfile, ask=False):
        launcher = Gtk.FileLauncher(file=gfile, always_ask=ask)

        def done(l, res):
            try:
                l.launch_finish(res)
            except GLib.Error as err:
                if not err.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED):
                    self.toast(err.message)
        launcher.launch(self, None, done)

    def open_with(self):
        files = self.selected_files()
        if files:
            self.launch(files[0], ask=True)

    # ---------------------------------------------------- context menu

    def _on_context_click(self, gesture, _n, x, y, view):
        widget = view.pick(x, y, Gtk.PickFlags.DEFAULT)
        pos = None
        while widget is not None and widget is not view:
            if hasattr(widget, "position"):
                pos = widget.position
                break
            widget = widget.get_parent()
        if pos is not None and not self.selection.is_selected(pos):
            self.selection.select_item(pos, True)
        elif pos is None:
            self.selection.unselect_all()

        menu = Gio.Menu()
        has_sel = pos is not None
        trash = self.in_trash()
        if has_sel:
            s = Gio.Menu()
            if trash:
                s.append(_("Restore"), "win.restore")
                s.append(_("Delete Permanently"), "win.delete")
            else:
                s.append(_("Open"), "win.open")
                s.append(_("Open With…"), "win.open-with")
            menu.append_section(None, s)
            if not trash:
                s = Gio.Menu()
                s.append(_("Cut"), "win.cut")
                s.append(_("Copy"), "win.copy")
                s.append(_("Rename…"), "win.rename")
                menu.append_section(None, s)
                s = Gio.Menu()
                s.append(_("Move to Trash"), "win.trash")
                menu.append_section(None, s)
            s = Gio.Menu()
            s.append(_("Properties"), "win.properties")
            menu.append_section(None, s)
        elif trash:
            menu.append(_("Empty Trash"), "win.empty-trash")
        else:
            s = Gio.Menu()
            s.append(_("New Folder…"), "win.new-folder")
            s.append(_("Paste"), "win.paste")
            menu.append_section(None, s)
            s = Gio.Menu()
            s.append(_("Select All"), "win.select-all")
            s.append(_("Open in Terminal"), "win.terminal-here")
            s.append(_("Properties"), "win.properties")
            menu.append_section(None, s)

        self.context_menu.set_menu_model(menu)
        ok, px, py = view.translate_coordinates(self.view_stack, x, y)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(px), int(py), 1, 1
        self.context_menu.set_pointing_to(rect)
        self.context_menu.popup()

    # ------------------------------------------------------ operations

    def toast(self, msg):
        self.toast_overlay.add_toast(Adw.Toast(title=msg, timeout=3))

    def to_clipboard(self, mode):
        files = self.selected_files()
        if not files:
            return
        CLIPBOARD["mode"], CLIPBOARD["files"] = mode, files
        filelist = Gdk.FileList.new_from_list(files)
        self.get_clipboard().set(filelist)
        n = len(files)
        self.toast((_("{n} item(s) cut") if mode == "move" else _("{n} item(s) copied"))
                   .format(n=n))

    def paste(self):
        target = self.current.get_path()
        if target is None:
            return
        if CLIPBOARD["files"]:
            self._run_job(CLIPBOARD["mode"], [f.get_path() for f in CLIPBOARD["files"]
                                              if f.get_path()], target)
            if CLIPBOARD["mode"] == "move":
                CLIPBOARD["mode"], CLIPBOARD["files"] = None, []
            return

        def got(clip, res):
            try:
                value = clip.read_value_finish(res)
            except GLib.Error:
                return
            paths = [f.get_path() for f in value.get_files() if f.get_path()]
            if paths:
                self._run_job("copy", paths, target)
        self.get_clipboard().read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, got)

    def _run_job(self, kind, paths, target):
        if not paths:
            return
        job = Job(kind, paths, target)
        self.progress.set_text(job.label)
        self.progress.set_fraction(0)
        self.progress_revealer.set_reveal_child(True)
        job.connect("progress", lambda _j, frac, _n: self.progress.set_fraction(frac))

        def finished(_j, error):
            self.jobs.remove(job)
            if not self.jobs:
                self.progress_revealer.set_reveal_child(False)
            if error:
                self.toast(error)
        job.connect("finished", finished)
        self.jobs.append(job)
        job.start()

    def trash_selected(self):
        if self.in_trash():
            self.delete_selected()
            return
        files = self.selected_files()
        for f in files:
            f.trash_async(GLib.PRIORITY_DEFAULT, None, self._trash_done)
        if files:
            self.toast(_("{n} item(s) moved to the Trash").format(n=len(files)))

    def _trash_done(self, f, res):
        try:
            f.trash_finish(res)
        except GLib.Error as err:
            self.toast(err.message)

    def delete_selected(self):
        files = self.selected_files()
        if not files:
            return
        dialog = Adw.AlertDialog(
            heading=_("Permanently Delete {n} Item(s)?").format(n=len(files)),
            body=_("Deleted items cannot be restored."))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("delete", _("Delete"))
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def response(_d, resp):
            if resp == "delete":
                for f in files:
                    self._delete_recursive(f)
        dialog.connect("response", response)
        dialog.present(self)

    def _delete_recursive(self, gfile):
        try:
            info = gfile.query_info("standard::type", Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None)
            if info.get_file_type() == Gio.FileType.DIRECTORY:
                for child in gfile.enumerate_children("standard::name",
                                                      Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None):
                    self._delete_recursive(gfile.get_child(child.get_name()))
            gfile.delete(None)
        except GLib.Error as err:
            self.toast(err.message)

    def restore_selected(self):
        for info in self.selected_infos():
            orig = info.get_attribute_byte_string("trash::orig-path")
            if not orig:
                continue
            dest = Gio.File.new_for_path(unique_destination(os.path.dirname(orig),
                                                            os.path.basename(orig)))
            try:
                file_of(info).move(dest, Gio.FileCopyFlags.NONE, None, None)
            except GLib.Error as err:
                self.toast(err.message)

    def empty_trash(self):
        dialog = Adw.AlertDialog(heading=_("Empty Trash?"),
                                 body=_("All items in the Trash will be permanently deleted."))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("empty", _("Empty Trash"))
        dialog.set_response_appearance("empty", Adw.ResponseAppearance.DESTRUCTIVE)

        def response(_d, resp):
            if resp != "empty":
                return
            trash = Gio.File.new_for_uri(TRASH_URI)
            try:
                for child in trash.enumerate_children("standard::name",
                                                      Gio.FileQueryInfoFlags.NONE, None):
                    trash.get_child(child.get_name()).delete(None)
            except GLib.Error as err:
                self.toast(err.message)
        dialog.connect("response", response)
        dialog.present(self)

    def _ask_name(self, heading, initial, action_label, callback, select_stem=True):
        dialog = Adw.AlertDialog(heading=heading)
        entry = Gtk.Entry(text=initial, activates_default=True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ok", action_label)
        dialog.set_default_response("ok")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def response(_d, resp):
            name = entry.get_text().strip()
            if resp == "ok" and name and "/" not in name:
                callback(name)
        dialog.connect("response", response)
        dialog.present(self)
        entry.grab_focus()
        stem = os.path.splitext(initial)[0] if select_stem else initial
        entry.select_region(0, len(stem) if stem else -1)

    def rename(self):
        infos = self.selected_infos()
        if len(infos) != 1:
            return
        info = infos[0]

        def do(name):
            try:
                file_of(info).set_display_name(name, None)
            except GLib.Error as err:
                self.toast(err.message)
        self._ask_name(_("Rename"), info.get_display_name(), _("Rename"), do,
                       select_stem=not is_dir(info))

    def new_folder(self):
        if self.current.get_path() is None:
            return

        def do(name):
            try:
                self.current.get_child(name).make_directory(None)
            except GLib.Error as err:
                self.toast(err.message)
        self._ask_name(_("New Folder"), _("Untitled Folder"), _("Create"), do, False)

    def terminal_here(self):
        path = self.current.get_path()
        if path:
            try:
                GLib.spawn_async(["x-terminal-emulator"], working_directory=path,
                                 flags=GLib.SpawnFlags.SEARCH_PATH)
            except GLib.Error as err:
                self.toast(err.message)

    def properties(self):
        files = self.selected_files() or [self.current]
        from aurora.files.properties import PropertiesDialog
        PropertiesDialog(files).present(self)
