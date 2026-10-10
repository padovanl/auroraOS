"""Settings → Appearance → Background, laid out like Windows' Personalize page.

Visible type buttons separate static images, looping videos, daylight series,
daily pictures, slideshows and solid colours. One inline searchable picker
shows included and personal wallpapers for the selected type. Thumbnail
work is bounded, cached and coalesced.
"""

import hashlib
from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import subprocess
import threading
import uuid

from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

from aurora import settings, sun, wallpapers
from aurora.i18n import N_, _
from aurora.settingsapp.util import combo_row, switch_row, toast
from aurora.shell.livingwallpaper import LivingWallpaper, MOTIONS as SUPPORTED_MOTIONS

WALLPAPER_DIRS = ["/usr/share/backgrounds", "~/.local/share/backgrounds", "~/Pictures/Wallpapers"]
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".tif", ".tiff")
MODES = ("picture", "animated", "dynamic", "daily", "slideshow", "color")
MODE_LABELS = (N_("Static image"), N_("Animated wallpaper"), N_("Daylight series"), N_("Picture of the day"),
               N_("Slideshow"), N_("Solid color"))
MODE_DESCRIPTIONS = (N_("A still photo or illustration"), N_("A video that plays in a loop"),
                     N_("Changes at dawn, day, dusk and night"), N_("A new image from the internet each day"),
                     N_("Rotates pictures from a folder"), N_("One uniform colour"))
MODE_ICONS = ("image-x-generic-symbolic", "media-playback-start-symbolic", "weather-clear-symbolic",
              "view-refresh-symbolic", "folder-pictures-symbolic", "applications-graphics-symbolic")
# Legacy effects remain supported by the renderer/schema; the picker offers
# static images and video playback directly instead of mixing these effects.
MOTION_LABELS = {"auto": N_("Automatic (matches the scene)"),
                 "aurora": N_("Aurora over the sky"), "zoom": N_("Slow zoom"),
                 "stars": N_("Twinkling stars"), "clouds": N_("Drifting clouds"),
                 "shimmer": N_("Water reflections"), "off": N_("Still")}
MOTIONS = ("auto", "aurora", "stars", "clouds", "shimmer", "zoom", "off")
assert set(MOTIONS) == set(SUPPORTED_MOTIONS)
DAILY_SOURCES = ("bing", "nasa", "wikimedia")
COLORS = ("#1e1b2e", "#2d1b4e", "#0f2a43", "#12372a", "#3b1f2b", "#4a2c0f",
          "#6d28d9", "#be185d", "#0e7490", "#15803d", "#b45309", "#475569")
RECENT = 6
INTERVALS = (15, 60, 360, 1440)


# --- pure helpers (tested) -------------------------------------------------------

def personal_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "backgrounds")


def import_wallpaper(path):
    """Keep a validated personal copy and a still companion for video files.

    Run off the GTK thread. A failed import leaves no partial gallery entries
    and never touches the original file.
    """
    if not path.lower().endswith(IMAGE_EXT + wallpapers.VIDEO_EXT):
        raise ValueError("Unsupported wallpaper format")
    os.makedirs(personal_dir(), exist_ok=True)
    name, extension = os.path.splitext(os.path.basename(path))
    dest = os.path.join(personal_dir(), f"{name}-{uuid.uuid4().hex[:8]}{extension.lower()}")
    try:
        shutil.copyfile(path, dest)
        if wallpapers.is_video(dest):
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-i", dest, "-map", "0:v:0", "-frames:v", "1",
                            "-vf", "scale=1920:-2:force_original_aspect_ratio=decrease",
                            "-update", "1", wallpapers.poster_path(dest)],
                           check=True, timeout=60, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        # Actually decode the image, including a video's poster, before use.
        GdkPixbuf.Pixbuf.new_from_file_at_scale(wallpapers.poster_path(dest), 64, 64, True)
    except Exception:
        for file in {dest, wallpapers.poster_path(dest)}:
            try:
                os.unlink(file)
            except OSError:
                pass
        raise
    return dest

