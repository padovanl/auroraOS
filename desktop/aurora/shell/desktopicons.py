"""Files from ~/Desktop on a freely positionable desktop canvas."""

import os
import re
import json

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from aurora import apps, settings
from aurora.files.icons import icon_for
from aurora.files.operations import Job
from aurora.i18n import _, ngettext

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

    def __init__(self, gfile, info=None, app=None, selection_key=None, more=0):
        super().__init__(css_classes=["flat", "desktop-icon"])
        self.gfile = gfile
        self.app = app
        # more > 0: the last spot, "N more…", opening the Desktop folder in Files.
        self.more = more
        # Live-only launchers (notably Install Aurora OS) are real desktop
        # icons even though they do not come from ~/Desktop and therefore have
        # no GFile.  Give every icon a stable key so those launchers can still
        # participate in click/rectangle selection.
        self.selection_key = selection_key or (gfile.get_basename() if gfile else None)
        if app is None and gfile is not None and gfile.get_basename().endswith(".desktop"):
            self.app = Gio.DesktopAppInfo.new_from_filename(gfile.get_path() or "")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        img = Gtk.Image(pixel_size=56)
        if more:
            name = ngettext("{n} more…", "{n} more…", more).format(n=more)
            img.set_from_icon_name("folder-open")
        elif self.app is not None:
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
        if more:
            self.set_tooltip_text(_("Open the Desktop folder to see everything on it"))
        if self.gfile is not None and not more:
            drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            drag.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            drag.connect("prepare", self._drag_files)
            self.add_controller(drag)
            drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            drop.connect("drop", self._on_drop)
            self.add_controller(drop)

    def _drag_files(self, *_args):
        parent = self.get_ancestor(DesktopIcons)
        files = parent.selected_files() if parent and self.has_css_class("selected") else []
        return Gdk.ContentProvider.new_for_value(
            Gdk.FileList.new_from_list(files or [self.gfile]))

    def _on_drop(self, _target, value, x, y):
        if not isinstance(value, Gdk.FileList) or self.gfile is None:
            return False
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        parent = self.get_ancestor(DesktopIcons)
        target = self.gfile.get_path()
        if not paths or parent is None or target is None or target in paths:
            return False
        if os.path.isdir(target):
            from aurora.dnd import is_move
            parent.transfer(paths, target, move=is_move(_target))
            return True
        if len(paths) == 1 and os.path.dirname(paths[0]) == desktop_dir():
            px, py = self.translate_coordinates(parent, x, y)[-2:]
            return parent.place(os.path.basename(paths[0]), px - 40, py - 40)
        return False

    def _on_press(self, _gesture, n_press, _x, _y):
        if _gesture.get_current_button() != Gdk.BUTTON_PRIMARY:
            return
        parent = self.get_ancestor(DesktopIcons)
        if parent is not None:
            state = _gesture.get_current_event_state()
            parent.select(self, extend=bool(state & (Gdk.ModifierType.CONTROL_MASK |
                                                     Gdk.ModifierType.SHIFT_MASK)))
        if n_press == 2:
            if self.app is not None:
                from aurora import apps
                apps.launch(self.app)
                return
            open_file(self.gfile)

    def _on_right_click(self, gesture, _n, x, y):
        if self.gfile is not None and not self.more:
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


