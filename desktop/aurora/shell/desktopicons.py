"""Files from ~/Desktop shown on the background, in columns from the top left
(or top right, per the desktop-icons-position setting)."""

import os

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from aurora import settings

MAX_ITEMS = 40


def desktop_dir():
    return GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) \
        or os.path.expanduser("~/Desktop")


def is_live():
    try:
        with open("/proc/cmdline") as f:
            return "boot=live" in f.read().split()
    except OSError:
        return False


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
            elif info.get_icon():
                img.set_from_gicon(info.get_icon())
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

    def _on_press(self, _gesture, n_press, _x, _y):
        # One selected icon at a time; a click on empty desktop clears it.
        parent = self.get_ancestor(DesktopIcons)
        if parent is not None:
            parent.select(self)
        if n_press == 2:
            if self.app is not None:
                from aurora import apps
                apps.launch(self.app)
                return
            launcher = Gtk.FileLauncher(file=self.gfile)
            launcher.launch(self.get_root(), None, None)


class DesktopIcons(Gtk.FlowBox):
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
                         valign=Gtk.Align.START, margin_top=46, margin_start=16, margin_end=16,
                         margin_bottom=100, row_spacing=6, column_spacing=6,
                         max_children_per_line=7, css_classes=["desktop-icons"])
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
        infos.sort(key=lambda i: (i.get_file_type() != Gio.FileType.DIRECTORY,
                                  i.get_display_name().lower()))
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
