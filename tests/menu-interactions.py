"""GTK popovers: animation completion, reopening, destruction and reduced motion."""
import time
from unittest.mock import patch
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk
from aurora import popovers

Gtk.init()

def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.002)

window = Gtk.Window(default_width=640, default_height=480)
anchor = Gtk.Button(label='Open context menu')
window.set_child(anchor)
menu = popovers.ContextMenu()
menu.set_parent(anchor)
menu.set_child(Gtk.Button(label='A context action'))
closed = []
menu.connect('closed', lambda *a: closed.append(True))
window.present()
pump(.2)
with patch.object(popovers.settings, 'get', lambda: None):
    menu.popup()
    pump(.2)
    assert menu.get_mapped() and menu.has_css_class('opening')
    menu.popdown()
    assert menu.get_mapped() and not menu.get_sensitive() and menu.has_css_class('closing')
    pump(.04)
    assert menu.get_mapped() and closed == []
    menu.popup()
    pump(.2)
    assert menu.get_mapped() and menu.get_sensitive() and closed == []
    menu.popdown()
    pump(.2)
    assert not menu.get_visible() and closed == [True]
    menu.popup()
    pump(.15)
    menu.popdown()  # same GTK dismissal path used by Escape
    pump(.2)
    assert not menu.get_visible() and len(closed) == 2
    menu.popup()
    pump(.15)
    menu.get_surface().hide()  # native outside-click dismissal precedes GTK hide
    pump(.02)
    assert not menu.get_visible() and menu._ghost is not None
    assert menu._ghost.get_mapped() and not menu._ghost.get_autohide()
    pump(.2)
    assert menu._ghost is None
    gtk_settings = menu.get_settings()
    old = gtk_settings.get_property('gtk-enable-animations')
    gtk_settings.set_property('gtk-enable-animations', False)
    menu.popup()
    pump(.1)
    assert not menu.has_css_class('opening')
    menu.popdown()
    assert not menu.get_visible() and menu._close_source == 0
    gtk_settings.set_property('gtk-enable-animations', old)
    menu.popup()
    pump(.15)
    menu.popdown()
    menu.unparent()
    pump(.2)
    assert menu._close_source == 0
    button = Gtk.MenuButton(label='Native menu button')
    window.set_child(button)
    native = popovers.ContextMenu(child=Gtk.Button(label='A native menu action'))
    button.set_popover(native)
    button.set_active(True)
    pump(.2)
    button.set_active(False)
    pump(.04)
    button.set_active(True)
    pump(.2)
    assert native.get_mapped() and native.get_sensitive() and native._close_source == 0
    button.set_active(False)
    pump(.2)
    assert not native.get_visible()
window.destroy()
print('ok: animated dismissal, rapid reopen, outside dismissal, reduced motion, destruction', flush=True)