def natural_key(path):
    """Sort "photo 2" before "photo 10"."""
    import re
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", os.path.basename(path))]


def find_wallpapers(dirs=None, videos=None):
    found = []
    seen = set()
    search_dirs = dirs if dirs is not None else [WALLPAPER_DIRS[0], personal_dir(), WALLPAPER_DIRS[2]]
    # The installed Aurora directory may itself be a symlink. Walk that root
    # explicitly rather than following arbitrary links/cycles in user folders.
    if WALLPAPER_DIRS[0] in search_dirs:
        search_dirs = [wallpapers.BACKGROUNDS] + list(search_dirs)
    for d in search_dirs:
        for root, _dirs, files in os.walk(os.path.expanduser(d)):
            for f in sorted(files, key=natural_key):
                path = os.path.join(root, f)
                companion = os.path.splitext(path)[0]
                is_poster = f.lower().endswith(".png") and any(
                    os.path.isfile(companion + ext) for ext in wallpapers.VIDEO_EXT)
                if f.lower().endswith(IMAGE_EXT + wallpapers.VIDEO_EXT) \
                        and (videos is None or wallpapers.is_video(path) == videos) \
                        and not f.startswith("aurora-dynamic-") and not is_poster:
                    if path not in seen:
                        found.append(path)
                        seen.add(path)
    return found


PHASE_NAMES = {"dawn": N_("Dawn"), "day": N_("Day"), "dusk": N_("Dusk"), "night": N_("Night")}
# The single pictures, as they are called in Settings and the gallery.
SCENE_NAMES = dict(wallpapers.SCENES + wallpapers.STATIC + wallpapers.ANIMATED)


def pretty_name(path):
    name = os.path.splitext(os.path.basename(path))[0]
    parts = name.split("-")
    series = dict(wallpapers.SERIES)
    if len(parts) == 3 and parts[0] == "aurora" and parts[1] in series \
            and parts[2] in PHASE_NAMES:
        return f"{_(series[parts[1]])} · {_(PHASE_NAMES[parts[2]])}"
    if name.startswith("aurora-") and name[len("aurora-"):] in SCENE_NAMES:
        return _(SCENE_NAMES[name[len("aurora-"):]])
    if wallpapers.is_video(path) and name in SCENE_NAMES:
        return _(SCENE_NAMES[name])
    return name.replace("-", " ").replace("_", " ")


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
    return "animated" if wallpapers.is_video(s.get_string("wallpaper")) else "picture"


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


_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="wallpaper-thumbnail")
_pending_thumbs = {}
_thumb_lock = threading.Lock()


