"""Aurora Files main window."""

import os
import functools
import hashlib
import subprocess
import shutil
import threading
from dataclasses import dataclass, field

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

from aurora import activities, apps
from aurora.files.icons import icon_for
from aurora.files.history import History, trashed_uri
from aurora.files import volumes
from aurora.files.operations import Job, unique_destination
from aurora.i18n import _, ngettext

ATTRS = ",".join([
    "standard::name", "standard::display-name", "standard::icon", "standard::type",
    "standard::size", "standard::is-hidden", "standard::is-backup", "standard::content-type",
    "standard::symbolic-icon", "time::modified", "thumbnail::path", "trash::orig-path",
    "trash::deletion-date", "access::can-write",
])

TRASH_URI = "trash:///"

# Shared by every window of the app: (mode, [Gio.File]).
CLIPBOARD = {"mode": None, "files": []}


@dataclass
class FileTab:
    location: Gio.File
    back: list = field(default_factory=list)
    forward: list = field(default_factory=list)
    search: str = ""
    view: str = "grid"


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


@functools.lru_cache(maxsize=65536)
def sort_key(name):
    """Names in the order people expect, as in Windows: f2 before f10, in the
    language's alphabetical order."""
    return GLib.utf8_collate_key_for_filename(name.casefold(), -1)


class Sidebar(Gtk.ListBox):
    __gsignals__ = {"open": (GObject.SignalFlags.RUN_FIRST, None, (Gio.File,))}

    def __init__(self, drop_callback=None):
        super().__init__(css_classes=["navigation-sidebar"])
        self.drop_callback = drop_callback
        self.connect("row-activated", self._on_row)
        self.volumes = Gio.VolumeMonitor.get()
        for sig in ("mount-added", "mount-removed", "volume-added", "volume-removed"):
            self.volumes.connect(sig, lambda *a: self.rebuild())
        self.rebuild()

    def _add(self, icon, label, file=None, volume=None, eject=None):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(spacing=12, margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        # Set the size before the icon.  PyGObject applies constructor
        # properties in order, and resolving a GIcon at the default size (-1)
        # produces GTK criticals (and can leave volume icons blank).
        image = Gtk.Image(pixel_size=16)
        if isinstance(icon, str):
            image.set_from_icon_name(icon)
        else:
            image.set_from_gicon(icon)
        box.append(image)
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
        row.eject = eject
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY,
                                 propagation_phase=Gtk.PropagationPhase.CAPTURE)
        right.connect("pressed", self._on_context, row)
        row.add_controller(right)
        if file is not None and file.get_path() is not None and os.path.isdir(file.get_path()):
            target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            target.connect("drop", lambda _t, value, _x, _y, dest=file:
                           self.drop_callback(value, dest, move=FilesWindow._drop_is_move(_t))
                           if self.drop_callback else False)
            row.add_controller(target)
        self.append(row)

    def _on_context(self, gesture, _n, x, y, row):
        window = self.get_root()
        if not isinstance(window, FilesWindow):
            return
        pop = Gtk.Popover(has_arrow=False, css_classes=["aurora-context-menu"])
        pop.set_parent(row)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                      margin_top=5, margin_bottom=5, margin_start=5, margin_end=5)

        def action(label, callback):
            button = Gtk.Button(label=label, css_classes=["flat", "context-action"])
            button.get_child().set_xalign(0)
            button.connect("clicked", lambda *_: (pop.popdown(), callback()))
            box.append(button)

        action(_("Open"), lambda: self._on_row(self, row))
        if row.file is not None:
            action(_("New Tab"), lambda: window.new_tab(row.file))
            action(_("New Window"), lambda: apps.spawn(["aurora-files", row.file.get_uri()]))
            box.append(Gtk.Separator())
            path = row.file.get_path()
            if path and os.path.isdir(path):
                action(_("Open in Terminal"), lambda: apps.spawn(
                    ["ptyxis", "--new-window", f"--working-directory={path}"]))
            action(_("Copy Path"), lambda: self.get_clipboard().set(
                path or row.file.get_uri()))
            action(_("Properties"), lambda: self._properties(row.file))
        if row.eject is not None:
            box.append(Gtk.Separator())
            action(_("Eject"), lambda: row.eject.unmount_with_operation(
                Gio.MountUnmountFlags.NONE, None, None, None, None))
        pop.set_child(box)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.popup()
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _properties(self, file):
        from aurora.files.properties import PropertiesDialog
        PropertiesDialog([file]).present(self.get_root())

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
        # Other computers and NAS boxes on the network, and any other server.
        self._add("network-workgroup-symbolic", _("Network"), Gio.File.new_for_uri("network:///"))
        self._add("list-add-symbolic", _("Connect to Server…"))
        # A disk mounted or removed rebuilds the list: keep the open place selected.
        window = self.get_root()
        current = getattr(window, "current", None) if isinstance(window, FilesWindow) else None
        if current is not None:
            self.select_file(current)

    def _on_row(self, _box, row):
        if row.file is None and row.volume is None:
            window = self.get_root()
            if isinstance(window, FilesWindow):
                window.connect_to_server()
            return
        if row.file is not None:
            self.emit("open", row.file)
        elif row.volume is not None:
            device = row.volume.get_identifier(Gio.VOLUME_IDENTIFIER_KIND_UNIX_DEVICE) or ""
            if device and volumes.filesystem_type(device) in volumes.WINDOWS_TYPES:
                self._mount_windows(row.volume, device)
                return

            def mounted(vol, res):
                try:
                    vol.mount_finish(res)
                except GLib.Error as err:
                    self._mount_failed(vol, err)
                    return
                if vol.get_mount():
                    self.emit("open", vol.get_mount().get_root())
            row.volume.mount(Gio.MountMountFlags.NONE, Gtk.MountOperation.new(self.get_root()),
                             None, mounted)

    def _toast(self, message, timeout=3):
        window = self.get_root()
        if isinstance(window, FilesWindow):
            window.toast(message, timeout=timeout)
        else:
            print(message)

    def _mount_failed(self, vol, err):
        """Say why a disk didn't open (nothing when the password prompt was closed)."""
        print(f"aurora-files: mounting {vol.get_name()} failed: {err.message}")
        if not volumes.is_cancelled(err):
            self._toast(_("Couldn't open {name}: {error}").format(name=vol.get_name(),
                                                                 error=err.message))

    def _mount_windows(self, vol, device):
        """Windows' partition: opened read-only when Windows left it in use
        (Fast Startup, hibernation, a pending disk check), with one password."""
        def mounted(path, err, read_only):
            if path is None:
                self._mount_failed(vol, err)
                return
            if read_only:
                self._toast(_("{name} is read-only: Windows wasn't fully shut down").format(
                    name=vol.get_name()), timeout=8)
            self.emit("open", Gio.File.new_for_path(path))
        volumes.mount_windows(device, mounted)

    def select_file(self, gfile):
        """Highlight the place that holds gfile (Desktop for ~/Desktop/weird),
        the closest one when several do (Desktop rather than Home)."""
        best, depth = None, -1
        i = 0
        while (row := self.get_row_at_index(i)) is not None:
            i += 1
            f = row.file
            if f is None or not (f.equal(gfile) or gfile.has_prefix(f)):
                continue
            here = len((f.get_path() or f.get_uri()).rstrip("/").split("/"))
            if here > depth:
                best, depth = row, here
        if best is not None:
            self.select_row(best)
        else:
            self.unselect_all()


