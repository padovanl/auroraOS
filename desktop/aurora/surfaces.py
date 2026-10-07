"""Aurora's surface colors in its own apps, following the style live.

Windows, sidebars, header bars and popovers get a faint violet tint of the
aurora instead of libadwaita's grey (data/gtk/gtk4-palette-dark.css and
-light.css). They're applied from inside each app, on the display, and
swapped the moment the style changes: the user's gtk.css is read once when an
app starts, so a palette there stayed dark in an app switched to light.
"""

from gi.repository import Adw, Gdk, Gtk

from aurora import data_path

_provider = None


def _load(manager):
    mode = "dark" if manager.get_dark() else "light"
    try:
        with open(data_path("gtk", f"gtk4-palette-{mode}.css"), encoding="utf-8") as f:
            _provider.load_from_string(f.read())
    except OSError:
        _provider.load_from_string("")


def _install(display):
    global _provider
    if _provider is not None or display is None:
        return
    _provider = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_display(display, _provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    manager = Adw.StyleManager.get_default()
    manager.connect("notify::dark", lambda m, _p: _load(m))
    _load(manager)


def install():
    """Apply the palette once a display is open (now, or when it opens)."""
    manager = Gdk.DisplayManager.get()
    if manager.get_default_display() is not None:
        _install(manager.get_default_display())
    else:
        manager.connect("notify::default-display",
                        lambda m, _p: _install(m.get_default_display()))
