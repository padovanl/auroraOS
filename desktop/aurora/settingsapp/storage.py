"""Settings → Storage, like Windows': what fills the disk, by kind, with a
one-click cleanup for each thing that can go, and Storage Sense, which cleans
up by itself."""

import os
import shutil
import subprocess
import threading

from gi.repository import Adw, Gdk, GLib, Gtk

from aurora import apps, housekeeping, settings
from aurora.i18n import N_, _
from aurora.settingsapp.util import Page, combo_row, switch_row, toast

# (key, label, color, special folder or None)
CATEGORIES = (
    ("apps", N_("Apps"), "#a970ff", None),
    ("documents", N_("Documents"), "#60a5fa", GLib.UserDirectory.DIRECTORY_DOCUMENTS),
    ("pictures", N_("Pictures"), "#f472b6", GLib.UserDirectory.DIRECTORY_PICTURES),
    ("music", N_("Music"), "#fbbf24", GLib.UserDirectory.DIRECTORY_MUSIC),
    ("videos", N_("Videos"), "#fb7185", GLib.UserDirectory.DIRECTORY_VIDEOS),
    ("downloads", N_("Downloads"), "#34d399", GLib.UserDirectory.DIRECTORY_DOWNLOAD),
    ("desktop", N_("Desktop"), "#22d3ee", GLib.UserDirectory.DIRECTORY_DESKTOP),
    ("cache", N_("Temporary files and cache"), "#94a3b8", None),
    ("trash", N_("Trash"), "#f97316", None),
    ("other", N_("Other files in your folder"), "#64748b", None),
    ("system", N_("System"), "#475569", None),
)
DOWNLOAD_DAYS = (0, 14, 30, 60)


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def same_disk(a, b):
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return True


def installed_apps_size():
    """Debian packages and Flatpak apps, in bytes."""
    total = 0
    try:
        out = subprocess.run(["dpkg-query", "-W", "-f=${Installed-Size}\n"],
                             capture_output=True, text=True, timeout=30).stdout
        total += sum(int(x) for x in out.split() if x.isdigit()) * 1024
    except (OSError, subprocess.TimeoutExpired):
        pass
    for folder in ("/var/lib/flatpak", os.path.expanduser("~/.local/share/flatpak")):
        total += housekeeping.tree_size(folder)
    return total


def measure(stop):
    """{category: bytes} for the disk that holds your home folder."""
    home = os.path.expanduser("~")
    sizes = {}
    counted = 0
    for key, _label, _color, special in CATEGORIES:
        if special is None:
            continue
        path = GLib.get_user_special_dir(special)
        if not path or os.path.realpath(path) == os.path.realpath(home):
            sizes[key] = 0
            continue
        sizes[key] = housekeeping.tree_size(path, stop)
        counted += sizes[key]
    sizes["cache"] = housekeeping.tree_size(GLib.get_user_cache_dir(), stop)
    sizes["trash"] = housekeeping.tree_size(housekeeping.trash_dir(), stop)
    counted += sizes["cache"] + sizes["trash"]
    sizes["other"] = max(housekeeping.tree_size(home, stop) - counted, 0)
    sizes["apps"] = installed_apps_size()
    usage = shutil.disk_usage(home)
    on_disk = sum(v for k, v in sizes.items()
                  if k != "apps" or same_disk("/usr", home))
    sizes["system"] = max(usage.used - on_disk, 0)
    return sizes, usage


