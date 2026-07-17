"""Aurora Welcome: first-run tour."""

import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from aurora import apps, config_path, settings  # noqa: E402
from aurora.i18n import _  # noqa: E402

SHORTCUTS = [
    ("Super", _("Open the app launcher and search")),
    ("Super + Enter", _("Open a terminal")),
    ("Super + E", _("Open Files")),
    ("Super + ← / →", _("Snap a window to the left or right half")),
    ("Super + ↑", _("Maximize the window")),
    ("Alt + Tab", _("Switch between windows")),
    ("Super + 1…4", _("Switch workspace")),
    ("Print / Shift + Print", _("Screenshot of the screen / an area")),
    ("Super + L", _("Lock the screen")),
]


def is_live():
    try:
        with open("/proc/cmdline") as f:
            return "boot=live" in f.read().split()
    except OSError:
        return False


class Welcome(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Welcome"), default_width=760,
                         default_height=560, resizable=False)
        self.carousel = Adw.Carousel(allow_scroll_wheel=False, vexpand=True)
        self.carousel.connect("page-changed", lambda *_: self._update_buttons())
        self.carousel.append(self._page_hello())
        self.carousel.append(self._page_style())
        self.carousel.append(self._page_shortcuts())
        self.carousel.append(self._page_done())

        self.back = Gtk.Button(label=_("Back"))
        self.back.connect("clicked", lambda *_: self._go(-1))
        self.next = Gtk.Button(label=_("Next"), css_classes=["suggested-action"])
        self.next.connect("clicked", lambda *_: self._go(1))

        header = Adw.HeaderBar(show_title=False)
        header.pack_start(self.back)
        header.pack_end(self.next)
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.carousel)
        box.append(Adw.CarouselIndicatorDots(carousel=self.carousel, margin_bottom=12))
        view.set_content(box)
        self.set_content(view)
        self._update_buttons()

    def _status(self, icon, title, description, child=None):
        page = Adw.StatusPage(icon_name=icon, title=title, description=description,
                              hexpand=True, vexpand=True)
        if child:
            page.set_child(child)
        return page

    def _page_hello(self):
        return self._status("aurora-logo", _("Welcome to Aurora OS"),
                            _("A calm, fast desktop built on Debian. "
                              "Let's take a minute to make it yours."))

    def _page_style(self):
        iface = settings.interface()
        box = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        for label, scheme, icon in ((_("Light"), "default", "weather-clear-symbolic"),
                                    (_("Dark"), "prefer-dark", "weather-clear-night-symbolic")):
            btn = Gtk.ToggleButton(css_classes=["card"])
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                            margin_top=18, margin_bottom=18, margin_start=36, margin_end=36)
            inner.append(Gtk.Image(icon_name=icon, pixel_size=48))
            inner.append(Gtk.Label(label=label))
            btn.set_child(inner)
            if iface:
                btn.set_active(iface.get_string("color-scheme") == scheme)
                btn.connect("toggled", lambda b, s=scheme: b.get_active()
                            and iface.set_string("color-scheme", s))
            if box.get_first_child():
                btn.set_group(box.get_first_child())
            box.append(btn)
        return self._status("preferences-desktop-appearance-symbolic", _("Light or Dark?"),
                            _("You can change this, the accent color and the background "
                              "at any time in Settings → Appearance."), box)

    def _page_shortcuts(self):
        group = Adw.PreferencesGroup(margin_start=48, margin_end=48)
        for keys, desc in SHORTCUTS:
            row = Adw.ActionRow(title=desc)
            row.add_suffix(Gtk.Label(label=keys, css_classes=["dim-label", "monospace"]))
            group.add(row)
        scroller = Gtk.ScrolledWindow(child=group, vexpand=True, propagate_natural_height=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24)
        page.append(Gtk.Label(label=_("Handy Shortcuts"), css_classes=["title-1"]))
        page.append(scroller)
        return page

    def _page_done(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, halign=Gtk.Align.CENTER)
        if is_live() and apps.app_by_id("aurora-installer.desktop"):
            install = Gtk.Button(label=_("Install Aurora OS…"),
                                 css_classes=["suggested-action", "pill"])
            install.connect("clicked", lambda *_: (apps.launch(apps.app_by_id("aurora-installer.desktop")),
                                                   self._finish()))
            box.append(install)
        settings_btn = Gtk.Button(label=_("Open Settings"), css_classes=["pill"])
        settings_btn.connect("clicked", lambda *_: (subprocess.Popen(["aurora-settings"]),
                                                    self._finish()))
        box.append(settings_btn)
        return self._status("emblem-ok-symbolic", _("You're All Set"),
                            _("Press the Super key to find apps, files and settings."), box)

    def _go(self, delta):
        pos = int(round(self.carousel.get_position())) + delta
        n = self.carousel.get_n_pages()
        if pos >= n:
            self._finish()
            return
        self.carousel.scroll_to(self.carousel.get_nth_page(max(0, pos)), True)

    def _update_buttons(self):
        pos = int(round(self.carousel.get_position()))
        self.back.set_visible(pos > 0)
        last = pos == self.carousel.get_n_pages() - 1
        self.next.set_label(_("Done") if last else _("Next"))

    def _finish(self):
        path = config_path("welcome-done")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()
        self.close()


class WelcomeApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Welcome")

    def do_activate(self):
        (self.props.active_window or Welcome(self)).present()


def main():
    return WelcomeApp().run(sys.argv)
