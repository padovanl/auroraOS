"""Files from ~/Desktop shown on the background, in columns from the top left
(or top right, per the desktop-icons-position setting)."""

import os

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from aurora import settings

MAX_ITEMS = 40


def desktop_dir():
    return GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) \
        or os.path.expanduser("~/Desktop")


class DesktopIcon(Gtk.Button):
    def __init__(self, gfile, info):
        super().__init__(css_classes=["flat", "desktop-icon"])
        self.gfile = gfile
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        thumb = info.get_attribute_byte_string("thumbnail::path")
        img = Gtk.Image(pixel_size=56)
        if thumb:
            img.set_from_file(thumb)
        elif info.get_icon():
            img.set_from_gicon(info.get_icon())
        box.append(img)
        box.append(Gtk.Label(label=info.get_display_name(), wrap=True, lines=2,
                             ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=12,
                             justify=Gtk.Justification.CENTER, css_classes=["desktop-icon-label"]))
        self.set_child(box)
        self.set_tooltip_text(info.get_display_name())
        # Single click selects (focus), double click opens, like a file manager.
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_press)
        self.add_controller(click)

    def _on_press(self, _gesture, n_press, _x, _y):
        self.grab_focus()
        if n_press == 2:
            launcher = Gtk.FileLauncher(file=self.gfile)
            launcher.launch(self.get_root(), None, None)


class DesktopIcons(Gtk.FlowBox):
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
        for info in infos[:MAX_ITEMS]:
            icon = DesktopIcon(self._dir.get_child(info.get_name()), info)
            self.append(icon)
        self.set_visible(bool(infos))
        return GLib.SOURCE_REMOVE
