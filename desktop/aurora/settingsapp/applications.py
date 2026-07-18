"""Apps (default applications, startup apps), Notifications and Accessibility."""

import os

from gi.repository import Adw, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import N_, _
from aurora.settingsapp.util import Page, switch_row

DEFAULTS = [
    (N_("Web"), "x-scheme-handler/https", ["x-scheme-handler/http", "text/html"]),
    (N_("Mail"), "x-scheme-handler/mailto", []),
    (N_("Files"), "inode/directory", []),
    (N_("Text Editor"), "text/plain", []),
    (N_("Music"), "audio/mpeg", ["audio/ogg", "audio/flac", "audio/x-wav"]),
    (N_("Video"), "video/mp4", ["video/x-matroska", "video/webm"]),
    (N_("Photos"), "image/png", ["image/jpeg", "image/webp", "image/gif"]),
    (N_("PDF"), "application/pdf", []),
]


class Applications(Page):
    page_id = "apps"
    title = _("Apps")
    icon_name = "application-x-executable-symbolic"

    def build(self):
        defaults = self.group(_("Default Apps"))
        for label, mime, extra in DEFAULTS:
            candidates = Gio.AppInfo.get_all_for_type(mime)
            if not candidates:
                continue
            current = Gio.AppInfo.get_default_for_type(mime, False)
            names = [a.get_display_name() for a in candidates]
            idx = next((i for i, a in enumerate(candidates)
                        if current and a.get_id() == current.get_id()), 0)
            row = Adw.ComboRow(title=_(label), model=Gtk.StringList.new(names))
            row.set_selected(idx)

            def changed(r, _p, candidates=candidates, mime=mime, extra=extra):
                app = candidates[r.get_selected()]
                for m in [mime] + extra:
                    try:
                        app.set_as_default_for_type(m)
                    except GLib.Error:
                        pass
            row.connect("notify::selected", changed)
            defaults.add(row)

        self.startup = self.group(_("Startup Apps"),
                                  _("Apps that open automatically when you log in."))
        add = Gtk.MenuButton(icon_name="list-add-symbolic", css_classes=["flat"],
                             tooltip_text=_("Add Startup App"))
        add.set_popover(self._app_picker())
        self.startup.set_header_suffix(add)
        self._rows = []
        self._fill()

    def _autostart_dir(self):
        return os.path.join(GLib.get_user_config_dir(), "autostart")

    def _fill(self):
        for r in self._rows:
            self.startup.remove(r)
        self._rows = []
        d = self._autostart_dir()
        files = sorted(f for f in os.listdir(d) if f.endswith(".desktop")) if os.path.isdir(d) else []
        if not files:
            row = Adw.ActionRow(title=_("No startup apps"))
            self.startup.add(row)
            self._rows.append(row)
        for f in files:
            app = Gio.DesktopAppInfo.new_from_filename(os.path.join(d, f))
            if app is None:
                continue
            row = Adw.ActionRow(title=app.get_display_name(), subtitle=app.get_commandline() or "")
            if app.get_icon():
                row.add_prefix(Gtk.Image(gicon=app.get_icon(), pixel_size=32))
            rm = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat"],
                            valign=Gtk.Align.CENTER, tooltip_text=_("Remove"))
            rm.connect("clicked", lambda _b, p=os.path.join(d, f): (os.remove(p), self._fill()))
            row.add_suffix(rm)
            self.startup.add(row)
            self._rows.append(row)

    def _app_picker(self):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6,
                      margin_bottom=6, margin_start=6, margin_end=6)
        search = Gtk.SearchEntry()
        listbox = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        all_apps = sorted(apps.all_apps(), key=lambda a: a.get_display_name().lower())
        for app in all_apps:
            row = Gtk.ListBoxRow()
            hb = Gtk.Box(spacing=8, margin_top=4, margin_bottom=4, margin_start=6, margin_end=6)
            if app.get_icon():
                hb.append(Gtk.Image(gicon=app.get_icon(), pixel_size=24))
            hb.append(Gtk.Label(label=app.get_display_name(), xalign=0))
            row.set_child(hb)
            row.app = app
            listbox.append(row)
        listbox.set_filter_func(lambda r: search.get_text().lower() in
                                r.app.get_display_name().lower())
        search.connect("search-changed", lambda *_: listbox.invalidate_filter())

        def activated(_lb, row):
            d = self._autostart_dir()
            os.makedirs(d, exist_ok=True)
            with open(row.app.get_filename()) as src, \
                    open(os.path.join(d, os.path.basename(row.app.get_filename())), "w") as dst:
                dst.write(src.read())
            pop.popdown()
            self._fill()
        listbox.set_activate_on_single_click(True)
        listbox.connect("row-activated", activated)
        box.append(search)
        box.append(Gtk.ScrolledWindow(child=listbox, min_content_height=320, min_content_width=280))
        pop.set_child(box)
        return pop


class Notifications(Page):
    page_id = "notifications"
    title = _("Notifications")
    icon_name = "preferences-system-notifications-symbolic"

    def build(self):
        s = settings.get()
        g = self.group()
        if s:
            g.add(switch_row(_("Do Not Disturb"), s.get_boolean("do-not-disturb"),
                             lambda v: s.set_boolean("do-not-disturb", v),
                             subtitle=_("Only urgent notifications will pop up. "
                                        "Everything still appears in the notification center.")))
        info = self.group(_("Where to find them"))
        info.add(Adw.ActionRow(title=_("Click the clock in the top bar"),
                               subtitle=_("to see past notifications and the calendar.")))


class Accessibility(Page):
    page_id = "accessibility"
    title = _("Accessibility")
    icon_name = "preferences-desktop-accessibility-symbolic"

    def build(self):
        iface = settings.interface()
        a11y = settings.get("org.gnome.desktop.a11y.interface")
        seeing = self.group(_("Seeing"))
        if a11y:
            seeing.add(switch_row(_("High contrast"), a11y.get_boolean("high-contrast"),
                                  lambda v: a11y.set_boolean("high-contrast", v)))
        if iface:
            seeing.add(switch_row(_("Large text"), iface.get_double("text-scaling-factor") > 1.1,
                                  lambda v: iface.set_double("text-scaling-factor",
                                                             1.3 if v else 1.0)))
            seeing.add(switch_row(_("Large pointer"), iface.get_int("cursor-size") >= 48,
                                  lambda v: iface.set_int("cursor-size", 48 if v else 24)))
            seeing.add(switch_row(_("Reduce animation"), not iface.get_boolean("enable-animations"),
                                  lambda v: iface.set_boolean("enable-animations", not v)))
        apps_settings = settings.get("org.gnome.desktop.a11y.applications")
        if apps_settings:
            def toggle_reader(v):
                apps_settings.set_boolean("screen-reader-enabled", v)
                if v:
                    apps.spawn(["orca", "--replace"])
                else:
                    apps.spawn(["pkill", "-x", "orca"])
            seeing.add(switch_row(_("Screen reader"),
                                  apps_settings.get_boolean("screen-reader-enabled"),
                                  toggle_reader, subtitle=_("Reads the screen aloud (Orca)")))