def load_thumbnail(path, width, callback):
    """Call callback(texture or None) on the main loop with a small copy of the
    picture, made once and kept in ~/.cache/aurora/thumbnails."""
    cached = _thumb_path(path, width)
    with _thumb_lock:
        if cached in _pending_thumbs:
            _pending_thumbs[cached].append(callback)
            return
        _pending_thumbs[cached] = [callback]

    def delivered(texture):
        with _thumb_lock:
            callbacks = _pending_thumbs.pop(cached, [])
        for done in callbacks:
            done(texture)
        return GLib.SOURCE_REMOVE

    def work():
        texture = None
        try:
            if os.path.exists(cached):
                texture = Gdk.Texture.new_from_filename(cached)
            else:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    wallpapers.poster_path(path), width * 2, -1, True)
                os.makedirs(os.path.dirname(cached), exist_ok=True)
                pix.savev(cached, "png", [], [])
                texture = Gdk.Texture.new_for_pixbuf(pix)
        except (GLib.Error, OSError):
            pass
        GLib.idle_add(delivered, texture)
    _pool.submit(work)


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
        self._importing = False
        self._syncing = False
        self._refresh_source = 0
        self._preview_path = None
        bg = page.group(_("Background"), _("Choose a type, then click a wallpaper to apply it."))
        self.group = bg

        # The desktop, in small: the picture, a top bar and a dock.
        self.preview = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True,
                                   css_classes=["background-preview"])
        self.preview.set_size_request(128, 72)
        screen = Gtk.Overlay(child=self.preview, halign=Gtk.Align.END,
                             css_classes=["background-screen"])
        self.live_preview = LivingWallpaper(activity=self._preview_activity)
        screen.add_overlay(self.live_preview)
        screen.add_overlay(Gtk.Box(css_classes=["preview-topbar"], valign=Gtk.Align.START,
                                   can_target=False))
        screen.add_overlay(Gtk.Box(css_classes=["preview-dock"], valign=Gtk.Align.END,
                                   halign=Gtk.Align.CENTER, can_target=False))
        self.caption = Gtk.Label(wrap=True, xalign=0, max_width_chars=36,
                                 justify=Gtk.Justification.LEFT)
        current = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          hexpand=True, valign=Gtk.Align.CENTER)
        current.append(Gtk.Label(label=_("Current wallpaper"), xalign=0,
                                 css_classes=["dim-label", "caption"]))
        current.append(self.caption)
        self.import_button = Gtk.Button(label=_("Load a File…"), halign=Gtk.Align.START,
                                       tooltip_text=_("Choose a photo or video from your computer"))
        self.import_button.connect("clicked", lambda *_a: self._browse())
        current.append(self.import_button)
        top = Gtk.Box(spacing=16, margin_top=6, margin_bottom=6)
        top.append(current)
        top.append(screen)
        bg.add(top)

        rows = Adw.PreferencesGroup()
        types = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                            min_children_per_line=2, max_children_per_line=3,
                            column_spacing=6, row_spacing=6, homogeneous=True,
                            css_classes=["background-types"])
        self.mode_buttons = {}
        first = None
        for index, (mode, title, description, icon) in enumerate(
                zip(MODES, MODE_LABELS, MODE_DESCRIPTIONS, MODE_ICONS)):
            button = Gtk.ToggleButton(css_classes=["background-mode", "layout-card"],
                                      tooltip_text=_(description))
            if first is not None:
                button.set_group(first)
            else:
                first = button
            heading = Gtk.Box(spacing=6)
            heading.append(Gtk.Image(icon_name=icon, pixel_size=16))
            heading.append(Gtk.Label(label=_(title), xalign=0, wrap=True,
                                     max_width_chars=18,
                                     css_classes=["heading"]))
            button.set_child(heading)
            button.connect("toggled", lambda b, i=index: b.get_active() and self._set_mode(i))
            self.mode_buttons[mode] = button
            types.append(button)
        type_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        type_box.append(types)
        self.mode_description = Gtk.Label(xalign=0, wrap=True,
                                         margin_start=4, margin_bottom=6,
                                         css_classes=["dim-label", "caption"])
        type_box.append(self.mode_description)
        rows.add(Adw.PreferencesRow(child=type_box, activatable=False))

        # Static images stay still. Video playback has its own explicit control.
        if self.s is not None:
            current = self.s.get_string("wallpaper-animation")
            self.video_motion_row = switch_row(
                _("Play animation"), current != "off",
                on_change=lambda active: self.s.set_string(
                    "wallpaper-animation", "auto" if active else "off")
                if not self._syncing and (self.s.get_string("wallpaper-animation") != "off") != active else None)
            self.video_motion_row.set_tooltip_text(
                _("Slow, silent movement. Pauses when the desktop is covered or in power saver."))
            rows.add(self.video_motion_row)

        # One searchable, virtualized picker for bundled and imported files.
        self.picker = WallpaperPicker(self)
        rows.add(self.picker)

        # Dynamic: which series follows the sun.
        self.series_box = Gtk.Box(spacing=10, margin_top=10, margin_bottom=10,
                                  halign=Gtk.Align.START)
        self.series_buttons = {}
        for key, name in wallpapers.SERIES:
            button = Gtk.Button(css_classes=["background-recent"], tooltip_text=_(name))
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.append(thumb(wallpapers.path(key, "dusk"), 150, 84))
            box.append(Gtk.Label(label=_(name), css_classes=["caption"]))
            button.set_child(box)
            button.connect("clicked", lambda _b, k=key: self._set_series(k))
            self.series_box.append(button)
            self.series_buttons[key] = button
        self.series_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.series_row.append(Gtk.Label(label=_("Choose a daylight series"), xalign=0,
                                        css_classes=["heading"]))
        self.series_row.append(self.series_box)
        rows.add(self.series_row)

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
        self.color_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12)
        self.color_box.append(Gtk.Label(label=_("Choose a color"), xalign=0, css_classes=["heading"]))
        colors = Gtk.Box(spacing=8)
        colors.append(swatches)
        colors.append(custom)
        self.color_box.append(colors)
        rows.add(self.color_box)
        page.add(rows)

        if self.s is not None:
            for key in ("wallpaper", "wallpaper-dynamic", "wallpaper-dynamic-series",
                        "wallpaper-slideshow", "wallpaper-slideshow-folder", "wallpaper-daily",
                        "wallpaper-animation"):
                self.s.connect(f"changed::{key}", lambda *_a: self._queue_refresh())
            # The shell downloads today's picture: show it when it arrives.
            from aurora import dailypicture
            os.makedirs(dailypicture.folder(), exist_ok=True)
            self._daily_monitor = Gio.File.new_for_path(dailypicture.folder()).monitor_directory(
                Gio.FileMonitorFlags.NONE, None)
            self._daily_monitor.connect("changed", lambda *_a: mode_of(self.s) == "daily"
                                        and self.refresh())
        self.refresh()

    # --- state ---------------------------------------------------------------------

    def _queue_refresh(self):
        # One choice updates several settings; render only the resulting state.
        if not self._refresh_source:
            self._refresh_source = GLib.idle_add(self.refresh, priority=GLib.PRIORITY_DEFAULT)

    def refresh(self):
        if self._refresh_source:
            GLib.source_remove(self._refresh_source)
            self._refresh_source = 0
        self._syncing = True
        try:
            self._refresh()
        finally:
            self._syncing = False
        return GLib.SOURCE_REMOVE

    def _refresh(self):
        mode = mode_of(self.s)
        current = self.s.get_string("wallpaper") if self.s else ""
        series = wallpapers.chosen_series(self.s)
        shown = wallpapers.path(series, sun.phase()) if mode == "dynamic" else current
        daily = None
        if mode == "daily":
            from aurora import dailypicture
            daily = dailypicture.latest(self.s.get_string("wallpaper-daily"))
            shown = daily["path"] if daily else ""
        if mode == "slideshow":
            link = os.path.join(os.environ.get("XDG_CACHE_HOME")
                                or os.path.expanduser("~/.cache"), "aurora", "wallpaper")
            shown = os.path.realpath(link) if os.path.exists(link) else current
        if shown and os.path.isfile(shown) and shown != self._preview_path:
            self._preview_path = shown

            def loaded(texture):
                if self._preview_path == shown and texture is not None:
                    self.preview.set_paintable(texture)
                    self.live_preview.set_picture(shown)
            load_thumbnail(shown, 480, loaded)
        elif not shown or not os.path.isfile(shown):
            self._preview_path = ""
            self.preview.set_paintable(None)
            self.live_preview.set_picture("")
        if self.s is not None:
            motion = self.s.get_string("wallpaper-animation")
            video_selected = mode == "animated"
            self.video_motion_row.set_visible(video_selected)
            self.video_motion_row.set_active(motion != "off")
        self.caption.set_label({
            "dynamic": pretty_name(shown),
            "picture": pretty_name(current),
            "animated": pretty_name(current),
            "daily": (" · ".join(x for x in (daily.get("title"), daily.get("credit")) if x)
                      if daily else _("Today's picture is on its way…")),
            "slideshow": pretty_name(shown) if shown else _("A new picture every so often"),
            "color": _("A calm, solid color"),
        }[mode])
        self.picker.set_visible(mode in ("picture", "animated"))
        if mode in ("picture", "animated"):
            self.picker.set_kind(mode == "animated")
        self.series_row.set_visible(mode == "dynamic")
        for key, button in self.series_buttons.items():
            (button.add_css_class if key == series else button.remove_css_class)("current")
        self.color_box.set_visible(mode == "color")
        for row in self.slide_rows:
            row.set_visible(mode == "slideshow")
        for row in self.daily_rows:
            row.set_visible(mode == "daily")
        if self.slide_rows:
            folder = self.s.get_string("wallpaper-slideshow-folder")
            self.folder_button.set_label(os.path.basename(folder) if folder
                                         else _("Included wallpapers"))
        self.mode_buttons[mode].set_active(True)
        self.mode_description.set_label(_(MODE_DESCRIPTIONS[MODES.index(mode)]))

    # --- choices -------------------------------------------------------------------

    def _preview_activity(self, running):
        from aurora.shell.livingwallpaper import style
        (self.preview.add_css_class if style() == "zoom" and
         not wallpapers.is_video(self.live_preview.path) else
         self.preview.remove_css_class)("wallpaper-drift")
        (self.preview.remove_css_class if running else
         self.preview.add_css_class)("wallpaper-paused")

    def _set_mode(self, index):
        if self._syncing or self.s is None or MODES[index] == mode_of(self.s):
            return
        mode = MODES[index]
        if mode in ("picture", "animated"):
            video = mode == "animated"
            current = self.s.get_string("wallpaper")
            recent = [p for p in self.s.get_strv("wallpaper-recent") if os.path.isfile(p)
                      and wallpapers.is_video(p) == video and os.path.dirname(p) != solid_dir()]
            included = find_wallpapers(["/usr/share/backgrounds"], videos=video)
            pick = current if current in recent + included else next(iter(recent + included), "")
            if pick:
                self.choose(pick)
            return
        self.s.set_boolean("wallpaper-slideshow", mode == "slideshow")
        self.s.set_boolean("wallpaper-dynamic", mode == "dynamic")
        self.s.set_string("wallpaper-daily", "bing" if mode == "daily" else "")
        self.s.set_string("wallpaper-animation", "off")
        if mode == "color":
            self._set_color(COLORS[0])
        self.refresh()

    def _set_series(self, key):
        if self.s is not None:
            self.s.set_string("wallpaper-dynamic-series", key)
            self.s.set_boolean("wallpaper-slideshow", False)
            self.s.set_string("wallpaper-daily", "")
            self.s.set_string("wallpaper-animation", "off")
            self.s.set_boolean("wallpaper-dynamic", True)

    def choose(self, path):
        if self.s is None:
            return
        self.s.set_string("wallpaper-animation", "auto" if wallpapers.is_video(path) else "off")
        self.s.set_boolean("wallpaper-slideshow", False)
        self.s.set_boolean("wallpaper-dynamic", False)
        self.s.set_string("wallpaper-daily", "")
        self.s.set_string("wallpaper", path)
        self.s.set_strv("wallpaper-recent", remember(list(self.s.get_strv("wallpaper-recent")),
                                                     path))

    def _set_color(self, color):
        if self.s is None:
            return
        self.s.set_string("wallpaper-animation", "off")
        self.s.set_boolean("wallpaper-slideshow", False)
        self.s.set_boolean("wallpaper-dynamic", False)
        self.s.set_string("wallpaper-daily", "")
        self.s.set_string("wallpaper", solid_picture(color))

    def _browse(self):
        if self._importing:
            return
        dialog = Gtk.FileDialog(title=_("Choose a Background"))
        filt = Gtk.FileFilter(name=_("Pictures and videos"))
        for extension in IMAGE_EXT + wallpapers.VIDEO_EXT:
            filt.add_pattern("*" + extension)
            filt.add_pattern("*" + extension.upper())
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
            self._import_personal(path)
        dialog.open(self.page.get_root(), None, done)

    def _import_personal(self, path):
        if self._importing:
            return
        self._importing = True
        self.import_button.set_sensitive(False)
        toast(self.page, _("Adding wallpaper…"))

        def finished(dest):
            self._importing = False
            self.import_button.set_sensitive(True)
            if dest is None:
                toast(self.page, _("Could not add wallpaper. Choose a readable picture or video."))
            else:
                self.picker.search.set_text("")
                self.choose(dest)
                toast(self.page, _("Wallpaper added"))
            return False

        def work():
            try:
                dest = import_wallpaper(path)
            except (OSError, GLib.Error, ValueError, subprocess.SubprocessError) as err:
                print(f"aurora: cannot add wallpaper: {err}")
                dest = None
            GLib.idle_add(finished, dest)
        threading.Thread(target=work, daemon=True).start()

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


