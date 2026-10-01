"""Apps (default applications, startup apps), Notifications and Accessibility."""

import os
import xml.etree.ElementTree as ET

from gi.repository import Adw, Gio, GLib, Gtk

from aurora import apps, labwcconf, settings
from aurora.i18n import N_, _
from aurora.settingsapp.util import Page, combo_row, switch_row

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
        if s:
            auto = self.group(_("Automatic Do Not Disturb"),
                              _("Turns on by itself, like Focus Assist. Notifications still "
                                "wait for you in the notification center."))
            auto.add(switch_row(_("On a schedule"), s.get_boolean("dnd-schedule"),
                                lambda v: s.set_boolean("dnd-schedule", v)))
            hours = [f"{h:02d}:00" for h in range(24)]
            auto.add(combo_row(_("From"), hours, s.get_int("dnd-from"),
                               on_change=lambda i: s.set_int("dnd-from", i)))
            auto.add(combo_row(_("To"), hours, s.get_int("dnd-to"),
                               on_change=lambda i: s.set_int("dnd-to", i)))
            auto.add(switch_row(_("While an app is fullscreen"), s.get_boolean("dnd-fullscreen"),
                                lambda v: s.set_boolean("dnd-fullscreen", v),
                                subtitle=_("Games, videos and presentations")))
            auto.add(switch_row(_("While sharing or recording the screen"),
                                s.get_boolean("dnd-sharing"),
                                lambda v: s.set_boolean("dnd-sharing", v)))
        info = self.group(_("Where to find them"))
        info.add(Adw.ActionRow(title=_("Click the clock in the top bar"),
                               subtitle=_("to see past notifications and the calendar.")))
        if not s:
            return

        per_app = self.group(_("App Notifications"),
                             _("Apps appear here after their first notification."))
        seen = sorted(s.get_strv("notifications-seen-apps"), key=str.lower)
        if not seen:
            per_app.add(Adw.ActionRow(title=_("No notifications yet")))
        for name in seen:
            def toggle(on, name=name):
                muted = [a for a in s.get_strv("notifications-muted-apps") if a != name]
                if not on:
                    muted.append(name)
                s.set_strv("notifications-muted-apps", muted)
            per_app.add(switch_row(name, name not in s.get_strv("notifications-muted-apps"),
                                   toggle))

        media = self.group(_("Removable Media"))
        actions = [("notify", _("Show a notification")), ("open", _("Open in Files")),
                   ("nothing", _("Do nothing"))]
        ids = [a for a, _l in actions]
        cur = s.get_string("removable-media-action")
        media.add(combo_row(_("When a drive is connected"), [label for _a, label in actions],
                            ids.index(cur) if cur in ids else 0,
                            on_change=lambda i: s.set_string("removable-media-action", ids[i])))


SCREEN_KEYBOARD_AUTOSTART = os.path.join(GLib.get_user_config_dir(), "autostart",
                                         "aurora-screen-keyboard.desktop")
TEXT_SIZES = [(1.0, N_("Default")), (1.25, N_("Large")), (1.5, N_("Larger"))]
POINTER_SIZES = [(24, N_("Default")), (32, N_("Medium")), (48, N_("Large")),
                 (64, N_("Larger")), (96, N_("Largest"))]
ZOOM_LEVELS = [1.5, 2.0, 3.0, 4.0]
DOUBLE_CLICK = [(250, N_("Fast")), (400, N_("Normal")), (600, N_("Slow")), (900, N_("Slowest"))]
# labwc's magnifier, bound like GNOME's zoom shortcuts.
ZOOM_KEYS = [("W-A-8", "ToggleMagnify"), ("W-A-equal", "ZoomIn"), ("W-A-minus", "ZoomOut")]


def ensure_zoom_keys(cfg):
    """Add the magnifier shortcuts to configs made before they existed."""
    have = {key for key, *_rest in cfg.keybinds()}
    changed = False
    for key, action in ZOOM_KEYS:
        if key not in have:
            kb = ET.SubElement(cfg.node("keyboard"), "keybind", key=key)
            ET.SubElement(kb, "action", name=action)
            changed = True
    return changed


def nearest(options, value):
    return min(range(len(options)), key=lambda i: abs(options[i][0] - value))


