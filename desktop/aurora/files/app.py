"""Aurora Files application."""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from aurora import VERSION  # noqa: E402
from aurora.files.window import FilesWindow  # noqa: E402
from aurora.i18n import _  # noqa: E402

CSS = """
.files-grid > child { border-radius: 12px; }
.files-grid > child:selected { background-color: alpha(@accent_bg_color, 0.25); }
popover.aurora-context-menu contents { min-width: 250px; }
"""


class FilesApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Files",
                         flags=Gio.ApplicationFlags.HANDLES_OPEN)

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for name, cb, accels in (
            ("new-window", lambda *_: self.open_window(None), ["<Ctrl>n"]),
            ("about", lambda *_: self._about(), []),
            ("quit", lambda *_: self.quit(), ["<Ctrl>q"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)
        self.set_accels_for_action("window.close", ["<Ctrl>w"])

    def open_window(self, gfile):
        win = FilesWindow(self, gfile)
        win.present()
        return win

    def do_activate(self):
        self.open_window(None)

    def do_open(self, files, _n, _hint):
        for f in files:
            self.open_window(f)

    def _about(self):
        Adw.AboutDialog(application_name=_("Files"), application_icon="system-file-manager",
                        developer_name="Aurora OS", version=VERSION,
                        license_type=Gtk.License.GPL_3_0).present(self.props.active_window)


def main():
    return FilesApp().run(sys.argv)