class WallpaperPicker(Gtk.Box):
    """The page's single gallery, with a bounded viewport and lazy thumbnails."""

    def __init__(self, section):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                         margin_top=12, margin_bottom=12)
        self.section = section
        self.videos = None
        self._paths = ()
        self.title = Gtk.Label(label=_("Choose a wallpaper"), xalign=0, css_classes=["heading"])
        self.title.set_wrap(True)
        self.search = Gtk.SearchEntry(placeholder_text=_("Search wallpapers"), hexpand=True)
        toolbar = Gtk.Box(spacing=12)
        toolbar.append(self.title)
        toolbar.append(self.search)
        self.append(toolbar)

        self.store = Gio.ListStore.new(Gtk.StringObject)
        self.filter = Gtk.CustomFilter.new(self._match)
        self.filtered = Gtk.FilterListModel(model=self.store, filter=self.filter)
        self.selection = Gtk.SingleSelection(model=self.filtered, autoselect=False, can_unselect=True)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup)
        factory.connect("bind", self._bind)
        self.grid = Gtk.GridView(model=self.selection, factory=factory, max_columns=3, min_columns=2,
                            single_click_activate=True, css_classes=["wallpaper-grid"])
        self.grid.connect("activate", lambda _g, pos: self._pick(self.filtered.get_item(pos).get_string()))
        self.search.connect("search-changed", self._search_changed)
        self.scroller = Gtk.ScrolledWindow(child=self.grid, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                          vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                          css_classes=["wallpaper-picker-scroll"])
        self.scroller.set_size_request(-1, 196)
        self.append(self.scroller)
        self.count = Gtk.Label(xalign=0, css_classes=["dim-label", "caption"])
        self.append(self.count)

    def set_kind(self, videos):
        changed = self.videos != videos
        paths = tuple(find_wallpapers(videos=videos))
        if changed:
            self.videos = videos
            # Leave room for video playback controls in a normal-sized window.
            self.scroller.set_size_request(-1, 140 if videos else 196)
            self.search.set_text("")
            self.title.set_label(_("Choose an animated wallpaper") if videos else _("Choose a static wallpaper"))
        if changed or paths != self._paths:
            self._paths = paths
            self.store.remove_all()
            for path in paths:
                self.store.append(Gtk.StringObject.new(path))
        self.sync_selection()

    def _search_changed(self, *_args):
        self.filter.changed(Gtk.FilterChange.DIFFERENT)
        self.sync_selection()

    def sync_selection(self):
        current = self.section.s.get_string("wallpaper") if self.section.s else ""
        selected = Gtk.INVALID_LIST_POSITION
        for index in range(self.filtered.get_n_items()):
            if self.filtered.get_item(index).get_string() == current:
                selected = index
                break
        changed = self.selection.get_selected() != selected
        self.selection.set_selected(selected)
        if changed and selected != Gtk.INVALID_LIST_POSITION:
            self.grid.scroll_to(selected, Gtk.ListScrollFlags.NONE, None)
        count = self.filtered.get_n_items()
        self.count.set_label(_("{n} wallpapers").format(n=count) if count else _("No wallpapers found"))

    def _match(self, item):
        q = self.search.get_text().strip().lower()
        return not q or q in pretty_name(item.get_string()).lower()

    @staticmethod
    def _setup(_factory, item):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["wallpaper-cell"])
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True,
                          css_classes=["wallpaper-thumb-pic"])
        pic.set_size_request(168, 94)
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

    def _pick(self, path):
        self.section.choose(path)


__all__ = ["BackgroundSection", "find_wallpapers"]