class DesktopIcons(Gtk.Fixed):
    CELL_WIDTH = 116
    CELL_HEIGHT = 112

    @staticmethod
    def _order_path():
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(base, "aurora", "desktop-icons.json")

    @classmethod
    def _positions_path(cls):
        return os.path.join(os.path.dirname(cls._order_path()), "desktop-icon-positions.json")

    def _load_positions(self):
        try:
            with open(self._positions_path(), encoding="utf-8") as stream:
                value = json.load(stream)
            if isinstance(value, dict):
                return {key: [int(point[0]), int(point[1])]
                        for key, point in value.items()
                        if isinstance(key, str) and isinstance(point, list) and len(point) == 2
                        and all(isinstance(n, (int, float)) for n in point)}
        except (OSError, ValueError, TypeError, OverflowError):
            pass
        return {}

    def _save_positions(self):
        path = self._positions_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temporary = path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as stream:
                json.dump(self._positions, stream)
            os.replace(temporary, path)
        except OSError as err:
            print(f"aurora: cannot save desktop icon positions: {err}")

    def _bounds(self):
        s = settings.get()
        bar = 46
        # Room for the dock, unless it is always hidden: in the "windows"
        # mode it is on screen whenever the desktop is.
        hidden = s is None or s.get_string("dock-hide") == "always"
        dock = 0 if hidden else s.get_int("dock-icon-size") + 40
        panel_top = s is None or s.get_string("panel-position") != "bottom"
        where = s.get_string("dock-position") if s else "bottom"
        left = 16 + (dock if where == "left" else 0)
        top = (bar if panel_top else 16) + (dock if where == "top" else 0)
        right = max(left, self.get_width() - 16 - (dock if where == "right" else 0)
                    - self.CELL_WIDTH)
        bottom = max(top, self.get_height() - max(16, (0 if panel_top else bar)
                     + (dock if where == "bottom" else 16)) - self.CELL_HEIGHT)
        return left, top, right, bottom

    def _clamp(self, x, y):
        left, top, right, bottom = self._bounds()
        return max(left, min(int(x), right)), max(top, min(int(y), bottom))

    def place(self, name, x, y):
        """Move one desktop file to a drop coordinate and remember the result."""
        icon = self._icons.get(name)
        if icon is None:
            return False
        x, y = self._clamp(x, y)
        self.move(icon, x, y)
        self._positions[name] = [x, y]
        self._save_positions()
        return True

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

    def transfer(self, paths, target, move=False):
        kind = "move" if move else "copy"
        job = Job(kind, paths, target)
        job.connect("finished", lambda _j, error: print(f"aurora: desktop drop: {error}")
                    if error else self.reload())
        job.start()

    def select(self, icon=None, extend=False):
        if not extend:
            self._selected.clear()
        if icon is not None and icon.selection_key is not None:
            name = icon.selection_key
            if extend and name in self._selected:
                self._selected.remove(name)
            else:
                self._selected.add(name)
        self._sync_selection()

    def selected_files(self):
        return [icon.gfile for name, icon in self._icons.items()
                if name in self._selected and icon.gfile is not None and not icon.more]

    def select_rect(self, x1, y1, x2, y2, original=()):
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        self._selected = set(original)
        for name, icon in self._icons.items():
            ok, bounds = icon.compute_bounds(self)
            if ok and bounds.get_x() < right and bounds.get_x() + bounds.get_width() > left \
                    and bounds.get_y() < bottom and bounds.get_y() + bounds.get_height() > top:
                self._selected.add(name)
        self._sync_selection()

    def _sync_selection(self):
        for name, button in self._icons.items():
            (button.add_css_class if name in self._selected else
             button.remove_css_class)("selected")

    def __init__(self):
        super().__init__(hexpand=True, vexpand=True, halign=Gtk.Align.FILL,
                         valign=Gtk.Align.FILL, css_classes=["desktop-icons"])
        self._dir = Gio.File.new_for_path(desktop_dir())
        self._positions = self._load_positions()
        self._icons = {}
        self._selected = set()
        self._last_size = (0, 0)
        self.add_tick_callback(self._watch_size)
        self._monitor = None
        self._reload_source = 0
        try:
            self._monitor = self._dir.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
            self._monitor.connect("changed", lambda *a: self._reload_soon())
        except GLib.Error:
            pass
        s = settings.get()
        if s:
            s.connect("changed::desktop-icons", lambda *a: self.reload())
            s.connect("changed::desktop-icons-position", lambda *a: self.reload())
            for key in ("panel-position", "dock-position", "dock-icon-size", "dock-hide"):
                s.connect(f"changed::{key}", lambda *a: self._fit_margins())
        self._fit_margins()
        self.reload()

    def _reload_soon(self):
        """One reload for a burst of changes: 300 files unpacked on the desktop
        rebuilt it 300 times, leaving it empty for seconds."""
        if self._reload_source:
            GLib.source_remove(self._reload_source)

        def run():
            self._reload_source = 0
            return self.reload()
        self._reload_source = GLib.timeout_add(250, run)

    def _fit_margins(self):
        """Reposition saved icons when panel or dock layout changes."""
        if self.get_width() and self.get_height():
            self.reload()

    def _watch_size(self, *_args):
        size = self.get_width(), self.get_height()
        if size != self._last_size and all(size):
            self._last_size = size
            self.reload()
        return GLib.SOURCE_CONTINUE

    def reload(self):
        child = self.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.remove(child)
            child = next_child
        self._icons = {}
        s = settings.get()
        right = s is not None and s.get_string("desktop-icons-position") == "right"
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
        left, top, right_edge, bottom = self._bounds()
        rows = max(1, (bottom - top) // self.CELL_HEIGHT + 1)
        occupied = set()
        visible_names = {info.get_name() for info in infos[:MAX_ITEMS]}
        for name, point in self._positions.items():
            if name in visible_names:
                px, py = self._clamp(*point)
                occupied.add((px // self.CELL_WIDTH, py // self.CELL_HEIGHT))

        def add_icon(icon, name=None):
            nonlocal shown
            slot = shown
            col, row = divmod(slot, rows)
            default_x = (right_edge - col * self.CELL_WIDTH if right
                         else left + col * self.CELL_WIDTH)
            default_y = top + row * self.CELL_HEIGHT
            x, y = self._clamp(*(self._positions[name] if name in self._positions
                                 else (default_x, default_y)))
            if name not in self._positions:
                while (x // self.CELL_WIDTH, y // self.CELL_HEIGHT) in occupied:
                    slot += 1
                    col, row = divmod(slot, rows)
                    x, y = self._clamp((right_edge - col * self.CELL_WIDTH if right
                                        else left + col * self.CELL_WIDTH),
                                       top + row * self.CELL_HEIGHT)
                    if slot > MAX_ITEMS + 1:
                        break
            occupied.add((x // self.CELL_WIDTH, y // self.CELL_HEIGHT))
            self.put(icon, x, y)
            if name is not None:
                self._icons[name] = icon
            shown += 1

        # The live system offers the installer on the desktop, like Ubuntu's.
        installer = Gio.DesktopAppInfo.new("aurora-installer.desktop") if is_live() else None
        if installer is not None:
            key = "__aurora_installer__"
            add_icon(DesktopIcon(None, app=installer, selection_key=key), key)
        # More than fit: the last spot says how many more, and opens the folder,
        # so nothing saved on the desktop goes missing without a word.
        fits = MAX_ITEMS if len(infos) <= MAX_ITEMS else MAX_ITEMS - 1
        for info in infos[:fits]:
            icon = DesktopIcon(self._dir.get_child(info.get_name()), info)
            add_icon(icon, info.get_name())
        if len(infos) > fits:
            add_icon(DesktopIcon(self._dir, more=len(infos) - fits,
                                 selection_key="__aurora_more__"), "__aurora_more__")
        self._selected.intersection_update(self._icons)
        self._sync_selection()
        self.set_visible(shown > 0)
        return GLib.SOURCE_REMOVE
