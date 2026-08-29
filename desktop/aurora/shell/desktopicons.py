"""Files from ~/Desktop shown on the background, in columns from the top left
(or top right, per the desktop-icons-position setting)."""

import os
import re
import json

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from aurora import apps, settings
from aurora.files.icons import icon_for
from aurora.files.operations import Job
from aurora.i18n import _

MAX_ITEMS = 40


def desktop_dir():
    return GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) \
        or os.path.expanduser("~/Desktop")


def natural_key(name):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name.casefold())]


def is_live():
    try:
        with open("/proc/cmdline") as f:
            return "boot=live" in f.read().split()
    except OSError:
        return False


def open_file(gfile):
    """Open a desktop file or folder in its default app. (Gtk.FileLauncher goes
    through the portal, which does nothing for the shell's layer surfaces.)"""
    from aurora import apps
    path = gfile.get_path()
    try:
        info = gfile.query_info("standard::content-type,standard::type",
                                Gio.FileQueryInfoFlags.NONE, None)
    except GLib.Error:
        return False
    if info.get_file_type() == Gio.FileType.DIRECTORY:
        return apps.spawn(["aurora-files", path])
    app = Gio.AppInfo.get_default_for_type(info.get_content_type(), False)
    if app is not None:
        return apps.launch(app, files=[path])
    # Nothing registered for it: let Files offer "Open With…".
    return apps.spawn(["aurora-files", os.path.dirname(path)])


