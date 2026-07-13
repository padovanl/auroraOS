"""Desktop background, one surface per monitor, with a right-click menu."""

import os

from gi.repository import Gdk, Gio, Gtk

from aurora import data_path, settings
from aurora.i18n import _
from aurora.shell.layer import Layer, LayerWindow

DEFAULT_WALLPAPER = "/usr/share/backgrounds/aurora/aurora-dawn.png"


def current_wallpaper():
    s = settings.get()
    path = s.get_string("wallpaper") if s else ""
    for candidate in (path, DEFAULT_WALLPAPER, data_path("backgrounds", "aurora-dawn.png")):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


class Wallpaper(LayerWindow):
    def __init__(self, app, monitor):
        super().__init__(app, "aurora-wallpaper", layer=Layer.BACKGROUND,
                         anchors=("top", "bottom", "left", "right"), monitor=monitor)
        self.add_css_class("aurora-wallpaper")
        self._picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER,
                                    can_shrink=True, hexpand=True, vexpand=True)
        overlay = Gtk.Overlay(child=self._picture)
        self.set_child(overlay)
        self._menu = self._build_menu(overlay)

        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self._on_right_click)
        overlay.add_controller(click)

        s = settings.get()
        if s:
            s.connect("changed::wallpaper", lambda *a: self.reload())
        self.reload()

    def reload(self):
        path = current_wallpaper()
        if path:
            self._picture.set_file(Gio.File.new_for_path(path))
        else:
            self._picture.set_paintable(None)

    def _build_menu(self, parent):
        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(_("Open Terminal"), "app.open-terminal")
        section.append(_("Open Files"), "app.open-files")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("Change Background…"), "app.settings::appearance")
        section.append(_("Display Settings"), "app.settings::display")
        section.append(_("Settings"), "app.settings::")
        menu.append_section(None, section)
        popover = Gtk.PopoverMenu(menu_model=menu, has_arrow=False,
                                  halign=Gtk.Align.START)
        popover.set_parent(parent)
        return popover

    def _on_right_click(self, gesture, _n, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self._menu.set_pointing_to(rect)
        self._menu.popup()
