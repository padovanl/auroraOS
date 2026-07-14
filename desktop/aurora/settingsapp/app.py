"""Aurora Settings application window."""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from aurora.i18n import _  # noqa: E402
from aurora.settingsapp.about import About  # noqa: E402
from aurora.settingsapp.appearance import Appearance  # noqa: E402
from aurora.settingsapp.display import Displays  # noqa: E402
from aurora.settingsapp.language import Language  # noqa: E402
from aurora.settingsapp.network import Network  # noqa: E402
from aurora.settingsapp.power import Power  # noqa: E402
from aurora.settingsapp.sound import Sound  # noqa: E402
from aurora.settingsapp.timedate import DateTime  # noqa: E402

PAGES = [Network, Appearance, Displays, Sound, Power, Language, DateTime, About]


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Settings"), default_width=980,
                         default_height=680)
        self.set_size_request(360, 400)
        self._pages = {}

        self.sidebar = Gtk.ListBox(css_classes=["navigation-sidebar"])
        self.sidebar.connect("row-selected", self._on_row)
        for cls in PAGES:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(spacing=12, margin_top=6, margin_bottom=6,
                          margin_start=6, margin_end=6)
            box.append(Gtk.Image(icon_name=cls.icon_name))
            box.append(Gtk.Label(label=cls.title, xalign=0))
            row.set_child(box)
            row.page_cls = cls
            self.sidebar.append(row)

        sidebar_view = Adw.ToolbarView()
        sidebar_view.add_top_bar(Adw.HeaderBar(title_widget=Adw.WindowTitle(title=_("Settings"))))
        sidebar_view.set_content(Gtk.ScrolledWindow(child=self.sidebar,
                                                    hscrollbar_policy=Gtk.PolicyType.NEVER))

        self.content_title = Adw.WindowTitle()
        self.content_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        content_view = Adw.ToolbarView()
        content_view.add_top_bar(Adw.HeaderBar(title_widget=self.content_title))
        self.toast_overlay = Adw.ToastOverlay(child=self.content_stack)
        content_view.set_content(self.toast_overlay)

        self.split = Adw.NavigationSplitView(
            sidebar=Adw.NavigationPage(child=sidebar_view, title=_("Settings")),
            content=Adw.NavigationPage(child=content_view, title=_("Settings")),
            min_sidebar_width=220, max_sidebar_width=260)
        self.set_content(self.split)

        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
        bp.add_setter(self.split, "collapsed", True)
        self.add_breakpoint(bp)

    def _on_row(self, _box, row):
        if row is None:
            return
        cls = row.page_cls
        if cls.page_id not in self._pages:
            page = cls()
            self._pages[cls.page_id] = page
            self.content_stack.add_named(page, cls.page_id)
        self.content_stack.set_visible_child_name(cls.page_id)
        self.content_title.set_title(cls.title)
        self.split.set_show_content(True)

    def show_page(self, page_id):
        for i, cls in enumerate(PAGES):
            if cls.page_id == page_id:
                self.sidebar.select_row(self.sidebar.get_row_at_index(i))
                return
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))


class SettingsApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Settings",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("page", ord("p"), GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             _("Open a specific page"), "PAGE")

    def do_command_line(self, cmdline):
        opts = cmdline.get_options_dict().end().unpack()
        win = self.props.active_window or SettingsWindow(self)
        win.show_page(opts.get("page") or "")
        win.present()
        return 0


def main():
    return SettingsApp().run(sys.argv)