class DesktopIcon(Gtk.Button):
    """A file on the desktop. App launchers (.desktop files) show the app's name and
    icon and start the app; everything else opens with its default app."""

    def __init__(self, gfile, info=None, app=None):
        super().__init__(css_classes=["flat", "desktop-icon"])
        self.gfile = gfile
        self.app = app
        if app is None and gfile is not None and gfile.get_basename().endswith(".desktop"):
            self.app = Gio.DesktopAppInfo.new_from_filename(gfile.get_path() or "")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        img = Gtk.Image(pixel_size=56)
        if self.app is not None:
            name = self.app.get_display_name()
            if self.app.get_icon():
                img.set_from_gicon(self.app.get_icon())
        else:
            name = info.get_display_name()
            thumb = info.get_attribute_byte_string("thumbnail::path")
            if thumb:
                img.set_from_file(thumb)
            else:
                img.set_from_gicon(icon_for(info))
        box.append(img)
        box.append(Gtk.Label(label=name, wrap=True, lines=2,
                             ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=12,
                             justify=Gtk.Justification.CENTER, css_classes=["desktop-icon-label"]))
        self.set_child(box)
        self.set_tooltip_text(name)
        # Single click selects (focus), double click opens, like a file manager.
        # Capture phase: the button's own gesture would otherwise claim the
        # presses and the second one of a double click never arrives here.
        click = Gtk.GestureClick(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_press)
        self.add_controller(click)
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY,
                                 propagation_phase=Gtk.PropagationPhase.CAPTURE)
        right.connect("pressed", self._on_right_click)
        self.add_controller(right)
        if self.gfile is not None:
            drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            drag.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(
                Gdk.FileList.new_from_list([self.gfile])))
            self.add_controller(drag)
            drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            drop.connect("drop", self._on_drop)
            self.add_controller(drop)

    def _on_drop(self, _target, value, _x, _y):
        if not isinstance(value, Gdk.FileList) or self.gfile is None:
            return False
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        parent = self.get_ancestor(DesktopIcons)
        target = self.gfile.get_path()
        if not paths or parent is None or target is None or target in paths:
            return False
        if os.path.isdir(target):
            actions = _target.get_current_drop().get_actions()
            parent.transfer(paths, target, move=bool(actions & Gdk.DragAction.MOVE) and
                            not bool(actions & Gdk.DragAction.COPY))
            return True
        if len(paths) == 1 and os.path.dirname(paths[0]) == desktop_dir():
            parent.reorder(os.path.basename(paths[0]), os.path.basename(target))
            return True
        return False

    def _on_press(self, _gesture, n_press, _x, _y):
        if _gesture.get_current_button() != Gdk.BUTTON_PRIMARY:
            return
        # One selected icon at a time; a click on empty desktop clears it.
        parent = self.get_ancestor(DesktopIcons)
        if parent is not None:
            parent.select(self)
        if n_press == 2:
            if self.app is not None:
                from aurora import apps
                apps.launch(self.app)
                return
            open_file(self.gfile)

    def _on_right_click(self, gesture, _n, x, y):
        if self.gfile is not None:
            self.show_menu(x, y)
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def show_menu(self, x, y):
        if self.gfile is None:
            return
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

        row(_("Open"), lambda: open_file(self.gfile))
        row(_("Open in Files"), lambda: apps.spawn(
            ["aurora-files", self.gfile.get_path() if os.path.isdir(self.gfile.get_path())
             else os.path.dirname(self.gfile.get_path())]))
        box.append(Gtk.Separator())
        row(_("Copy"), lambda: self.get_clipboard().set(
            Gdk.FileList.new_from_list([self.gfile])))
        row(_("Rename…"), self._rename)
        row(_("Move to Trash"), self._trash)
        row(_("Properties"), self._properties)
        pop.set_child(box)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.popup()

    def _rename(self):
        dialog = Adw.AlertDialog(heading=_("Rename"))
        entry = Gtk.Entry(text=self.gfile.get_basename(), activates_default=True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("rename", _("Rename"))
        dialog.set_default_response("rename")

        def done(_dialog, response):
            name = entry.get_text().strip()
            if response == "rename" and name and name not in (".", "..") and "/" not in name:
                try:
                    self.gfile.set_display_name(name, None)
                except GLib.Error as err:
                    print(f"aurora: desktop rename failed: {err.message}")
        dialog.connect("response", done)
        dialog.present(self.get_root())
        entry.grab_focus()

    def _trash(self):
        try:
            self.gfile.trash(None)
        except GLib.Error as err:
            print(f"aurora: desktop trash failed: {err.message}")

    def _properties(self):
        from aurora.files.properties import PropertiesDialog
        PropertiesDialog([self.gfile]).present(self.get_root())


class DesktopIcons(Gtk.FlowBox):
    @staticmethod
    def _order_path():
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(base, "aurora", "desktop-icons.json")

    def _load_order(self):
        try:
            with open(self._order_path(), encoding="utf-8") as stream:
                value = json.load(stream)
            return [name for name in value if isinstance(name, str)] if isinstance(value, list) else []
        except (OSError, ValueError):
            return []

    def _save_order(self, order):
        path = self._order_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temporary = path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(order, stream)
            os.replace(temporary, path)
        except OSError as err:
            print(f"aurora: cannot save desktop icon order: {err}")

    def reorder(self, source, target):
        names = []
        child = self.get_first_child()
        while child is not None:
            icon = child.get_child()
            if icon.gfile is not None:
                names.append(icon.gfile.get_basename())
            child = child.get_next_sibling()
        if source not in names or target not in names or source == target:
            return
        names.remove(source)
        names.insert(names.index(target), source)
        self._save_order(names)
        self.reload()

    def reorder_to_end(self, source):
        names = []
        child = self.get_first_child()
        while child is not None:
            icon = child.get_child()
            if icon.gfile is not None:
                names.append(icon.gfile.get_basename())
            child = child.get_next_sibling()
        if source in names:
            names.remove(source)
            names.append(source)
            self._save_order(names)
            self.reload()

    def transfer(self, paths, target, move=False):
        kind = "move" if move else "copy"
        job = Job(kind, paths, target)
        job.connect("finished", lambda _j, error: print(f"aurora: desktop drop: {error}")
                    if error else self.reload())
        job.start()

    def select(self, icon=None):
        child = self.get_first_child()
        while child is not None:
            button = child.get_child() if isinstance(child, Gtk.FlowBoxChild) else child
            if button is not None:
                (button.add_css_class if button is icon else button.remove_css_class)("selected")
            child = child.get_next_sibling()

    def __init__(self):
        super().__init__(selection_mode=Gtk.SelectionMode.NONE,
                         orientation=Gtk.Orientation.VERTICAL,
                         valign=Gtk.Align.FILL, margin_top=46, margin_start=16, margin_end=16,
                         margin_bottom=100, row_spacing=6, column_spacing=6,
                         max_children_per_line=40, css_classes=["desktop-icons"])
        self._dir = Gio.File.new_for_path(desktop_dir())
        self._monitor = None
        try:
            self._monitor = self._dir.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
            self._monitor.connect("changed", lambda *a: GLib.timeout_add(200, self.reload))
        except GLib.Error:
            pass
        s = settings.get()
        if s:
            s.connect("changed::desktop-icons", lambda *a: self.reload())
            s.connect("changed::desktop-icons-position", lambda *a: self.reload())
            for key in ("panel-position", "dock-position", "dock-icon-size", "dock-autohide"):
                s.connect(f"changed::{key}", lambda *a: self._fit_margins())
        self._fit_margins()
        self.reload()

    def _fit_margins(self):
        """Keep the icons clear of the top bar and the dock, wherever they are."""
        s = settings.get()
        if s is None:
            return
        bar = 46
        dock = 0 if s.get_boolean("dock-autohide") else s.get_int("dock-icon-size") + 40
        panel_top = s.get_string("panel-position") != "bottom"
        where = s.get_string("dock-position")
        self.set_margin_top((bar if panel_top else 16) + (dock if where == "top" else 0))
        self.set_margin_bottom(max(16, (0 if panel_top else bar) + (dock if where == "bottom" else 16)))
        self.set_margin_start(16 + (dock if where == "left" else 0))
        self.set_margin_end(16 + (dock if where == "right" else 0))

    def reload(self):
        self.remove_all()
        s = settings.get()
        right = s is not None and s.get_string("desktop-icons-position") == "right"
        self.set_halign(Gtk.Align.END if right else Gtk.Align.START)
        if s is not None and not s.get_boolean("desktop-icons"):
            self.set_visible(False)
            return GLib.SOURCE_REMOVE
        infos = []
        try:
            for info in self._dir.enumerate_children(
                    "standard::*,thumbnail::path", Gio.FileQueryInfoFlags.NONE, None):
                if not info.get_is_hidden() and not info.get_is_backup():
                    infos.append(info)
        except GLib.Error:
            pass
        # Folders first, then by name with numbers in order (file-2 before file-10).
        order = {name: index for index, name in enumerate(self._load_order())}
        infos.sort(key=lambda i: (0, order[i.get_name()]) if i.get_name() in order else
                   (1, i.get_file_type() != Gio.FileType.DIRECTORY,
                    natural_key(i.get_display_name())))
        shown = 0
        # The live system offers the installer on the desktop, like Ubuntu's.
        installer = Gio.DesktopAppInfo.new("aurora-installer.desktop") if is_live() else None
        if installer is not None:
            self.append(DesktopIcon(None, app=installer))
            shown += 1
        for info in infos[:MAX_ITEMS]:
            icon = DesktopIcon(self._dir.get_child(info.get_name()), info)
            self.append(icon)
            shown += 1
        self.set_visible(shown > 0)
        return GLib.SOURCE_REMOVE
