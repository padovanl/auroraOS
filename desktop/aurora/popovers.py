"""Context menus with short entrance/exit animations and GTK's native dismissal."""
from gi.repository import Gdk, GLib, Gtk
import cairo
from aurora import settings

_providers = {}
CSS = """
@keyframes aurora-context-in {
  from { opacity: 0; transform: scale(0.96) translateY(-4px); }
  to { opacity: 1; transform: none; }
}
@keyframes aurora-context-out {
  from { opacity: 1; transform: none; }
  to { opacity: 0; transform: scale(0.97) translateY(-3px); }
}
popover.aurora-animated-menu > contents { animation: none; }
popover.aurora-animated-menu.opening > contents {
  animation: aurora-context-in 150ms ease-out both;
}
popover.aurora-animated-menu.closing > contents {
  animation: aurora-context-out 110ms ease-in both;
}
popover.aurora-animated-menu.bottom > contents { transform-origin: top center; }
popover.aurora-animated-menu.top > contents { transform-origin: bottom center; }
"""


class ContextMenu(Gtk.Popover):
    def __init__(self, **kwargs):
        self._close_source = 0
        self._ghost = None
        self._ghost_source = 0
        self._button = None
        self._button_handler = 0
        super().__init__(**kwargs)
        self.connect("notify::parent", self._watch_button)
        self.add_css_class("aurora-animated-menu")
        display = Gdk.Display.get_default()
        if display is not None and display not in _providers:
            provider = Gtk.CssProvider()
            provider.load_from_string(CSS)
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
            _providers[display] = provider

    def _watch_button(self, *_args):
        if self._button is not None:
            self._button.disconnect(self._button_handler)
            self._button = None
        parent = self.get_parent()
        if isinstance(parent, Gtk.MenuButton):
            self._button = parent
            self._button_handler = parent.connect("notify::active", self._button_active)

    def _button_active(self, button, *_args):
        if button.get_active() and self._close_source:
            self.popup()

    def _animate(self):
        preferences = settings.get()
        return (self.get_settings().get_property("gtk-enable-animations") and
                (preferences is None or preferences.get_boolean("window-animations")))

    def popup(self):
        # A closing popover is still visible until its last animation frame.
        # Reopening it must cancel that dismissal even though GTK won't show
        # an already visible widget a second time.
        self._clear_ghost()
        if self._close_source:
            GLib.source_remove(self._close_source)
            self._close_source = 0
            self.set_sensitive(True)
            self.remove_css_class("closing")
            if self._animate():
                self.add_css_class("opening")
        Gtk.Popover.popup(self)

    def _clear_ghost(self):
        if self._ghost_source:
            GLib.source_remove(self._ghost_source)
            self._ghost_source = 0
        if self._ghost is not None:
            self._ghost.popdown()
            if self._ghost.get_parent() is not None:
                self._ghost.unparent()
            self._ghost = None
        return GLib.SOURCE_REMOVE

    def _exit_picture(self):
        # Wayland dismisses an autohiding popup's native surface before GTK
        # hides its widget. Keep only its last painted frame for the fade;
        # the real menu and its input grab are already gone.
        child, parent = self.get_child(), self.get_parent()
        if child is None or parent is None:
            return
        paintable = Gtk.WidgetPaintable.new(child).get_current_image()
        if paintable.get_intrinsic_width() <= 0:
            return
        self._clear_ghost()
        ghost = Gtk.Popover(autohide=False, has_arrow=self.get_has_arrow(),
                            css_classes=self.get_css_classes())
        ghost.remove_css_class("opening")
        ghost.add_css_class("closing")
        ghost.set_can_target(False)
        ghost.set_parent(parent)
        ghost.set_position(self.get_position())
        pointing, rect = self.get_pointing_to()
        if pointing:
            ghost.set_pointing_to(rect)
        ghost.set_offset(*self.get_offset())
        ghost.set_child(Gtk.Picture(paintable=paintable, can_shrink=False))
        self._ghost = ghost
        ghost.popup()
        ghost.get_surface().set_input_region(cairo.Region())
        self._ghost_source = GLib.timeout_add(110, self._clear_ghost)

    def do_show(self):
        self._clear_ghost()
        if self._close_source:
            GLib.source_remove(self._close_source)
            self._close_source = 0
        self.set_sensitive(True)
        self.remove_css_class("closing")
        if self._animate():
            self.add_css_class("opening")
        else:
            self.remove_css_class("opening")
        Gtk.Popover.do_show(self)

    def do_hide(self):
        if self._close_source:
            return
        surface = self.get_surface()
        animate = self._animate()
        if not animate or not self.get_mapped() or surface is None or not surface.get_mapped():
            if animate and self.get_mapped() and surface is not None:
                self._exit_picture()
            Gtk.Popover.do_hide(self)
            return
        self.remove_css_class("opening")
        self.add_css_class("closing")
        self.set_sensitive(False)

        def finish():
            self._close_source = 0
            Gtk.Popover.do_hide(self)
            self.remove_css_class("closing")
            self.set_sensitive(True)
            return GLib.SOURCE_REMOVE
        self._close_source = GLib.timeout_add(110, finish)

    def do_unmap(self):
        if self._close_source:
            GLib.source_remove(self._close_source)
            self._close_source = 0
        Gtk.Popover.do_unmap(self)