class Storage(Page):
    page_id = "storage"
    title = _("Storage")
    icon_name = "drive-harddisk-symbolic"

    def build(self):
        self.privacy = settings.get("org.gnome.desktop.privacy")
        self.aurora = settings.get()
        self._stop = False
        self.connect("unmap", lambda *_a: setattr(self, "_stop", True))

        top = self.group(_("Disk"))
        self.headline = Gtk.Label(xalign=0, css_classes=["title-2"], margin_top=4)
        self.subline = Gtk.Label(xalign=0, css_classes=["dim-label"], margin_bottom=10)
        self.bar = Gtk.DrawingArea(content_height=18, hexpand=True)
        self.bar.set_draw_func(self._draw_bar)
        self._segments = []
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_bottom=8)
        for w in (self.headline, self.subline, self.bar):
            box.append(w)
        top.add(box)

        self.kinds = self.group(_("What takes the space"))
        self.rows = {}
        for key, label, color, special in CATEGORIES:
            row = Adw.ActionRow(title=_(label), subtitle=_("Counting…"))
            dot = Gtk.Box(css_classes=["storage-dot"], valign=Gtk.Align.CENTER)
            self._paint(dot, color)
            row.add_prefix(dot)
            if special is not None:
                path = GLib.get_user_special_dir(special)
                if path:
                    row.set_activatable(True)
                    row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
                    row.connect("activated", lambda _r, p=path: apps.spawn(["aurora-files", p]))
            elif key == "apps":
                row.set_activatable(True)
                row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
                row.connect("activated", lambda *_a: apps.spawn(["aurora-settings", "--page",
                                                                 "applications"]))
            self.kinds.add(row)
            self.rows[key] = row

        clean = self.group(_("Clean up now"),
                           _("Free space in one click. The Trash and the cache can always "
                             "be emptied safely; apps remake their cache when needed."))
        self.trash_row = Adw.ActionRow(title=_("Empty the Trash"))
        self._button(self.trash_row, _("Empty"), self._empty_trash)
        self.cache_row = Adw.ActionRow(title=_("Clear temporary files and cache"))
        self._button(self.cache_row, _("Clear"), self._clear_cache)
        self.downloads_row = Adw.ActionRow(title=_("Downloads older than 30 days"),
                                           subtitle=_("Moved to the Trash, so you can "
                                                      "still get them back"))
        self._button(self.downloads_row, _("Review…"), self._old_downloads)
        for row in (self.trash_row, self.cache_row, self.downloads_row):
            clean.add(row)

        sense = self.group(_("Storage Sense"),
                           _("Frees space by itself, every few hours, while you work."))
        if self.privacy is not None:
            sense.add(switch_row(_("Empty old items from the Trash"),
                                 self.privacy.get_boolean("remove-old-trash-files"),
                                 lambda v: self.privacy.set_boolean("remove-old-trash-files", v)))
            sense.add(switch_row(_("Delete old temporary files"),
                                 self.privacy.get_boolean("remove-old-temp-files"),
                                 lambda v: self.privacy.set_boolean("remove-old-temp-files", v)))
            ages = (7, 14, 30, 60)
            age = self.privacy.get_uint("old-files-age")
            sense.add(combo_row(_("Old means older than"),
                                [_("1 week"), _("2 weeks"), _("30 days"), _("60 days")],
                                ages.index(age) if age in ages else 2,
                                on_change=lambda i: self.privacy.set_uint("old-files-age",
                                                                          ages[i])))
        if self.aurora is not None:
            days = self.aurora.get_int("downloads-cleanup-days")
            sense.add(combo_row(_("Move unused Downloads to the Trash"),
                                [_("Never"), _("After 2 weeks"), _("After 30 days"),
                                 _("After 60 days")],
                                DOWNLOAD_DAYS.index(days) if days in DOWNLOAD_DAYS else 0,
                                on_change=lambda i: self.aurora.set_int(
                                    "downloads-cleanup-days", DOWNLOAD_DAYS[i])))

        more = self.group(_("More"))
        disks = Adw.ActionRow(title=_("Disks and partitions"), activatable=True,
                              subtitle=_("Format, check and mount drives"))
        disks.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        disks.connect("activated", lambda *_a: apps.spawn(["gnome-disks"]))
        analyzer = Adw.ActionRow(title=_("See every folder's size"), activatable=True,
                                 subtitle=_("Disk Usage Analyzer"))
        analyzer.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        analyzer.connect("activated", lambda *_a: apps.spawn(["baobab"]))
        more.add(disks)
        more.add(analyzer)
        self.connect("map", lambda *_a: self.refresh())

    @staticmethod
    def _paint(widget, color):
        provider = Gtk.CssProvider()
        provider.load_from_string(f"box {{ background-color: {color}; }}")
        widget.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    @staticmethod
    def _button(row, label, callback):
        b = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda *_a: callback())
        row.add_suffix(b)

    # --- measuring ---------------------------------------------------------------

    def refresh(self):
        self._stop = False
        self.headline.set_label(_("Counting…"))

        def work():
            sizes, usage = measure(lambda: self._stop)
            old = housekeeping.old_files(
                GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD) or "/nonexistent",
                30)
            old_size = sum(housekeeping.tree_size(p) if os.path.isdir(p) else
                           os.lstat(p).st_blocks * 512 for p in old)
            GLib.idle_add(self._show, sizes, usage, old, old_size)
        threading.Thread(target=work, daemon=True).start()

    def _show(self, sizes, usage, old, old_size):
        self.headline.set_label(_("{free} free of {total}").format(free=human(usage.free),
                                                                  total=human(usage.total)))
        self.subline.set_label(_("{used} used").format(used=human(usage.used)))
        total = max(usage.total, 1)
        self._segments = []
        for key, label, color, _special in CATEGORIES:
            size = sizes.get(key, 0)
            self.rows[key].set_subtitle(human(size))
            # Apps live on another disk in the live system (or with a separate
            # /home): they don't take this disk's space.
            if key == "apps" and not same_disk("/usr", os.path.expanduser("~")):
                continue
            self._segments.append((size / total, color))
        self.bar.set_tooltip_text(_("{used} used").format(used=human(usage.used)))
        self.bar.queue_draw()
        self.trash_row.set_subtitle(human(sizes.get("trash", 0)))
        self.cache_row.set_subtitle(human(sizes.get("cache", 0)))
        self._old = old
        self.downloads_row.set_title(_("Downloads older than 30 days"))
        self.downloads_row.set_subtitle(
            _("{n} items · {size}, moved to the Trash so you can get them back").format(
                n=len(old), size=human(old_size)))
        return False

    def _draw_bar(self, _area, cr, width, height):
        """The disk as one rounded bar: a colored part per kind of file, then
        the free space."""
        import math
        fg = self.bar.get_color()
        r = height / 2

        def rounded():
            cr.new_sub_path()
            cr.arc(r, r, r, math.pi / 2, 3 * math.pi / 2)
            cr.arc(width - r, r, r, -math.pi / 2, math.pi / 2)
            cr.close_path()
        rounded()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
        cr.fill_preserve()
        cr.clip()
        x = 0.0
        for fraction, color in self._segments:
            w = min(fraction, 1 - x / width) * width if width else 0
            if w <= 0:
                continue
            rgba = Gdk.RGBA()
            rgba.parse(color)
            cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1)
            cr.rectangle(x, 0, max(w - 1.5, 1), height)
            cr.fill()
            x += w
            if x >= width:
                break

    # --- cleaning ------------------------------------------------------------------

    def _empty_trash(self):
        gone = housekeeping.empty_trash()
        toast(self, _("Trash emptied ({n} items)").format(n=gone))
        self.refresh()

    def _clear_cache(self):
        freed = housekeeping.clear_cache()
        toast(self, _("{size} freed").format(size=human(freed)))
        self.refresh()

    def _old_downloads(self):
        old = getattr(self, "_old", [])
        if not old:
            toast(self, _("Nothing old in Downloads"))
            return
        dialog = Adw.AlertDialog(
            heading=_("Move {n} old downloads to the Trash?").format(n=len(old)),
            body="\n".join(os.path.basename(p) for p in old[:12])
                 + ("\n…" if len(old) > 12 else ""))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("move", _("Move to Trash"))
        dialog.set_response_appearance("move", Adw.ResponseAppearance.DESTRUCTIVE)

        def done(_d, response):
            if response == "move":
                n = housekeeping.to_trash(old)
                toast(self, _("{n} items moved to the Trash").format(n=n))
                self.refresh()
        dialog.connect("response", done)
        dialog.present(self)