class FilesWindow(Adw.ApplicationWindow):
    def __init__(self, app, location=None):
        super().__init__(application=app, default_width=1000, default_height=640)
        self.current = None
        self.back_stack, self.forward_stack = [], []
        self.show_hidden = False
        self.search_text = ""
        self.jobs = []
        self._job_queue = []
        self.history = History()
        self._history_busy = False
        self.tabs = []
        self.active_tab = -1

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
        self.new_tab(location or Gio.File.new_for_path(GLib.get_home_dir()))

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        self.sidebar = Sidebar(self._drop_on_location)
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
        path_keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        path_keys.connect("key-pressed", self._on_path_key)
        self.path_entry.add_controller(path_keys)
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
        section.append(_("New File…"), "win.new-file")
        section.append(_("Open in Terminal"), "win.terminal-here")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("Undo"), "win.undo")
        section.append(_("Redo"), "win.redo")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("Show Hidden Files"), "win.show-hidden")
        section.append(_("List View"), "win.list-view")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("New Tab"), "win.new-tab")
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

        self.tab_buttons = Gtk.Box(spacing=4, css_classes=["files-tabs"])
        tab_scroller = Gtk.ScrolledWindow(child=self.tab_buttons, hexpand=True,
                                          vscrollbar_policy=Gtk.PolicyType.NEVER,
                                          hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        self.tab_strip = Gtk.Box(spacing=6, margin_start=12, margin_end=12,
                                 margin_top=5, margin_bottom=5)
        self.tab_strip.append(tab_scroller)
        add_tab = Gtk.Button(icon_name="list-add-symbolic", css_classes=["flat"],
                             tooltip_text=_("New Tab"))
        add_tab.connect("clicked", lambda *_: self.new_tab())
        self.tab_strip.append(add_tab)

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

        # Capture on the stack also covers empty folders and unused space in
        # the scroller, while leaving item clicks and rubberband drags to GTK.
        clear = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY,
                                 propagation_phase=Gtk.PropagationPhase.CAPTURE)
        clear.connect("pressed", self._on_background_click)
        self.view_stack.add_controller(clear)
        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY,
                                 propagation_phase=Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_context_click, self.view_stack)
        self.view_stack.add_controller(click)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        drop.connect("drop", self._drop_on_view)
        self.view_stack.add_controller(drop)
        for view in (self.grid, self.list):
            # Space previews the selection (Quick Look), before the view sees it.
            keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
            keys.connect("key-pressed", self._on_view_key)
            view.add_controller(keys)
        self.quicklook = None
        self.context_menu = Gtk.Popover(has_arrow=False, halign=Gtk.Align.START,
                                        css_classes=["aurora-context-menu"])
        self.context_menu.set_parent(self.view_stack)

        # Trash banner and progress
        self.banner = Adw.Banner(button_label=_("Empty Trash"), action_name="win.empty-trash",
                                 title=_("Items in the Trash are deleted permanently when emptied"))
        self.progress = Gtk.ProgressBar(show_text=True, css_classes=["osd"])
        progress_box = Gtk.Box(spacing=8, margin_start=12, margin_end=12,
                               margin_top=6, margin_bottom=6)
        self.progress.set_hexpand(True)
        progress_box.append(self.progress)
        self.cancel_job_button = Gtk.Button(icon_name="process-stop-symbolic",
                                            tooltip_text=_("Cancel transfer"))
        self.cancel_job_button.connect("clicked", lambda *_: self.jobs[-1].cancel()
                                       if self.jobs else None)
        progress_box.append(self.cancel_job_button)
        self.retry_job_button = Gtk.Button(label=_("Retry"), visible=False)
        self.retry_job_button.connect("clicked", lambda *_: self._retry_job())
        progress_box.append(self.retry_job_button)
        self._retry_args = None
        self.progress_revealer = Gtk.Revealer(child=progress_box,
                                              transition_type=Gtk.RevealerTransitionType.SLIDE_UP)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.tab_strip)
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

    def _render_tabs(self):
        while (child := self.tab_buttons.get_first_child()) is not None:
            self.tab_buttons.remove(child)
        for index, state in enumerate(self.tabs):
            chip = Gtk.Box(spacing=2, css_classes=["files-tab"])
            if index == self.active_tab:
                chip.add_css_class("active-tab")
            title = self._display_name(state.location)
            label = Gtk.Label(label=title, max_width_chars=18,
                              ellipsize=Pango.EllipsizeMode.MIDDLE)
            choose = Gtk.Button(child=label, css_classes=["flat"],
                                tooltip_text=state.location.get_parse_name())
            choose.connect("clicked", lambda _b, i=index: self.switch_tab(i))
            chip.append(choose)
            close = Gtk.Button(icon_name="window-close-symbolic", css_classes=["flat"],
                               tooltip_text=_("Close Tab"))
            close.connect("clicked", lambda _b, i=index: self.close_tab(i))
            chip.append(close)
            target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            target.connect("drop", lambda _t, value, _x, _y, dest=state.location:
                           self._drop_on_location(value, dest, move=self._drop_is_move(_t)))
            chip.add_controller(target)
            self.tab_buttons.append(chip)

    def _save_tab(self):
        if self.active_tab < 0:
            return
        state = self.tabs[self.active_tab]
        state.location = self.current
        state.back = list(self.back_stack)
        state.forward = list(self.forward_stack)
        state.search = self.search_entry.get_text()
        state.view = getattr(self, "_view_name", "grid")

    def new_tab(self, location=None):
        self.tabs.append(FileTab(location or self.current or
                                 Gio.File.new_for_path(GLib.get_home_dir())))
        self.switch_tab(len(self.tabs) - 1)

    def switch_tab(self, index):
        if not 0 <= index < len(self.tabs) or index == self.active_tab:
            return
        self._save_tab()
        self.active_tab = index
        state = self.tabs[index]
        self.back_stack, self.forward_stack = list(state.back), list(state.forward)
        self.open_location(state.location, record=False)
        self.set_list_view(state.view == "list")
        self.search_entry.set_text(state.search)
        self.search_btn.set_active(bool(state.search))
        self._render_tabs()

    def close_tab(self, index=None):
        index = self.active_tab if index is None else index
        if not 0 <= index < len(self.tabs):
            return
        if len(self.tabs) == 1:
            self.close()
            return
        active = index == self.active_tab
        del self.tabs[index]
        if active:
            self.active_tab = -1
            self.switch_tab(min(index, len(self.tabs) - 1))
        else:
            if index < self.active_tab:
                self.active_tab -= 1
            self._render_tabs()

    def cycle_tab(self, step):
        if len(self.tabs) > 1:
            self.switch_tab((self.active_tab + step) % len(self.tabs))

    def _icon_for(self, info, size):
        thumb = info.get_attribute_byte_string("thumbnail::path")
        if thumb and size >= 48:
            return Gio.FileIcon.new(Gio.File.new_for_path(thumb))
        return icon_for(info)

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
            drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            drag.connect("prepare", self._drag_prepare, item)
            box.add_controller(drag)
            folder_drop = Gtk.DropTarget.new(Gdk.FileList,
                                              Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            folder_drop.connect("drop", self._drop_on_item, item)
            box.add_controller(folder_drop)

        def bind(_f, item):
            info = item.get_item()
            box = item.get_child()
            img, label = box.get_first_child(), box.get_last_child()
            img.set_from_gicon(self._icon_for(info, 64))
            changed = info.get_name() in getattr(self, "_git_changed", set())
            label.set_label(info.get_display_name() + ("  ●" if changed else ""))
            (label.add_css_class if changed else label.remove_css_class)("files-git-changed")
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
            if kind == "name":
                drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
                drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                drag.connect("prepare", self._drag_prepare, item)
                item.get_child().add_controller(drag)
                folder_drop = Gtk.DropTarget.new(Gdk.FileList,
                                                  Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
                folder_drop.connect("drop", self._drop_on_item, item)
                item.get_child().add_controller(folder_drop)

        def bind(_f, item):
            info = item.get_item()
            w = item.get_child()
            w.position = item.get_position()
            if kind == "name":
                w.get_first_child().set_from_gicon(self._icon_for(info, 24))
                changed = info.get_name() in getattr(self, "_git_changed", set())
                name = w.get_last_child()
                name.set_label(info.get_display_name() + ("  ●" if changed else ""))
                (name.add_css_class if changed else name.remove_css_class)("files-git-changed")
            elif kind == "size":
                w.set_label(human_size(info))
            else:
                w.set_label(modified(info))

        f.connect("setup", setup)
        f.connect("bind", bind)
        return f

    def _drag_prepare(self, _source, _x, _y, item):
        info = item.get_item()
        if info is None or self.in_trash():
            return None
        files = (self.selected_files() if self.selection.is_selected(item.get_position())
                 else [file_of(info)])
        files = [f for f in files if f is not None and f.get_path()]
        if not files:
            return None
        return Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list(files))

    @staticmethod
    def _drop_is_move(target):
        from aurora.dnd import is_move
        return is_move(target)

    def _drop_on_item(self, target, value, _x, _y, item):
        info = item.get_item()
        if info is None or not is_dir(info):
            return False
        return self._drop_on_location(value, file_of(info), move=self._drop_is_move(target))

    def _drop_on_location(self, value, destination, move=False):
        if not isinstance(value, Gdk.FileList) or destination is None:
            return False
        target = destination.get_path()
        if target is None or not os.path.isdir(target):
            return False
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        if not paths:
            return False
        self._run_job("move" if move else "copy", paths, target)
        return True

    def _drop_on_view(self, _target, value, x, y):
        if self.in_trash():
            return False
        destination = self.current
        pos = self._item_position(self.view_stack, x, y)
        if pos is not None:
            info = self.model.get_item(pos)
            if info is not None and is_dir(info):
                destination = file_of(info)
        return self._drop_on_location(value, destination,
                                      move=self._drop_is_move(_target))

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
        # Return is handled by the file views' key controller.  A window-wide
        # accelerator would steal it from the Ctrl+L entry and name dialogs.
        add("open", self.open_selected)
        add("open-with", self.open_with)
        add("copy", lambda: self.to_clipboard("copy"), ["<Ctrl>c"])
        add("new-tab", self.new_tab, ["<Ctrl>t"])
        add("close-tab", self.close_tab, ["<Ctrl>w"])
        add("next-tab", lambda: self.cycle_tab(1), ["<Ctrl>Tab"])
        add("previous-tab", lambda: self.cycle_tab(-1), ["<Ctrl><Shift>Tab"])
        add("duplicate", self.duplicate_selected, ["<Ctrl>d"])
        add("cut", lambda: self.to_clipboard("move"), ["<Ctrl>x"])
        add("paste", self.paste, ["<Ctrl>v"])
        add("undo", self.undo, ["<Ctrl>z"])
        add("redo", self.redo, ["<Ctrl><Shift>z", "<Ctrl>y"])
        add("rename", self.rename, ["F2"])
        add("batch-rename", self.batch_rename)
        add("compress", self.compress)
        add("resize-images", self.resize_images)
        add("file-users", self.file_users)
        add("copy-path", self.copy_paths, ["<Ctrl><Shift>c"])
        add("extract-here", self.extract_here)
        add("connect-server", self.connect_to_server)
        add("checksums", self.checksums)
        add("compare-folders", self.compare_folders)
        add("ai-git-summary", self.summarize_git_changes)
        add("trash", self.trash_selected, ["Delete"])
        add("delete", self.delete_selected, ["<Shift>Delete"])
        add("restore", self.restore_selected)
        add("empty-trash", self.empty_trash)
        add("new-folder", self.new_folder, ["<Ctrl><Shift>n"])
        add("new-file", self.new_file)
        self._update_history_actions()
        add("properties", self.properties, ["<Alt>Return"])
        add("select-all", lambda: self.selection.select_all(), ["<Ctrl>a"])
        add("terminal-here", self.terminal_here)
        add("quick-look", self.quick_look)
        add("send-nearby", self.send_nearby)
        add("ai-summarize", lambda: self.ask_ai(summarize=True))
        add("ai-ask", lambda: self.ask_ai(summarize=False))
        add("reload", self.reload, ["F5", "<Ctrl>r"])
        add("show-hidden", self.set_show_hidden, ["<Ctrl>h"], state=False)
        add("list-view", self.set_list_view, ["<Ctrl>1"], state=False)
        add("search", lambda: self.search_btn.set_active(True), ["<Ctrl>f"])
        self._update_nav()

    def _action(self, name):
        return self.lookup_action(name)

    def _update_history_actions(self):
        self._action("undo").set_enabled(bool(self.history.undo_stack) and
                                          not self._history_busy and not self.jobs and
                                          not self._job_queue)
        self._action("redo").set_enabled(bool(self.history.redo_stack) and
                                          not self._history_busy and not self.jobs and
                                          not self._job_queue)

    def _record_history(self, kind, pairs):
        try:
            self.history.record(kind, pairs)
        except OSError as err:
            self.toast(str(err))
        self._update_history_actions()

    def undo(self):
        self._apply_history("undo")

    def redo(self):
        self._apply_history("redo")

    def _apply_history(self, direction):
        if self._history_busy or self.jobs or self._job_queue:
            return
        stack = self.history.undo_stack if direction == "undo" else self.history.redo_stack
        if not stack:
            return
        self._history_busy = True
        self._update_history_actions()

        def worker():
            error = ""
            try:
                getattr(self.history, direction)()
            except (OSError, shutil.Error) as err:
                error = str(err)

            def finished():
                self._history_busy = False
                self._update_history_actions()
                if error:
                    self.toast(error)
                else:
                    self.reload()
                return GLib.SOURCE_REMOVE
            GLib.idle_add(finished)
        threading.Thread(target=worker, daemon=True).start()

    # --------------------------------------------------------- navigation

    def open_location(self, gfile, record=True):
        if gfile is None:
            return
        info = None
        try:
            info = gfile.query_info("standard::type", Gio.FileQueryInfoFlags.NONE, None)
        except GLib.Error as err:
            if err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.NOT_MOUNTED):
                self.mount_and_open(gfile)
                return
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
        self._refresh_git_status(gfile)
        self._animate_items()
        self.search_btn.set_active(False)
        self._update_path()
        self._update_nav()
        self.sidebar.select_file(gfile)
        in_trash = gfile.get_uri_scheme() == "trash"
        self.banner.set_revealed(in_trash)
        self.set_title(self._display_name(gfile))
        self.split.set_show_content(True)
        if self.active_tab >= 0:
            self.tabs[self.active_tab].location = gfile
            self._render_tabs()

    def _display_name(self, gfile):
        if gfile.get_uri_scheme() == "trash":
            return _("Trash")
        if gfile.get_uri_scheme() == "network":
            return _("Network")
        if gfile.get_path() is None and gfile.get_parent() is None:
            # The top of a server: its name, not "/".
            return GLib.Uri.parse(gfile.get_uri(), GLib.UriFlags.NONE).get_host() or gfile.get_uri()
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
        # Ctrl+L is primarily used to type a different path.  Selecting the
        # current value also lets typing replace it, as in browsers and other
        # file managers, instead of silently appending to it.
        def focus_entry():
            self.path_entry.grab_focus()
            self.path_entry.select_region(0, -1)
            return GLib.SOURCE_REMOVE
        GLib.idle_add(focus_entry)

    def _on_path_entry(self, entry):
        text = os.path.expanduser(entry.get_text().strip())
        gfile = Gio.File.new_for_commandline_arg(text)
        self.open_location(gfile)
        self.path_stack.set_visible_child_name("crumbs")

    def _on_path_key(self, _ctrl, keyval, _code, _state):
        if keyval != Gdk.KEY_Escape:
            return False
        self.path_stack.set_visible_child_name("crumbs")
        view = self.list if self.view_stack.get_visible_child_name() == "list" else self.grid
        view.grab_focus()
        return True

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

    def _refresh_git_status(self, gfile):
        path = gfile.get_path()
        self._git_changed = set()
        self._git_generation = getattr(self, "_git_generation", 0) + 1
        generation = self._git_generation
        if not path or not os.path.isdir(path):
            return

        def work():
            try:
                result = subprocess.run(
                    ["git", "-C", path, "status", "--porcelain=v1", "--untracked-files=normal",
                     "--", "."], capture_output=True, text=True, timeout=6)
                changed = {line[3:].split(" -> ")[-1] for line in result.stdout.splitlines()
                           if len(line) > 3 and "/" not in line[3:]}
            except (OSError, subprocess.TimeoutExpired):
                changed = set()
            GLib.idle_add(apply, changed)

        def apply(changed):
            if generation == self._git_generation:
                self._git_changed = changed
                self.reload()
            return GLib.SOURCE_REMOVE
        threading.Thread(target=work, daemon=True).start()

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
        na, nb = sort_key(a.get_display_name()), sort_key(b.get_display_name())
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

    def _animate_items(self):
        """Let the items float in (gtk4-animations.css) as the folder fills. They are
        hidden in the same frame the folder changes ("pre"), and the animation starts
        on the next frame, so nothing flashes at full opacity first. The class is
        removed afterwards so scrolling does not replay it."""
        views = (self.grid, self.list)
        if getattr(self, "_appear_source", 0):
            GLib.source_remove(self._appear_source)
            self._appear_source = 0
        for v in views:
            v.remove_css_class("appear")
            v.add_css_class("pre")

        def start(*_a):
            for v in views:
                v.remove_css_class("pre")
                v.add_css_class("appear")
            self._appear_source = GLib.timeout_add(900, stop)
            return GLib.SOURCE_REMOVE

        def stop():
            self._appear_source = 0
            for v in views:
                v.remove_css_class("appear")
            return GLib.SOURCE_REMOVE
        self.add_tick_callback(lambda *_a: start())

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
        path = gfile.get_path()
        if path and os.path.islink(path) and not os.path.exists(path):
            self.toast(_("{name} points to {target}, which isn't there any more").format(
                name=gfile.get_basename(), target=os.readlink(path)))
            return
        if apps.special_file(path):
            # Gtk.FileLauncher opens it to read, and Files would hang.
            self.toast(_("{name} is a pipe or a device: there is nothing to open").format(
                name=gfile.get_basename()))
            return
        launcher = Gtk.FileLauncher(file=gfile, always_ask=ask)

        def done(l, res):
            try:
                l.launch_finish(res)
            except GLib.Error as err:
                if not err.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED):
                    self.toast(err.message)
        launcher.launch(self, None, done)

    def _on_view_key(self, _ctrl, keyval, _code, state):
        if keyval == Gdk.KEY_space and not state & Gdk.ModifierType.CONTROL_MASK:
            self.quick_look()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not state & (
                Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            self.open_selected()
            return True
        return False

    def quick_look(self):
        """Preview the selected file; arrows in the preview move the selection."""
        from aurora.quicklook import QuickLook
        n = self.model.get_n_items()
        files = [file_of(self.model.get_item(i)) for i in range(n)]
        selected = [i for i in range(n) if self.selection.is_selected(i)]
        if not selected:
            return
        if self.quicklook is not None:
            self.quicklook.close()
            return

        def moved(i):
            self.selection.select_item(i, True)
            view = self.list if self.view_stack.get_visible_child_name() == "list" else self.grid
            view.scroll_to(i, Gtk.ListScrollFlags.FOCUS, None)

        self.quicklook = QuickLook(files, selected[0], parent=self, on_move=moved)
        self.quicklook.connect("close-request", lambda *_: setattr(self, "quicklook", None))
        self.quicklook.present()

    def selection_has_dir(self):
        return any(is_dir(i) for i in self.selected_infos())

    def ask_ai(self, summarize):
        files = [f.get_path() for f in self.selected_files() if f.get_path()]
        if files:
            argv = ["aurora-assistant", "--file", files[0]]
            apps.spawn(argv + (["--summarize"] if summarize else []))

    def send_nearby(self):
        """Hand the selected files to LocalSend, which asks which device to send to."""
        files = [f.get_path() for f in self.selected_files() if f.get_path()]
        if files:
            apps.spawn(["localsend_app", *files])

    def open_with(self):
        files = self.selected_files()
        if files:
            self.launch(files[0], ask=True)

    # ---------------------------------------------------- context menu

    @staticmethod
    def _item_position(view, x, y):
        widget = view.pick(x, y, Gtk.PickFlags.DEFAULT)
        while widget is not None and widget is not view:
            if hasattr(widget, "position"):
                return widget.position
            # The padding of GTK's internal item container belongs to the
            # item too, even when the custom factory child wasn't picked.
            if widget.get_css_name() in ("child", "row", "cell"):
                pending = [widget.get_first_child()]
                while pending:
                    child = pending.pop()
                    if child is None:
                        continue
                    if hasattr(child, "position"):
                        return child.position
                    pending.extend((child.get_first_child(), child.get_next_sibling()))
            widget = widget.get_parent()
        return None

    def _on_background_click(self, gesture, _n, x, y):
        widget = self.view_stack.pick(x, y, Gtk.PickFlags.DEFAULT)
        if widget is not None and (widget.get_ancestor(Gtk.Popover) is not None or
                                   widget.get_ancestor(Gtk.Scrollbar) is not None):
            return
        if gesture.get_current_event_state() & (Gdk.ModifierType.CONTROL_MASK |
                                                Gdk.ModifierType.SHIFT_MASK):
            return
        if self._item_position(self.view_stack, x, y) is None:
            self.selection.unselect_all()

    def _on_context_click(self, gesture, _n, x, y, view):
        widget = view.pick(x, y, Gtk.PickFlags.DEFAULT)
        if widget is not None and widget.get_ancestor(Gtk.Popover) is not None:
            return
        pos = self._item_position(view, x, y)
        if pos is not None and not self.selection.is_selected(pos):
            self.selection.select_item(pos, True)
        elif pos is None:
            self.selection.unselect_all()

        sections = []
        has_sel = pos is not None
        trash = self.in_trash()
        if has_sel:
            s = []
            if trash:
                s.extend([(_("Restore"), "restore"),
                          (_("Delete Permanently"), "delete")])
            else:
                s.extend([(_("Open"), "open"), (_("Open With…"), "open-with"),
                          (_("Quick Look"), "quick-look")])
                if shutil.which("localsend_app"):
                    s.append((_("Send to Nearby Device…"), "send-nearby"))
                from aurora import ai
                if ai.feature("files") and not self.selection_has_dir():
                    sections.append([(_("Summarize with Aurora"), "ai-summarize"),
                                     (_("Ask Aurora About This File…"), "ai-ask")])
            sections.append(s)
            if not trash:
                from aurora.files.archives import is_archive
                paths = [f.get_path() for f in self.selected_files()]
                if paths and all(p and is_archive(p) for p in paths):
                    sections.append([(_("Extract Here"), "extract-here")])
                tools = [(_("Compress…"), "compress")]
                from aurora.files.imagetools import is_image
                if paths and all(p and is_image(p) for p in paths):
                    tools.append((_("Resize Images…"), "resize-images"))
                tools.append((_("What's Using This?"), "file-users"))
                sections.append(tools)
                sections.append([(_("Cut"), "cut"), (_("Copy"), "copy"),
                                 (_("Copy Path"), "copy-path"),
                                 (_("Duplicate"), "duplicate"), (_("Rename…"), "rename")])
                if len(self.selected_files()) > 1:
                    sections.append([(_("Rename Multiple…"), "batch-rename"),
                                     (_("Compare Folders"), "compare-folders")])
                sections.append([(_("SHA-256 Checksums"), "checksums")])
                sections.append([(_("Move to Trash"), "trash")])
            sections.append([(_("Properties"), "properties")])
        elif trash:
            sections.append([(_("Empty Trash"), "empty-trash")])
        else:
            sections.extend([[(_("New Folder…"), "new-folder"),
                              (_("New File…"), "new-file")],
                             [(_("Paste"), "paste")],
                             [(_("Select All"), "select-all"),
                              (_("Open in Terminal"), "terminal-here"),
                              (_("Properties"), "properties")]])
            from aurora import ai
            if ai.enabled() and ai.feature("files"):
                sections.append([(_("Summarize Git Changes…"), "ai-git-summary")])

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1,
                      margin_top=3, margin_bottom=3, margin_start=3, margin_end=3)
        for index, section in enumerate(sections):
            if index:
                box.append(Gtk.Separator())
            for label, name in section:
                action = self.lookup_action(name)
                button = Gtk.Button(label=label, css_classes=["flat", "context-action"],
                                    sensitive=action is not None and action.get_enabled())
                button.get_child().set_xalign(0)
                button.connect("clicked", lambda _b, a=action: (
                    self.context_menu.popdown(), a.activate(None)))
                box.append(button)
        # A long menu (a picture has many actions) scrolls instead of growing past
        # the screen, which the compositor would refuse to show.
        limit = max(240, int((self.get_height() or 600) * 0.85))
        self.context_menu.set_child(Gtk.ScrolledWindow(
            child=box, propagate_natural_height=True, propagate_natural_width=True,
            max_content_height=limit, hscrollbar_policy=Gtk.PolicyType.NEVER))
        self.context_menu.set_position(Gtk.PositionType.TOP if y > view.get_height() / 2
                                       else Gtk.PositionType.BOTTOM)
        # (x, y), or (ok, x, y) with older PyGObject.
        px, py = view.translate_coordinates(self.view_stack, x, y)[-2:]
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(px), int(py), 1, 1
        self.context_menu.set_pointing_to(rect)
        self.context_menu.popup()

    # ------------------------------------------------------ operations

    def toast(self, msg, timeout=3):
        self.toast_overlay.add_toast(Adw.Toast(title=msg, timeout=timeout))

    def batch_rename(self):
        paths = [file.get_path() for file in self.selected_files()]
        if len(paths) < 2 or any(not path for path in paths):
            return
        dialog = Adw.AlertDialog(heading=_("Rename Multiple…"),
                                 body=_("Replace text in the selected names. No file is overwritten."))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        find = Gtk.Entry(placeholder_text=_("Find"))
        replace = Gtk.Entry(placeholder_text=_("Replace with"))
        box.append(find)
        box.append(replace)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("rename", _("Rename"))

        def apply(_dialog, response):
            if response != "rename":
                return
            needle = find.get_text()
            if not needle:
                self.toast(_("Enter text to find"))
                return
            pairs = [(path, os.path.join(os.path.dirname(path),
                      os.path.basename(path).replace(needle, replace.get_text())))
                     for path in paths]
            pairs = [(src, dst) for src, dst in pairs if src != dst]
            targets = [dst for _src, dst in pairs]
            if len(targets) != len(set(targets)) or any(os.path.lexists(dst) for dst in targets):
                self.toast(_("A destination name already exists"))
                return
            done = []
            try:
                for src, dst in pairs:
                    os.rename(src, dst)
                    done.append((src, dst))
            except OSError as err:
                self.toast(str(err))
            if done:
                self.history.record("move", done)
                self._update_history_actions()
                self.reload()
        dialog.connect("response", apply)
        dialog.present(self)

    def checksums(self):
        paths = [f.get_path() for f in self.selected_files()]
        paths = [p for p in paths if p and os.path.isfile(p)]
        if not paths:
            return
        dialog = Adw.AlertDialog(heading=_("SHA-256 Checksums"), body=_("Calculating…"))
        dialog.add_response("close", _("Close"))
        dialog.present(self)

        def work():
            lines = []
            for path in paths:
                if apps.special_file(path):     # a pipe would never end
                    lines.append(f"{os.path.basename(path)}: " + _("not a regular file"))
                    continue
                try:
                    digest = hashlib.sha256()
                    with open(path, "rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    lines.append(f"{digest.hexdigest()}  {os.path.basename(path)}")
                except OSError as err:
                    lines.append(f"{os.path.basename(path)}: {err}")
            GLib.idle_add(show, "\n".join(lines))

        def show(report):
            dialog.set_body("")
            view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR)
            view.get_buffer().set_text(report)
            dialog.set_extra_child(Gtk.ScrolledWindow(child=view,
                                                      min_content_width=600,
                                                      min_content_height=220))
            return GLib.SOURCE_REMOVE
        threading.Thread(target=work, daemon=True).start()

    def compare_folders(self):
        paths = [f.get_path() for f in self.selected_files()]
        if len(paths) != 2 or any(not path or not os.path.isdir(path) for path in paths):
            self.toast(_("Select exactly two folders"))
            return
        apps.spawn(["meld", *paths])

    def summarize_git_changes(self):
        from aurora import ai
        path = self.current.get_path() if self.current else None
        if not path or not ai.enabled():
            return
        dialog = Adw.AlertDialog(heading=_("Summarize Git Changes…"),
                                 body=_("Review the changes before sending them to Aurora AI."))
        view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR)
        view.get_buffer().set_text(_("Loading…"))
        dialog.set_extra_child(Gtk.ScrolledWindow(child=view, min_content_width=600,
                                                  min_content_height=320))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ask", _("Ask Aurora"))
        dialog.set_response_enabled("ask", False)
        dialog.present(self)
        preview = {"text": ""}

        def response(_dialog, choice):
            if choice == "ask" and preview["text"]:
                prompt = "Summarize these Git changes, identify risks and suggest next steps:\n\n" \
                    + preview["text"][:12000]
                apps.spawn(["aurora-assistant", "--ask", prompt])
        dialog.connect("response", response)

        def work():
            parts = []
            for args in (("status", "--short"), ("diff", "--no-ext-diff", "--", "."),
                         ("diff", "--cached", "--no-ext-diff", "--", ".")):
                try:
                    result = subprocess.run(["git", "-C", path, *args], capture_output=True,
                                            text=True, timeout=8)
                    if result.returncode == 0 and result.stdout.strip():
                        parts.append("$ git " + " ".join(args) + "\n" + result.stdout[:12000])
                except (OSError, subprocess.TimeoutExpired):
                    pass
            GLib.idle_add(show, "\n\n".join(parts)[:16000])

        def show(text):
            preview["text"] = text
            view.get_buffer().set_text(text or _("No Git changes found"))
            dialog.set_response_enabled("ask", bool(text))
            dialog.set_body(_("Provider: {name}. Review the text before sending.").format(
                name=ai.provider()))
            return GLib.SOURCE_REMOVE
        threading.Thread(target=work, daemon=True).start()

    def to_clipboard(self, mode):
        files = self.selected_files()
        if not files:
            return
        CLIPBOARD["mode"], CLIPBOARD["files"] = mode, files
        filelist = Gdk.FileList.new_from_list(files)
        self.get_clipboard().set(filelist)
        n = len(files)
        self.toast((ngettext("{n} item cut", "{n} items cut", n) if mode == "move" else
                    ngettext("{n} item copied", "{n} items copied", n)).format(n=n))

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

    def duplicate_selected(self):
        if self.in_trash():
            return
        target = self.current.get_path()
        if target is None:
            return
        paths = [f.get_path() for f in self.selected_files() if f.get_path()]
        self._run_job("copy", paths, target)

    def _run_job(self, kind, paths, target):
        if not paths:
            return
        # Destination names are chosen by Job's worker. Starting two workers
        # at once lets both choose the same free name before either creates it.
        # Queue requests so rapid duplicate/paste gestures remain distinct and
        # their undo history has a deterministic order.
        if self.jobs:
            self._job_queue.append((kind, list(paths), target))
            self._update_history_actions()
            return
        self._start_job(kind, paths, target)

    def _start_job(self, kind, paths, target):
        self._retry_args = None
        self.retry_job_button.set_visible(False)
        self.cancel_job_button.set_visible(True)
        job = Job(kind, paths, target)
        job.activity_id = activities.create(job.label, kind)
        self.progress.set_text(job.label)
        self.progress.set_fraction(0)
        self.progress_revealer.set_reveal_child(True)
        def progress(_j, frac, name):
            self.progress.set_fraction(frac)
            activities.update(job.activity_id, progress=frac, item=name)
        job.connect("progress", progress)

        def finished(_j, error):
            self.jobs.remove(job)
            if job.history_entry is not None:
                self.history.push(job.history_entry)
            self._update_history_actions()
            # Gtk.DirectoryList is monitored: let its incremental update keep
            # the current selection instead of replacing the entire model.
            # A forced reload made a second Ctrl+D lose its source when a tiny
            # first copy completed between the two key presses.
            completed = {source for source, _dest in job.changes}
            remaining = [path for path in paths if path not in completed and os.path.lexists(path)]
            # Retry only what can go differently a second time (a full disk, a
            # drive unplugged), not a cancel or a folder pasted into itself.
            self._retry_args = (kind, remaining, target) if error and remaining and \
                error not in (_("Cancelled"), _("Cannot copy a folder into itself")) else None
            self.retry_job_button.set_visible(self._retry_args is not None)
            self.cancel_job_button.set_visible(bool(self.jobs))
            if not self.jobs and self._retry_args is None and not self._job_queue:
                self.progress_revealer.set_reveal_child(False)
            if error:
                self.toast(error)
            activities.update(job.activity_id, progress=1.0 if not error else
                              self.progress.get_fraction(),
                              status="cancelled" if error == _("Cancelled") else
                              "failed" if error else "finished", error=error)
            if not self.jobs and self._retry_args is None and self._job_queue:
                self._start_job(*self._job_queue.pop(0))
        job.connect("finished", finished)
        self.jobs.append(job)
        self._update_history_actions()
        job.start()

    def _retry_job(self):
        if self._retry_args:
            self._run_job(*self._retry_args)

    def trash_selected(self):
        if self._history_busy:
            return
        if self.in_trash():
            self.delete_selected()
            return
        files = self.selected_files()
        pending = {"count": len(files), "pairs": []}
        if files:
            # Do not let an immediate Ctrl+Z consume the previous history
            # entry while the asynchronous trash callbacks are still pending.
            self._history_busy = True
            self._update_history_actions()
        for f in files:
            f.trash_async(GLib.PRIORITY_DEFAULT, None, self._trash_done, pending)
        if files:
            self.toast(ngettext("{n} item moved to the Trash", "{n} items moved to the Trash",
                                len(files)).format(n=len(files)))

    def _trash_done(self, f, res, pending):
        try:
            original = f.get_path()
            f.trash_finish(res)
            uri = trashed_uri(original) if original else None
            if original and uri:
                pending["pairs"].append((original, uri))
        except GLib.Error as err:
            self.toast(err.message)
        finally:
            pending["count"] -= 1
            if pending["count"] == 0:
                self._history_busy = False
                if pending["pairs"]:
                    self._record_history("trash", pending["pairs"])
                else:
                    self._update_history_actions()

    def delete_selected(self):
        files = self.selected_files()
        if not files:
            return
        dialog = Adw.AlertDialog(
            heading=ngettext("Permanently Delete {n} Item?", "Permanently Delete {n} Items?",
                             len(files)).format(n=len(files)),
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

    # ------------------------------------------------------ archives

    def _run_tool(self, command, done_message):
        """Run a helper (File Roller) in the background, then refresh."""
        import subprocess
        import threading

        def work():
            try:
                ok = subprocess.run(command, timeout=3600).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
            GLib.idle_add(lambda: (self.toast(done_message if ok else _("That didn't work")),
                                   self.reload(), False)[2])
        threading.Thread(target=work, daemon=True).start()

    def compress(self):
        from aurora.files import archives
        paths = [f.get_path() for f in self.selected_files() if f.get_path()]
        if not paths:
            return
        folder = os.path.dirname(paths[0].rstrip("/"))
        dialog = Adw.AlertDialog(heading=_("Compress"),
                                 body=_("{n} items into one archive").format(n=len(paths)))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        entry = Gtk.Entry(text=archives.archive_name(paths), activates_default=True)
        box.append(entry)
        formats = Gtk.DropDown.new_from_strings([_(label) for _s, label in archives.FORMATS])
        box.append(formats)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ok", _("Compress"))
        dialog.set_default_response("ok")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def response(_d, resp):
            name = entry.get_text().strip()
            if resp != "ok" or not name or "/" in name:
                return
            suffix = archives.FORMATS[formats.get_selected()][0]
            target = archives.free_name(folder, name, suffix)
            self.toast(_("Compressing…"))
            self._run_tool(archives.compress_command(paths, target),
                           _("{name} is ready").format(name=os.path.basename(target)))
        dialog.connect("response", response)
        dialog.present(self)
        entry.grab_focus()

    def extract_here(self):
        from aurora.files import archives
        paths = [f.get_path() for f in self.selected_files()
                 if f.get_path() and archives.is_archive(f.get_path())]
        if paths:
            self.toast(_("Extracting…"))
            self._run_tool(archives.extract_command(paths), _("Extracted"))

    def copy_paths(self):
        """The selected files' full paths, one per line (Windows' Copy as path)."""
        paths = [f.get_path() or f.get_uri() for f in self.selected_files()]
        if paths:
            self.get_clipboard().set("\n".join(paths))
            self.toast(ngettext("{n} path copied", "{n} paths copied", len(paths)).format(n=len(paths)))

    def resize_images(self):
        """Smaller copies of pictures (or the pictures themselves), like
        PowerToys' Image Resizer."""
        from aurora.files import imagetools as it
        paths = [f.get_path() for f in self.selected_files()
                 if f.get_path() and it.is_image(f.get_path())]
        if not paths:
            return
        dialog = Adw.AlertDialog(heading=_("Resize Images"),
                                 body=ngettext("{n} picture", "{n} pictures",
                                               len(paths)).format(n=len(paths)))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sizes = Gtk.DropDown.new_from_strings([_(label) for _k, _px, label, _w in it.SIZES])
        sizes.set_selected(1)
        formats = Gtk.DropDown.new_from_strings([_("Keep the format"), "JPEG", "PNG"])
        in_place = Gtk.CheckButton(label=_("Resize the originals instead of making copies"))
        for w in (sizes, formats, in_place):
            box.append(w)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ok", _("Resize"))
        dialog.set_default_response("ok")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def response(_d, resp):
            if resp != "ok":
                return
            _key, longest, _label, short = it.SIZES[sizes.get_selected()]
            fmt = (None, "jpeg", "png")[formats.get_selected()]
            original = in_place.get_active()
            import threading

            def work():
                done, failed = 0, 0
                for path in paths:
                    try:
                        it.resize(path, longest, _(short), fmt, original)
                        done += 1
                    except (GLib.Error, OSError):
                        failed += 1
                GLib.idle_add(lambda: (self.toast(
                    ngettext("{n} picture resized", "{n} pictures resized", done).format(n=done)
                    + (" · " + _("{n} failed").format(n=failed) if failed else "")),
                    self.reload(), False)[2])
            threading.Thread(target=work, daemon=True).start()
        dialog.connect("response", response)
        dialog.present(self)

    def file_users(self):
        """Which programs have this file (or anything in this folder) open, and
        end them: like PowerToys' File Locksmith, for when a file "is in use"."""
        from aurora.files.imagetools import holders
        from aurora import procinfo
        paths = [f.get_path() for f in self.selected_files() if f.get_path()]
        if not paths:
            return
        found = holders(paths)
        dialog = Adw.AlertDialog(heading=_("What's Using This?"))
        if not found:
            dialog.set_body(_("No program of yours has it open."))
            dialog.add_response("ok", _("OK"))
            dialog.present(self)
            return
        dialog.set_body(_("These programs have it open. Close them in the program, or end "
                          "them here (unsaved work in them is lost)."))
        rows = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        for pid, name, what in found:
            row = Adw.ActionRow(title=name,
                                subtitle=f"PID {pid} · " + ", ".join(
                                    os.path.basename(w) for w in what[:3]))
            end = Gtk.Button(label=_("End Task"), valign=Gtk.Align.CENTER,
                             css_classes=["flat"])

            def kill(button, pid=pid):
                procinfo.end([pid])
                button.set_label(_("Ended"))
                button.set_sensitive(False)
            end.connect("clicked", kill)
            row.add_suffix(end)
            rows.append(row)
        dialog.set_extra_child(Gtk.ScrolledWindow(child=rows, propagate_natural_height=True,
                                                  max_content_height=320))
        dialog.add_response("close", _("Close"))
        dialog.add_response("all", _("End All"))
        dialog.set_response_appearance("all", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda _d, r: r == "all" and procinfo.end(
            [pid for pid, _n, _w in found]))
        dialog.present(self)

    # ------------------------------------------------------ network

    def connect_to_server(self):
        """Open a shared folder on another computer: Windows shares (smb://),
        SSH (sftp://), FTP or WebDAV."""
        dialog = Adw.AlertDialog(heading=_("Connect to Server"),
                                 body=_("For example smb://192.168.1.10/Shared for a Windows "
                                        "or NAS shared folder, or sftp://user@server"))
        entry = Gtk.Entry(placeholder_text="smb://", activates_default=True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("ok", _("Connect"))
        dialog.set_default_response("ok")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def response(_d, resp):
            address = entry.get_text().strip()
            if resp != "ok" or not address:
                return
            if "://" not in address:
                address = "smb://" + address.lstrip("\\/").replace("\\", "/")
            self.mount_and_open(Gio.File.new_for_uri(address))
        dialog.connect("response", response)
        dialog.present(self)
        entry.grab_focus()

    def mount_and_open(self, gfile):
        """Open a network location, asking for the password when it needs one."""
        def mounted(f, res):
            try:
                f.mount_enclosing_volume_finish(res)
            except GLib.Error as err:
                if not err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.ALREADY_MOUNTED):
                    self.toast(err.message)
                    return
            self.open_location(f)
        gfile.mount_enclosing_volume(Gio.MountMountFlags.NONE, Gtk.MountOperation.new(self),
                                     None, mounted)

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
        stem = os.path.splitext(initial)[0] if select_stem else initial
        # Adw assigns initial focus after present(); do this in the following
        # main-loop iteration so its select-all does not overwrite our range.
        def focus_entry():
            entry.grab_focus()
            entry.select_region(0, len(stem) if stem else -1)
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(100, focus_entry)

    def rename(self):
        infos = self.selected_infos()
        if len(infos) != 1:
            return
        info = infos[0]

        def do(name):
            try:
                source = file_of(info).get_path()
                renamed = file_of(info).set_display_name(name, None)
                if source and renamed.get_path() and source != renamed.get_path():
                    self._record_history("move", [(source, renamed.get_path())])
            except GLib.Error as err:
                self.toast(err.message)
        self._ask_name(_("Rename"), info.get_display_name(), _("Rename"), do,
                       select_stem=not is_dir(info))

    def new_folder(self):
        if self.current.get_path() is None:
            return

        def do(name):
            try:
                target = self.current.get_child(name)
                target.make_directory(None)
                self._record_history("create-folder", [(None, target.get_path())])
            except GLib.Error as err:
                self.toast(err.message)
        self._ask_name(_("New Folder"), _("Untitled Folder"), _("Create"), do, False)

    def new_file(self):
        if self.current is not None and self.current.get_path() is not None:
            from aurora.files.create import NewItemDialog
            NewItemDialog(self.get_application(), self.current, self,
                          on_created=lambda target, folder: self._record_history(
                              "create-folder" if folder else "create-file",
                              [(None, target.get_path())])).present()

    def terminal_here(self):
        path = self.current.get_path()
        if path:
            argv = (["ptyxis", "--new-window", f"--working-directory={path}"]
                    if GLib.find_program_in_path("ptyxis") else ["x-terminal-emulator"])
            try:
                GLib.spawn_async(argv, working_directory=path,
                                 flags=GLib.SpawnFlags.SEARCH_PATH)
            except GLib.Error as err:
                self.toast(err.message)

    def properties(self):
        files = self.selected_files() or [self.current]
        from aurora.files.properties import PropertiesDialog
        PropertiesDialog(files).present(self)
