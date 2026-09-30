"""Settings → Appearance → Background, laid out like Windows' Personalize page.

A preview of the desktop on top; "Personalize your background" picks what
fills it: the dynamic Aurora landscape, a picture, a slideshow or a solid
color. For a picture: the ones chosen lately in one row, Browse photos… and
All wallpapers…, a gallery in its own window that only draws the thumbnails
in sight (so a thousand pictures stay quick), with search. Thumbnails are
made in the background and cached.
"""

import hashlib
import os
import shutil
import threading
import uuid

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from aurora import settings
from aurora.i18n import N_, _
from aurora.settingsapp.util import combo_row, switch_row

WALLPAPER_DIRS = ["/usr/share/backgrounds", "~/.local/share/backgrounds", "~/Pictures/Wallpapers"]
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg")
DYNAMIC_PREVIEW = "/usr/share/backgrounds/aurora/aurora-dynamic-dusk.png"
MODES = ("dynamic", "picture", "daily", "slideshow", "color")
MODE_LABELS = (N_("Dynamic (follows the sun)"), N_("Picture"), N_("Picture of the day"),
               N_("Slideshow"), N_("Solid color"))
DAILY_SOURCES = ("bing", "nasa", "wikimedia")
COLORS = ("#1e1b2e", "#2d1b4e", "#0f2a43", "#12372a", "#3b1f2b", "#4a2c0f",
          "#6d28d9", "#be185d", "#0e7490", "#15803d", "#b45309", "#475569")
RECENT = 6
INTERVALS = (15, 60, 360, 1440)


# --- pure helpers (tested) -------------------------------------------------------

def natural_key(path):
    """Sort "photo 2" before "photo 10"."""
    import re
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", os.path.basename(path))]


def find_wallpapers(dirs=None):
    found = []
    for d in dirs or WALLPAPER_DIRS:
        for root, _dirs, files in os.walk(os.path.expanduser(d)):
            for f in sorted(files, key=natural_key):
                if f.lower().endswith(IMAGE_EXT) and not f.startswith("aurora-dynamic-"):
                    found.append(os.path.join(root, f))
    return found


def pretty_name(path):
    return os.path.splitext(os.path.basename(path))[0].replace("-", " ").replace("_", " ")


def remember(recent, path, keep=12):
    """The recent list with path first, once."""
    return ([path] + [p for p in recent if p != path])[:keep]


def recent_row(recent, current, included, count=RECENT):
    """The pictures in the "Recent images" row: the current one, those chosen
    lately, then included ones to fill it."""
    row = []
    for path in [current] + list(recent) + list(included):
        if path and path not in row and os.path.isfile(path):
            row.append(path)
        if len(row) == count:
            break
    return row


def mode_of(s):
    if s is None:
        return "dynamic"
    if s.get_boolean("wallpaper-slideshow"):
        return "slideshow"
    if s.get_string("wallpaper-daily"):
        return "daily"
    if s.get_boolean("wallpaper-dynamic"):
        return "dynamic"
    if os.path.dirname(s.get_string("wallpaper")) == solid_dir():
        return "color"
    return "picture"


def solid_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "aurora", "solid")


def solid_picture(hex_color):
    """A small PNG of one color (the desktop scales it to cover the screen)."""
    path = os.path.join(solid_dir(), f"solid-{hex_color.lstrip('#').lower()}.png")
    if not os.path.exists(path):
        os.makedirs(solid_dir(), exist_ok=True)
        rgba = Gdk.RGBA()
        rgba.parse(hex_color)
        pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 16, 16)
        pix.fill((int(rgba.red * 255) << 24) | (int(rgba.green * 255) << 16)
                 | (int(rgba.blue * 255) << 8) | 0xff)
        pix.savev(path, "png", [], [])
    return path


# --- thumbnails ------------------------------------------------------------------

def _thumb_path(path, width):
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        stamp = 0
    key = hashlib.sha1(f"{path}\0{stamp}\0{width}".encode()).hexdigest()
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aurora", "thumbnails", key + ".png")


_pool = threading.BoundedSemaphore(3)


def load_thumbnail(path, width, callback):
    """Call callback(texture or None) on the main loop with a small copy of the
    picture, made once and kept in ~/.cache/aurora/thumbnails."""
    def work():
        with _pool:
            cached = _thumb_path(path, width)
            texture = None
            try:
                if os.path.exists(cached):
                    texture = Gdk.Texture.new_from_filename(cached)
                else:
                    pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width * 2, -1, True)
                    os.makedirs(os.path.dirname(cached), exist_ok=True)
                    pix.savev(cached, "png", [], [])
                    texture = Gdk.Texture.new_for_pixbuf(pix)
            except (GLib.Error, OSError):
                texture = None
        GLib.idle_add(lambda: (callback(texture), False)[1])
    threading.Thread(target=work, daemon=True).start()


