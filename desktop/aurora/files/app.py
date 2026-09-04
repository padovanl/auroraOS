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
.files-tab { border-radius: 10px; background: alpha(@window_fg_color, 0.06); }
.files-tab.active-tab { background: alpha(@accent_bg_color, 0.22); }
popover.aurora-context-menu contents {
  min-width: 256px; padding: 7px; border-radius: 8px;
  background: #303030; color: #f4f4f4;
  border: 1px solid #404040; box-shadow: 0 6px 22px alpha(#000000, 0.35);
}
popover.aurora-context-menu separator { background: #454545; margin: 6px 7px; min-height: 1px; }
popover.aurora-context-menu button.model {
  margin: 1px 0; min-height: 36px; padding: 5px 12px;
  border-radius: 5px; color: #f4f4f4;
}
popover.aurora-context-menu button.model:hover,
popover.aurora-context-menu button.model:focus { background: #4b4b4b; }
popover.aurora-context-menu button.model:disabled { color: #999999; }
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