class Accessibility(Page):
    page_id = "accessibility"
    title = _("Accessibility")
    icon_name = "preferences-desktop-accessibility-symbolic"

    def build(self):
        iface = settings.interface()
        a11y = settings.get("org.gnome.desktop.a11y.interface")
        cfg = labwcconf.Config()
        if ensure_zoom_keys(cfg):
            cfg.save()

        seeing = self.group(_("Seeing"))
        if a11y:
            seeing.add(switch_row(_("High contrast"), a11y.get_boolean("high-contrast"),
                                  lambda v: self._high_contrast(v, a11y, iface)))
        if iface:
            seeing.add(combo_row(_("Text size"), [_(t[1]) for t in TEXT_SIZES],
                                 nearest(TEXT_SIZES, iface.get_double("text-scaling-factor")),
                                 on_change=lambda i: iface.set_double("text-scaling-factor",
                                                                      TEXT_SIZES[i][0])))
            seeing.add(combo_row(_("Pointer size"), [_(t[1]) for t in POINTER_SIZES],
                                 nearest(POINTER_SIZES, iface.get_int("cursor-size")),
                                 on_change=lambda i: iface.set_int("cursor-size",
                                                                   POINTER_SIZES[i][0])))
            seeing.add(switch_row(_("Reduce animation"), not iface.get_boolean("enable-animations"),
                                  lambda v: self._reduce_motion(v, iface)))
            seeing.add(switch_row(_("Always show scrollbars"),
                                  not iface.get_boolean("overlay-scrolling"),
                                  lambda v: iface.set_boolean("overlay-scrolling", not v)))
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

        zoom = self.group(_("Zoom"), _("Super+Alt+8 turns zoom on and off; Super+Alt+= and "
                                       "Super+Alt+− zoom in and out."))
        level = float(cfg.get("magnifier", "initScale", default="2.0") or 2.0)
        zoom.add(combo_row(_("Magnification"), [f"{z:g}×" for z in ZOOM_LEVELS],
                           min(range(len(ZOOM_LEVELS)), key=lambda i: abs(ZOOM_LEVELS[i] - level)),
                           on_change=lambda i: self._magnifier(initScale=ZOOM_LEVELS[i])))
        full = cfg.get("magnifier", "width", default="-1") == "-1"
        zoom.add(combo_row(_("Zoom area"), [_("Whole screen"), _("Lens around the pointer")],
                           0 if full else 1,
                           on_change=lambda i: self._magnifier(width=-1 if i == 0 else 500,
                                                               height=-1 if i == 0 else 300)))

        hearing = self.group(_("Hearing"))
        sounds = settings.get("org.gnome.desktop.sound")
        if sounds:
            hearing.add(switch_row(_("Alert sounds"), sounds.get_boolean("event-sounds"),
                                   lambda v: sounds.set_boolean("event-sounds", v)))
        hearing.add(Adw.ActionRow(title=_("Captions"),
                                  subtitle=_("Firefox and Videos show subtitles when a video "
                                             "has them; Aurora AI can dictate what you say.")))

        typing = self.group(_("Typing"))
        aurora_s = settings.get()
        if aurora_s is not None:
            from aurora.shell.osk_themes import THEMES as OSK_THEMES
            ids = [k for k, _l in OSK_THEMES]
            cur = aurora_s.get_string("screen-keyboard-theme")
            theme_row = combo_row(_("Keyboard theme"), [_(label) for _k, label in OSK_THEMES],
                                  ids.index(cur) if cur in ids else 0,
                                  on_change=lambda i: (aurora_s.set_string(
                                      "screen-keyboard-theme", ids[i]),
                                      apps.spawn(["aurora-shell", "osk", "show"])))
            typing.add(switch_row(_("Screen keyboard"), aurora_s.get_boolean("screen-keyboard"),
                                  self._screen_keyboard,
                                  subtitle=_("A keyboard on the screen, for touch screens or "
                                             "when a keyboard is hard to use")))
            typing.add(theme_row)
        if iface:
            typing.add(switch_row(_("Blinking text cursor"), iface.get_boolean("cursor-blink"),
                                  lambda v: iface.set_boolean("cursor-blink", v)))
        typing.add(Adw.ActionRow(title=_("Repeat keys"),
                                 subtitle=_("Repeat delay and speed are in Keyboard.")))

        pointing = self.group(_("Pointing & Clicking"))
        mouse = settings.get("org.gnome.desktop.peripherals.mouse")
        cur = int(cfg.get("mouse", "doubleClickTime", default="400") or 400)
        pointing.add(combo_row(_("Double-click delay"), [_(t[1]) for t in DOUBLE_CLICK],
                               nearest(DOUBLE_CLICK, cur),
                               on_change=lambda i: self._double_click(DOUBLE_CLICK[i][0], mouse)))
        speed = Adw.ActionRow(title=_("Pointer speed"), use_markup=False)
        speed.set_subtitle(_("Speed, left-handed use and gestures are in Mouse & Touchpad."))
        pointing.add(speed)

    def _magnifier(self, **values):
        cfg = labwcconf.Config()
        for key, value in values.items():
            cfg.set("magnifier", key, value=value)
        cfg.save()

    def _high_contrast(self, on, a11y, iface):
        from aurora import look
        a11y.set_boolean("high-contrast", on)
        if iface:
            iface.set_string("gtk-theme", "HighContrast" if on else
                             ("adw-gtk3-dark" if look.is_dark() else "adw-gtk3"))
        look.apply()

    def _reduce_motion(self, on, iface):
        from aurora import look
        iface.set_boolean("enable-animations", not on)
        aurora = settings.get()
        if aurora:
            aurora.set_boolean("window-animations", not on)
        look.apply()

    def _double_click(self, ms, mouse):
        cfg = labwcconf.Config()
        cfg.set("mouse", "doubleClickTime", value=ms)
        cfg.save()
        if mouse:
            mouse.set_int("double-click", ms)

    def _screen_keyboard(self, on):
        """Aurora's own on-screen keyboard: shown now and at every login."""
        s = settings.get()
        if s is not None:
            s.set_boolean("screen-keyboard", on)
        # The old wvkbd autostart entry, from before Aurora had its own keyboard.
        try:
            os.remove(SCREEN_KEYBOARD_AUTOSTART)
        except OSError:
            pass
        apps.spawn(["aurora-shell", "osk", "show" if on else "hide"])