def thumb(path, width=150, height=92, css=("wallpaper-thumb-pic",)):
    pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True, css_classes=list(css))
    pic.set_size_request(width, height)
    load_thumbnail(path, width, lambda t: t is not None and pic.set_paintable(t))
    return pic


# --- the section -----------------------------------------------------------------

class BackgroundSection:
    def __init__(self, page):
        self.page = page
        self.s = settings.get()
        bg = page.group(_("Background"))
        self.group = bg

        # The desktop, in small: the picture, a top bar and a dock.
        self.preview = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True,
                                   css_classes=["background-preview"])
        self.preview.set_size_request(480, 270)
        screen = Gtk.Overlay(child=self.preview, halign=Gtk.Align.CENTER,
                             css_classes=["background-screen"])
        screen.add_overlay(Gtk.Box(css_classes=["preview-topbar"], valign=Gtk.Align.START,
                                   can_target=False))
        screen.add_overlay(Gtk.Box(css_classes=["preview-dock"], valign=Gtk.Align.END,
                                   halign=Gtk.Align.CENTER, can_target=False))
        self.caption = Gtk.Label(css_classes=["dim-label"], margin_top=8, wrap=True,
                                 max_width_chars=60, justify=Gtk.Justification.CENTER)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_top=6, margin_bottom=16)
        top.append(screen)
        top.append(self.caption)
        bg.add(top)

        rows = Adw.PreferencesGroup()
        self.mode_row = combo_row(_("Personalize your background"), [_(m) for m in MODE_LABELS],
                                  MODES.index(mode_of(self.s)), on_change=self._set_mode)
        rows.add(self.mode_row)

        # Picture: the recent ones and the ways to find more.
        self.recent_box = Gtk.Box(spacing=8, margin_top=10, margin_bottom=10)
        picture = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["background-picker"])
        picture.append(self.recent_box)
        buttons = Gtk.Box(spacing=8, margin_bottom=4)
        browse = Gtk.Button(label=_("Browse Photos…"), css_classes=["pill"])
        browse.connect("clicked", lambda *_a: self._browse())
        gallery = Gtk.Button(label=_("All Wallpapers…"), css_classes=["pill", "suggested-action"])
        gallery.connect("clicked", lambda *_a: WallpaperGallery(self).present(page))
        buttons.append(browse)
        buttons.append(gallery)
        picture.append(buttons)
        self.picture_expander = Adw.ExpanderRow(title=_("Recent images"), expanded=True)
        self.picture_expander.add_row(Adw.PreferencesRow(child=picture, activatable=False))
        rows.add(self.picture_expander)

        # Picture of the day: where from.
        self.daily_rows = []
        if self.s is not None:
            from aurora import dailypicture
            current = self.s.get_string("wallpaper-daily") or "bing"
            source = combo_row(_("Picture from"),
                               [_(dailypicture.SOURCES[k]) for k in DAILY_SOURCES],
                               DAILY_SOURCES.index(current) if current in DAILY_SOURCES else 0,
                               subtitle=_("Aurora asks the service for today's picture once "
                                          "a day; nothing else is sent"),
                               on_change=lambda i: self.s.set_string("wallpaper-daily",
                                                                     DAILY_SOURCES[i]))
            self.daily_rows = [source]
            rows.add(source)

        # Slideshow: a folder, how often, in order or not.
        self.slide_rows = []
        if self.s is not None:
            folder = Adw.ActionRow(title=_("Pictures from"))
            self.folder_button = Gtk.Button(valign=Gtk.Align.CENTER)
            self.folder_button.connect("clicked", lambda *_a: self._pick_folder())
            folder.add_suffix(self.folder_button)
            value = self.s.get_int("wallpaper-slideshow-minutes")
            interval = combo_row(_("Change picture every"),
                                 [_("15 minutes"), _("1 hour"), _("6 hours"), _("24 hours")],
                                 INTERVALS.index(value) if value in INTERVALS else 1,
                                 on_change=lambda i: self.s.set_int(
                                     "wallpaper-slideshow-minutes", INTERVALS[i]))
            shuffle = switch_row(_("Shuffle the picture order"),
                                 self.s.get_boolean("wallpaper-slideshow-shuffle"),
                                 lambda v: self.s.set_boolean("wallpaper-slideshow-shuffle", v))
            self.slide_rows = [folder, interval, shuffle]
            for row in self.slide_rows:
                rows.add(row)

        # Solid color.
        swatches = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=12,
                               min_children_per_line=6, column_spacing=6, row_spacing=6,
                               valign=Gtk.Align.CENTER, margin_top=8, margin_bottom=8)
        for color in COLORS:
            b = Gtk.Button(css_classes=["background-swatch"], tooltip_text=color)
            provider = Gtk.CssProvider()
            provider.load_from_string(f"button {{ background: {color}; }}")
            b.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            b.connect("clicked", lambda _b, c=color: self._set_color(c))
            swatches.append(b)
        custom = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False),
                                       valign=Gtk.Align.CENTER, tooltip_text=_("Custom Color"))
        custom.connect("notify::rgba", lambda b, _p: self._set_color(
            "#%02x%02x%02x" % tuple(int(v * 255) for v in (b.get_rgba().red, b.get_rgba().green,
                                                            b.get_rgba().blue))))
        self.color_expander = Adw.ExpanderRow(title=_("Choose a color"), expanded=True)
        self.color_expander.add_row(Adw.PreferencesRow(child=swatches, activatable=False))
        rows.add(self.color_expander)
        self.color_expander.add_suffix(custom)
        page.add(rows)

        if self.s is not None:
            for key in ("wallpaper", "wallpaper-dynamic", "wallpaper-slideshow",
                        "wallpaper-slideshow-folder", "wallpaper-daily"):
                self.s.connect(f"changed::{key}", lambda *_a: self.refresh())
            # The shell downloads today's picture: show it when it arrives.
            from aurora import dailypicture
            os.makedirs(dailypicture.folder(), exist_ok=True)
            self._daily_monitor = Gio.File.new_for_path(dailypicture.folder()).monitor_directory(
                Gio.FileMonitorFlags.NONE, None)
            self._daily_monitor.connect("changed", lambda *_a: mode_of(self.s) == "daily"
                                        and self.refresh())
        self.refresh()

    # --- state ---------------------------------------------------------------------

    def refresh(self):
        mode = mode_of(self.s)
        current = self.s.get_string("wallpaper") if self.s else ""
        shown = DYNAMIC_PREVIEW if mode == "dynamic" else current
        daily = None
        if mode == "daily":
            from aurora import dailypicture
            daily = dailypicture.latest(self.s.get_string("wallpaper-daily"))
            shown = daily["path"] if daily else ""
        if mode == "slideshow":
            link = os.path.join(os.environ.get("XDG_CACHE_HOME")
                                or os.path.expanduser("~/.cache"), "aurora", "wallpaper")
            shown = os.path.realpath(link) if os.path.exists(link) else current
        if shown and os.path.isfile(shown):
            load_thumbnail(shown, 480, lambda t: t is not None and self.preview.set_paintable(t))
        self.caption.set_label({
            "dynamic": _("Dawn, day, dusk and night follow the sun where you are"),
            "picture": pretty_name(current),
            "daily": (" · ".join(x for x in (daily.get("title"), daily.get("credit")) if x)
                      if daily else _("Today's picture is on its way…")),
            "slideshow": _("A new picture every so often"),
            "color": _("A calm, solid color"),
        }[mode])
        self.picture_expander.set_visible(mode == "picture")
        self.color_expander.set_visible(mode == "color")
        for row in self.slide_rows:
            row.set_visible(mode == "slideshow")
        for row in self.daily_rows:
            row.set_visible(mode == "daily")
        if self.slide_rows:
            folder = self.s.get_string("wallpaper-slideshow-folder")
            self.folder_button.set_label(os.path.basename(folder) if folder
                                         else _("Included wallpapers"))
        if self.mode_row.get_selected() != MODES.index(mode):
            self.mode_row.set_selected(MODES.index(mode))
        self._fill_recent(current if mode == "picture" else "")

    def _fill_recent(self, current):
        while (child := self.recent_box.get_first_child()) is not None:
            self.recent_box.remove(child)
        recent = list(self.s.get_strv("wallpaper-recent")) if self.s else []
        included = find_wallpapers(["/usr/share/backgrounds"])
        for path in recent_row(recent, current, included):
            b = Gtk.Button(css_classes=["background-recent"], tooltip_text=pretty_name(path))
            b.set_child(thumb(path, 112, 70))
            if path == current:
                b.add_css_class("current")
            b.connect("clicked", lambda _b, p=path: self.choose(p))
            self.recent_box.append(b)

    # --- choices -------------------------------------------------------------------

    def _set_mode(self, index):
        if self.s is None or MODES[index] == mode_of(self.s):
            return
        mode = MODES[index]
        self.s.set_boolean("wallpaper-slideshow", mode == "slideshow")
        self.s.set_boolean("wallpaper-dynamic", mode == "dynamic")
        self.s.set_string("wallpaper-daily", "bing" if mode == "daily" else "")
        if mode == "picture" and os.path.dirname(self.s.get_string("wallpaper")) == solid_dir():
            recent = [p for p in self.s.get_strv("wallpaper-recent") if os.path.isfile(p)]
            included = find_wallpapers(["/usr/share/backgrounds"])
            pick = (recent or included or [""])[0]
            if pick:
                self.s.set_string("wallpaper", pick)
        if mode == "color":
            self._set_color(COLORS[0])
        self.refresh()

    def choose(self, path):
        if self.s is None:
            return
        self.s.set_boolean("wallpaper-slideshow", False)
        self.s.set_boolean("wallpaper-dynamic", False)
        self.s.set_string("wallpaper-daily", "")
        self.s.set_string("wallpaper", path)
        self.s.set_strv("wallpaper-recent", remember(list(self.s.get_strv("wallpaper-recent")),
                                                     path))

    def _set_color(self, color):
        if self.s is None:
            return
        self.s.set_boolean("wallpaper-slideshow", False)
        self.s.set_boolean("wallpaper-dynamic", False)
        self.s.set_string("wallpaper-daily", "")
        self.s.set_string("wallpaper", solid_picture(color))

    def _browse(self):
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
            path = f.get_path() if f else None
            if not path or not os.path.isfile(path):
                return
            # A copy, so the background stays if the original moves.
            dest_dir = os.path.expanduser("~/.local/share/backgrounds")
            os.makedirs(dest_dir, exist_ok=True)
            name, extension = os.path.splitext(os.path.basename(path))
            dest = os.path.join(dest_dir, f"{name}-{uuid.uuid4().hex[:8]}{extension}")
            try:
                shutil.copyfile(path, dest)
            except OSError as err:
                print(f"aurora: cannot add wallpaper: {err}")
                return
            self.choose(dest)
        dialog.open(self.page.get_root(), None, done)

    def _pick_folder(self):
        dialog = Gtk.FileDialog(title=_("Pictures for the Slideshow"))

        def done(dlg, res):
            try:
                folder = dlg.select_folder_finish(res)
            except GLib.Error:
                return
            if folder is not None and folder.get_path():
                self.s.set_string("wallpaper-slideshow-folder", folder.get_path())
        dialog.select_folder(self.page.get_root(), None, done)


