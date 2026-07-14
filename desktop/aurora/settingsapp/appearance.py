"""Appearance: style, accent color, background, icons, text size."""

import os
import shutil

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

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

ICON_THEMES = [("Papirus-Dark", "Papirus Dark"), ("Papirus", "Papirus"),
               ("Adwaita", "Adwaita")]

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
        style.add(combo_row(_("Color scheme"), [_("Light"), _("Dark")], int(dark),
                            on_change=lambda i: iface and iface.set_string(
                                "color-scheme", "prefer-dark" if i == 1 else "default")))

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

        icon_ids = [t[0] for t in ICON_THEMES]
        cur_icons = iface.get_string("icon-theme") if iface else "Papirus-Dark"
        style.add(combo_row(_("Icons"), [t[1] for t in ICON_THEMES],
                            icon_ids.index(cur_icons) if cur_icons in icon_ids else 0,
                            on_change=lambda i: iface and iface.set_string(
                                "icon-theme", icon_ids[i])))

        large = iface is not None and iface.get_double("text-scaling-factor") > 1.0
        style.add(switch_row(_("Large text"), large,
                             lambda v: iface and iface.set_double(
                                 "text-scaling-factor", 1.25 if v else 1.0)))

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

        clock = self.group(_("Top bar"))
        if aurora:
            clock.add(switch_row(_("24-hour clock"), aurora.get_string("clock-format") == "24h",
                                 lambda v: aurora.set_string("clock-format",
                                                             "24h" if v else "12h")))
            clock.add(switch_row(_("Show seconds"), aurora.get_boolean("clock-show-seconds"),
                                 lambda v: aurora.set_boolean("clock-show-seconds", v)))

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
        for path in find_wallpapers():
            pic = Gtk.Picture(file=Gio.File.new_for_path(path),
                              content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            pic.set_size_request(160, 90)
            frame = Gtk.Frame(child=pic, css_classes=["wallpaper-thumb"])
            child = Gtk.FlowBoxChild(child=frame)
            child.path = path
            child.set_tooltip_text(os.path.basename(path))
            self.flow.append(child)
            if path == current:
                self.flow.select_child(child)

    def _on_wallpaper(self, _flow, child):
        aurora = settings.get()
        if aurora:
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
                aurora.set_string("wallpaper", dest)
            self._load_wallpapers()

        dialog.open(self.get_root(), None, done)
