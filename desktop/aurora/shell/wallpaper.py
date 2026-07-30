"""Desktop background, one surface per monitor, with a right-click menu."""

from gi.repository import Gdk, Gio, Gtk

from aurora.i18n import _
from aurora.shell.layer import Layer, LayerWindow

FADE_MS = 2500      # crossfade when the dynamic wallpaper moves to the next phase


class Wallpaper(LayerWindow):
    def __init__(self, app, monitor):
        super().__init__(app, "aurora-wallpaper", layer=Layer.BACKGROUND,
                         anchors=("top", "bottom", "left", "right"), monitor=monitor,
                         exclusive=-1)  # cover the whole output, ignore panels
        self.add_css_class("aurora-wallpaper")
        self.app = app
        # Two pictures in a crossfading stack: the new background fades in.
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                                transition_duration=FADE_MS, hexpand=True, vexpand=True)
        self._pictures = []
        for name in ("a", "b"):
            pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            self._stack.add_named(pic, name)
            self._pictures.append(pic)
        self._current = None
        overlay = Gtk.Overlay(child=self._stack)
        self.set_child(overlay)
        # Files from ~/Desktop, on the primary monitor only.
        if monitor == app.get_primary_monitor():
            from aurora.shell.desktopicons import DesktopIcons
            overlay.add_overlay(DesktopIcons())
        self._menu = self._build_menu(overlay)

        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self._on_right_click)
        overlay.add_controller(click)

        self._handler = app.daycycle.connect("wallpaper-changed", lambda *a: self.reload())
        self.connect("destroy", lambda *a: app.daycycle.disconnect(self._handler))
        self.reload()

    def reload(self):
        path = self.app.daycycle.wallpaper()
        if path == self._current:
            return
        self._current = path
        visible = self._stack.get_visible_child()
        target = self._pictures[1] if visible is self._pictures[0] else self._pictures[0]
        target.set_file(Gio.File.new_for_path(path) if path else None)
        self._stack.set_visible_child(target)

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