class WallpaperGallery(Adw.Dialog):
    """Every wallpaper as a grid that only makes the thumbnails in sight."""

    def __init__(self, section):
        super().__init__(title=_("All Wallpapers"), content_width=820, content_height=600)
        self.section = section
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.search = Gtk.SearchEntry(placeholder_text=_("Search wallpapers"), width_chars=24)
        header.set_title_widget(self.search)
        toolbar.add_top_bar(header)

        self.store = Gio.ListStore.new(Gtk.StringObject)
        paths = find_wallpapers()
        for path in paths:
            self.store.append(Gtk.StringObject.new(path))
        self.filter = Gtk.CustomFilter.new(self._match)
        filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        selection = Gtk.NoSelection(model=filtered)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        grid = Gtk.GridView(model=selection, factory=factory, max_columns=6, min_columns=2,
                            single_click_activate=True, css_classes=["wallpaper-grid"])
        grid.connect("activate", lambda _g, pos: self._pick(filtered.get_item(pos).get_string()))
        self.search.connect("search-changed",
                            lambda *_a: self.filter.changed(Gtk.FilterChange.DIFFERENT))
        scroller = Gtk.ScrolledWindow(child=grid, vexpand=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        count = Gtk.Label(label=_("{n} pictures").format(n=len(paths)),
                          css_classes=["dim-label", "caption"], margin_top=6, margin_bottom=6)
        box.append(scroller)
        box.append(count)
        toolbar.set_content(box)
        self.set_child(toolbar)

    def _match(self, item):
        q = self.search.get_text().strip().lower()
        return not q or q in pretty_name(item.get_string()).lower()

    @staticmethod
    def _setup(_factory, item):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["wallpaper-cell"])
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True,
                          css_classes=["wallpaper-thumb-pic"])
        pic.set_size_request(168, 104)
        label = Gtk.Label(ellipsize=Pango.EllipsizeMode.END, max_width_chars=20,
                          css_classes=["caption"])
        box.append(pic)
        box.append(label)
        item.set_child(box)

    def _bind(self, _factory, item):
        path = item.get_item().get_string()
        box = item.get_child()
        pic, label = box.get_first_child(), box.get_last_child()
        label.set_label(pretty_name(path))
        pic.set_paintable(None)
        box.path = path

        def loaded(texture):
            # The cell may show another picture by now (cells are reused).
            if getattr(box, "path", None) == path and texture is not None:
                pic.set_paintable(texture)
        load_thumbnail(path, 168, loaded)
        current = self.section.s.get_string("wallpaper") if self.section.s else ""
        (box.add_css_class if path == current else box.remove_css_class)("current")

    def _pick(self, path):
        self.section.choose(path)
        self.close()


__all__ = ["BackgroundSection", "find_wallpapers"]
