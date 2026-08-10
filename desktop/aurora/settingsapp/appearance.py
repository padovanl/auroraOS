"""Appearance: style, accent color, background, icons, text size."""

import os
import shutil

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from aurora import settings
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

WALLPAPER_DIRS = ["/usr/share/backgrounds", "~/.local/share/backgrounds", "~/Pictures/Wallpapers"]
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg")


def find_wallpapers():
    found = []
    for d in WALLPAPER_DIRS:
        d = os.path.expanduser(d)
        for root, _dirs, files in os.walk(d):
            for f in sorted(files):
                if f.lower().endswith(IMAGE_EXT):
                    found.append(os.path.join(root, f))
    return found


class Appearance(Page):
    page_id = "appearance"
    title = _("Appearance")
    icon_name = "preferences-desktop-appearance-symbolic"

    def build(self):
        iface = settings.interface()
        aurora = settings.get()

        style = self.group(_("Style"))
        dark = iface is not None and iface.get_string("color-scheme") == "prefer-dark"
        auto = aurora is not None and aurora.get_boolean("color-scheme-auto")
        style.add(combo_row(_("Color scheme"), [_("Light"), _("Dark"), _("Auto")],
                            2 if auto else int(dark),
                            subtitle=_("Auto switches to dark at sunset and back at sunrise"),
                            on_change=self._set_scheme))

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

        bg = self.group(_("Background"))
        add_btn = Gtk.Button(icon_name="list-add-symbolic", css_classes=["flat"],
                             tooltip_text=_("Add Picture…"))
        add_btn.connect("clicked", self._add_picture)
        bg.set_header_suffix(add_btn)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                max_children_per_line=4, min_children_per_line=2,
                                row_spacing=10, column_spacing=10, homogeneous=True)
        self.flow.connect("child-activated", self._on_wallpaper)
        bg.add(self.flow)
        self._load_wallpapers()

        if aurora:
            night = self.group(_("Night Light"), _("Warmer colors are easier on the eyes at night."))
            night.add(switch_row(_("Night Light"), aurora.get_boolean("night-light"),
                                 lambda v: aurora.set_boolean("night-light", v)))
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
            f"#accent-{k} check {{ background: {c}; min-width: 22px; min-height: 22px;"
            f" border-radius: 999px; box-shadow: none; -gtk-icon-source: none; }}"
            f" #accent-{k}:checked check {{ box-shadow: 0 0 0 2px @window_bg_color,"
            f" 0 0 0 4px {c}; }}"
            for k, c, _n in ACCENTS)
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _load_wallpapers(self):
        self.flow.remove_all()
        aurora = settings.get()
        current = aurora.get_string("wallpaper") if aurora else ""
        dynamic = aurora is not None and aurora.get_boolean("wallpaper-dynamic")
        preview = "/usr/share/backgrounds/aurora/aurora-dynamic-dusk.png"
        if os.path.exists(preview):
            pic = Gtk.Picture(file=Gio.File.new_for_path(preview),
                              content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            pic.set_size_request(160, 90)
            badge = Gtk.Label(label=_("Dynamic"), css_classes=["osd", "caption-heading"],
                              halign=Gtk.Align.START, valign=Gtk.Align.END,
                              margin_start=6, margin_bottom=6)
            over = Gtk.Overlay(child=pic)
            over.add_overlay(badge)
            child = Gtk.FlowBoxChild(child=Gtk.Frame(child=over, css_classes=["wallpaper-thumb"]))
            child.path = None
            child.set_tooltip_text(_("Changes with the time of day: dawn, day, dusk and night"))
            self.flow.append(child)
            if dynamic:
                self.flow.select_child(child)
        for path in find_wallpapers():
            if os.path.basename(path).startswith("aurora-dynamic-"):
                continue
            pic = Gtk.Picture(file=Gio.File.new_for_path(path),
                              content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            pic.set_size_request(160, 90)
            frame = Gtk.Frame(child=pic, css_classes=["wallpaper-thumb"])
            child = Gtk.FlowBoxChild(child=frame)
            child.path = path
            child.set_tooltip_text(os.path.basename(path))
            self.flow.append(child)
            if path == current and not dynamic:
                self.flow.select_child(child)

    def _on_wallpaper(self, _flow, child):
        aurora = settings.get()
        if aurora:
            aurora.set_boolean("wallpaper-dynamic", child.path is None)
            if child.path:
                aurora.set_string("wallpaper", child.path)

    def _add_picture(self, *_a):
        dialog = Gtk.FileDialog(title=_("Choose a Background"))
        filt = Gtk.FileFilter(name=_("Images"))
        filt.add_mime_type("image/*")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog.set_filters(store)

        def done(dlg, res):
            try:
                f = dlg.open_finish(res)
            except GLib.Error:
                return
            dest_dir = os.path.expanduser("~/.local/share/backgrounds")
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(f.get_path()))
            shutil.copyfile(f.get_path(), dest)
            aurora = settings.get()
            if aurora:
                aurora.set_boolean("wallpaper-dynamic", False)
                aurora.set_string("wallpaper", dest)
            self._load_wallpapers()

        dialog.open(self.get_root(), None, done)
