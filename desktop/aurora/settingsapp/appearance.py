"""Appearance: style, accent color, background, icons, text size."""

import os

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from aurora import look, settings
from aurora.i18n import N_, _
from aurora.settingsapp.util import Page, combo_row, switch_row

ACCENTS = [
    ("blue", "#3584e4", N_("Blue")), ("teal", "#2190a4", N_("Teal")),
    ("green", "#3a944a", N_("Green")), ("yellow", "#c88800", N_("Yellow")),
    ("orange", "#ed5b00", N_("Orange")), ("red", "#e62d42", N_("Red")),
    ("pink", "#d56199", N_("Pink")), ("purple", "#9141ac", N_("Purple")),
    ("slate", "#6f8396", N_("Slate")),
]

ICON_DIRS = ["/usr/share/icons", os.path.expanduser("~/.local/share/icons"),
             os.path.expanduser("~/.icons")]


def _theme_name(path):
    try:
        with open(os.path.join(path, "index.theme")) as f:
            for line in f:
                if line.startswith("Name="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return os.path.basename(path)


def installed_themes(kind):
    """kind='icons' → icon themes, kind='cursors' → cursor themes: [(id, name)]."""
    found = {}
    for base in ICON_DIRS:
        if not os.path.isdir(base):
            continue
        for d in sorted(os.listdir(base)):
            path = os.path.join(base, d)
            if not os.path.isfile(os.path.join(path, "index.theme")) and kind == "icons":
                continue
            has_cursors = os.path.isdir(os.path.join(path, "cursors"))
            if kind == "cursors" and has_cursors:
                found[d] = _theme_name(path)
            elif kind == "icons" and d not in ("hicolor", "default", "locolor") and \
                    any(os.path.isdir(os.path.join(path, sub)) for sub in
                        ("scalable", "48x48", "symbolic", "apps", "places")) :
                found[d] = _theme_name(path)
    return sorted(found.items(), key=lambda kv: kv[1].lower())

class Appearance(Page):
    page_id = "appearance"
    title = _("Appearance")
    icon_name = "preferences-desktop-appearance-symbolic"

    def build(self):
        iface = settings.interface()
        aurora = settings.get()

        from aurora.settingsapp.backgrounds import BackgroundSection
        # First, as the page Windows opens with.
        self.background = BackgroundSection(self)
        if aurora is not None:
            self._lock_screen(aurora)

        style = self.group(_("Style"))
        dark = iface is not None and iface.get_string("color-scheme") == "prefer-dark"
        auto = aurora is not None and aurora.get_boolean("color-scheme-auto")
        style.add(combo_row(_("Color scheme"), [_("Light"), _("Dark"), _("Auto")],
                            2 if auto else int(dark),
                            subtitle=_("Auto switches to dark at sunset and back at sunrise"),
                            on_change=self._set_scheme))

        if aurora is not None:
            density = ["comfortable", "compact"]
            current_density = aurora.get_string("interface-density")
            style.add(combo_row(_("Density"), [_("Comfortable"), _("Compact")],
                                density.index(current_density)
                                if current_density in density else 0,
                                subtitle=_("How much room the top bar, menus and the dock take"),
                                on_change=lambda i: aurora.set_string("interface-density",
                                                                      density[i])))

        if aurora is not None:
            # Each style is a whole icon theme; the app icons beside the row
            # are the ones that change, so the choice can be seen being made.
            styles = list(look.ICON_STYLES)
            labels = {"galaxy": _("Galaxy"), "ribbon": _("Aurora ribbon"),
                      "glass": _("Glass"), "clay": _("Clay"), "bolt": _("Lightning")}
            current_style = aurora.get_string("icon-style")
            icons_row = Adw.ComboRow(
                title=_("Icon style"),
                subtitle=_("How the app icons are drawn, all of them at once"),
                model=Gtk.StringList.new([labels[name] for name in styles]),
                selected=styles.index(current_style) if current_style in styles else 0)
            self._icon_samples = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
            icons_row.add_prefix(self._icon_samples)
            self._show_icon_samples(current_style)
            icons_row.connect("notify::selected", lambda row, _p: self._pick_icon_style(
                aurora, styles[row.get_selected()]))
            style.add(icons_row)

        accent_row = Adw.ActionRow(title=_("Accent color"))
        accent_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        current = iface.get_string("accent-color") if iface else "purple"
        first = None
        for key, color, name in ACCENTS:
            btn = Gtk.CheckButton(tooltip_text=_(name), css_classes=["accent-swatch"])
            btn.set_name(f"accent-{key}")
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            btn.set_active(key == current)
            btn.connect("toggled", lambda b, k=key: b.get_active() and iface
                        and iface.set_string("accent-color", k))
            accent_box.append(btn)
        accent_row.add_suffix(accent_box)
        style.add(accent_row)
        self._install_swatch_css()

        # The accent taken from the picture on screen, Material You style: it
        # follows the background through the day. The nine fixed colors above
        # are greyed out while it is on, since they no longer decide anything.
        if aurora is not None:
            from_wall = switch_row(
                _("Color from the background"),
                aurora.get_boolean("accent-from-wallpaper"),
                subtitle=_("The most vivid color of your background becomes the accent"),
                on_change=lambda v: (aurora.set_boolean("accent-from-wallpaper", v),
                                     accent_row.set_sensitive(not v), look.apply())[0])
            accent_row.set_sensitive(not aurora.get_boolean("accent-from-wallpaper"))
            style.add(from_wall)

        icons = installed_themes("icons") or [("Adwaita", "Adwaita")]
        icon_ids = [t[0] for t in icons]
        cur_icons = iface.get_string("icon-theme") if iface else "Aurora-Dark"
        style.add(combo_row(_("Icons"), [t[1] for t in icons],
                            icon_ids.index(cur_icons) if cur_icons in icon_ids else 0,
                            on_change=lambda i: iface and iface.set_string(
                                "icon-theme", icon_ids[i])))

        cursors = installed_themes("cursors") or [("Adwaita", "Adwaita")]
        cursor_ids = [t[0] for t in cursors]
        cur_cursor = iface.get_string("cursor-theme") if iface else "Adwaita"
        style.add(combo_row(_("Pointer"), [t[1] for t in cursors],
                            cursor_ids.index(cur_cursor) if cur_cursor in cursor_ids else 0,
                            on_change=lambda i: iface and iface.set_string(
                                "cursor-theme", cursor_ids[i])))
        sizes = [24, 32, 48, 64]
        cur_size = iface.get_int("cursor-size") if iface else 24
        style.add(combo_row(_("Pointer size"), [str(x) for x in sizes],
                            sizes.index(cur_size) if cur_size in sizes else 0,
                            on_change=lambda i: iface and iface.set_int("cursor-size", sizes[i])))
        if iface:
            style.add(switch_row(_("Animations"), iface.get_boolean("enable-animations"),
                                 lambda v: iface.set_boolean("enable-animations", v)))
        aurora = settings.get()
        if aurora is not None:
            def set_window_animations(v):
                from aurora import look
                aurora.set_boolean("window-animations", v)
                look.apply()
            style.add(switch_row(_("Window animations"), aurora.get_boolean("window-animations"),
                                 set_window_animations,
                                 subtitle=_("Windows fade in as they open; files and folders "
                                            "float in as a folder opens")))

        fonts = self.group(_("Fonts"))
        if iface:
            for key, title in (("font-name", _("Interface")), ("document-font-name", _("Documents")),
                               ("monospace-font-name", _("Monospace"))):
                fonts.add(self._font_row(iface, key, title))
            row = Adw.ActionRow(title=_("Scaling"))
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.8, 2.0, 0.05)
            scale.set_value(iface.get_double("text-scaling-factor"))
            scale.set_size_request(240, -1)
            scale.set_valign(Gtk.Align.CENTER)
            scale.set_digits(2)
            scale.set_value_pos(Gtk.PositionType.LEFT)
            scale.connect("value-changed", lambda sc: iface.set_double(
                "text-scaling-factor", round(sc.get_value(), 2)))
            row.add_suffix(scale)
            fonts.add(row)
            aa = ["grayscale", "rgba", "none"]
            fonts.add(combo_row(_("Anti-aliasing"), [_("Standard (grayscale)"),
                                                     _("Subpixel (for LCD screens)"), _("None")],
                                aa.index(iface.get_string("font-antialiasing"))
                                if iface.get_string("font-antialiasing") in aa else 0,
                                on_change=lambda i: iface.set_string("font-antialiasing", aa[i])))
            hint = ["slight", "none", "medium", "full"]
            fonts.add(combo_row(_("Hinting"), [_("Slight"), _("None"), _("Medium"), _("Full")],
                                hint.index(iface.get_string("font-hinting"))
                                if iface.get_string("font-hinting") in hint else 0,
                                on_change=lambda i: iface.set_string("font-hinting", hint[i])))

        if aurora:
            night = self.group(_("Night Light"), _("Warmer colors are easier on the eyes at night."))
            night.add(switch_row(_("Night Light"), aurora.get_boolean("night-light"),
                                 lambda v: aurora.set_boolean("night-light", v)))
            from aurora.shell.daycycle import night_light_unsupported
            if night_light_unsupported():
                night.add(Adw.ActionRow(
                    title=_("Not available on this screen"),
                    subtitle=_("The graphics driver doesn't allow color changes (usual in "
                               "a virtual machine)."),
                    css_classes=["warning"]))
            schedules = ["sunset", "manual", "always"]
            current = aurora.get_string("night-light-schedule")
            night.add(combo_row(_("Schedule"), [_("Sunset to Sunrise"), _("Manual"),
                                                _("All the Time")],
                                schedules.index(current) if current in schedules else 0,
                                subtitle=_("Sunset and sunrise follow your time zone"),
                                on_change=lambda i: self._set_schedule(schedules[i])))
            self._hours = []
            for key, title in (("night-light-from", _("From")), ("night-light-to", _("To"))):
                row = Adw.EntryRow(title=title, text=aurora.get_string(key),
                                   show_apply_button=True)
                row.connect("apply", lambda r, k=key: self._set_hour(r, k))
                night.add(row)
                self._hours.append(row)
            self._sync_hours()
            row = Adw.ActionRow(title=_("Color temperature"))
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 2500, 6000, 100)
            scale.set_value(aurora.get_int("night-light-temperature"))
            scale.set_inverted(True)
            scale.set_size_request(240, -1)
            scale.set_valign(Gtk.Align.CENTER)
            scale.set_draw_value(False)
            scale.connect("value-changed", lambda sc: aurora.set_int(
                "night-light-temperature", int(sc.get_value())))
            row.add_suffix(scale)
            night.add(row)

    def _lock_screen(self, aurora):
        """Settings → Appearance → Lock Screen, as on Windows: its picture and
        whether it shows who is signed in."""
        from aurora.lockscreen import MODES
        group = self.group(_("Lock Screen"))
        current = aurora.get_string("lock-background")
        self._lock_pick = Adw.ActionRow(title=_("Picture"))
        self._lock_button = Gtk.Button(valign=Gtk.Align.CENTER)
        self._lock_button.connect("clicked", lambda *_a: self._choose_lock_picture(aurora))
        self._lock_pick.add_suffix(self._lock_button)

        def changed(i):
            aurora.set_string("lock-background", MODES[i])
            if MODES[i] == "picture" and not aurora.get_string("lock-picture"):
                self._choose_lock_picture(aurora)
            self._sync_lock(aurora)
        group.add(combo_row(_("Background"), [_("Same as the desktop"),
                                              _("The desktop's, blurred"), _("A picture")],
                            MODES.index(current) if current in MODES else 0,
                            on_change=changed))
        group.add(self._lock_pick)
        group.add(switch_row(_("Show my name and picture"),
                             aurora.get_boolean("lock-show-account"),
                             lambda v: aurora.set_boolean("lock-show-account", v),
                             subtitle=_("Off: only the time, the date and the password field")))
        self._sync_lock(aurora)

    def _sync_lock(self, aurora):
        own = aurora.get_string("lock-picture")
        self._lock_pick.set_visible(aurora.get_string("lock-background") == "picture")
        self._lock_button.set_label(os.path.basename(own) if own else _("Choose…"))

    def _choose_lock_picture(self, aurora):
        dialog = Gtk.FileDialog(title=_("Lock Screen Picture"))
        images = Gtk.FileFilter(name=_("Images"))
        images.add_mime_type("image/*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(images)
        dialog.set_filters(filters)

        def done(dlg, result):
            try:
                chosen = dlg.open_finish(result)
            except GLib.Error:
                return
            if chosen is not None and chosen.get_path():
                aurora.set_string("lock-picture", chosen.get_path())
                aurora.set_string("lock-background", "picture")
                self._sync_lock(aurora)
        dialog.open(self.get_root(), None, done)

    # --- icon style ---

    SAMPLE_ICONS = ("aurora-logo", "org.aurora.Files", "org.aurora.TaskManager")

    def _show_icon_samples(self, style):
        """Three icons drawn in the style, so the names mean something."""
        theme = look.ICON_STYLES.get(style, "Aurora")
        while (child := self._icon_samples.get_first_child()) is not None:
            self._icon_samples.remove(child)
        for name in self.SAMPLE_ICONS:
            path = None
            for base in ("/usr/share/icons", os.path.join(os.environ.get(
                    "AURORA_PREFIX", "/usr"), "share", "icons")):
                candidate = os.path.join(base, theme, "scalable", "apps", name + ".svg")
                if os.path.exists(candidate):
                    path = candidate
                    break
            image = Gtk.Image(pixel_size=28)
            if path is not None:
                image.set_from_file(path)
            else:
                image.set_from_icon_name(name)
            self._icon_samples.append(image)

    def _pick_icon_style(self, aurora, style):
        aurora.set_string("icon-style", style)
        self._show_icon_samples(style)
        look.apply_icon_style()

    def _set_scheme(self, index):
        aurora, iface = settings.get(), settings.interface()
        if aurora is not None:
            aurora.set_boolean("color-scheme-auto", index == 2)
        if iface is not None and index < 2:
            iface.set_string("color-scheme", "prefer-dark" if index == 1 else "default")

    def _set_schedule(self, value):
        settings.get().set_string("night-light-schedule", value)
        self._sync_hours()

    def _sync_hours(self):
        manual = settings.get().get_string("night-light-schedule") == "manual"
        for row in self._hours:
            row.set_visible(manual)

    def _set_hour(self, row, key):
        text = row.get_text().strip()
        try:
            h, m = (int(x) for x in text.split(":"))
            if not (0 <= h < 24 and 0 <= m < 60):
                raise ValueError
        except ValueError:
            row.add_css_class("error")
            return
        row.remove_css_class("error")
        row.set_text(f"{h:02d}:{m:02d}")
        settings.get().set_string(key, f"{h:02d}:{m:02d}")

    def _font_row(self, iface, key, title):
        row = Adw.ActionRow(title=title)
        dialog = Gtk.FontDialog(title=title)
        button = Gtk.FontDialogButton(dialog=dialog, valign=Gtk.Align.CENTER,
                                      use_font=True, level=Gtk.FontLevel.FONT)
        button.set_font_desc(Pango.FontDescription.from_string(iface.get_string(key)))
        button.connect("notify::font-desc", lambda b, _p: iface.set_string(
            key, b.get_font_desc().to_string()))
        row.add_suffix(button)
        return row

    def _install_swatch_css(self):
        css = "".join(
            f"#accent-{k} radio {{ background: {c}; min-width: 22px; min-height: 22px;"
            f" border-radius: 999px; box-shadow: none; -gtk-icon-source: none; }}"
            f" #accent-{k}:checked radio {{ box-shadow: 0 0 0 2px @window_bg_color,"
            f" 0 0 0 4px {c}; }}"
            for k, c, _n in ACCENTS)
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

