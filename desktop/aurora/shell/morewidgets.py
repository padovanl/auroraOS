"""More desktop widgets: To Do, Countdown, Sun & Moon, Progress, Recent Files and
Clipboard. Each has its own options (right-click → Customize…); the helpers at
the top are pure and tested."""

import datetime
import json
import math
import os

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

from aurora import apps
from aurora.i18n import N_, _, ngettext
from aurora.shell.widgets import DesktopWidget, _ring, accent_rgba

SYNODIC_MONTH = 29.530588853
NEW_MOON = datetime.datetime(2000, 1, 6, 18, 14, tzinfo=datetime.timezone.utc)
MOON_NAMES = (N_("New Moon"), N_("Waxing Crescent"), N_("First Quarter"),
              N_("Waxing Gibbous"), N_("Full Moon"), N_("Waning Gibbous"),
              N_("Last Quarter"), N_("Waning Crescent"))


# --- pure helpers ---------------------------------------------------------------

def days_until(target, today):
    """Whole days from today to target (negative once it's past)."""
    return (target - today).days


def parse_date(text, fallback):
    try:
        return datetime.date.fromisoformat(str(text))
    except ValueError:
        return fallback


def period_progress(now, period):
    """(fraction 0…1 of the day, week, month or year that has passed, start, end)."""
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "day":
        start, end = day, day + datetime.timedelta(days=1)
    elif period == "week":
        start = day - datetime.timedelta(days=day.weekday())
        end = start + datetime.timedelta(days=7)
    elif period == "month":
        start = day.replace(day=1)
        end = (start + datetime.timedelta(days=32)).replace(day=1)
    else:
        start = day.replace(month=1, day=1)
        end = start.replace(year=start.year + 1)
    return (now - start) / (end - start), start, end


def moon(when):
    """(age as a fraction of the lunar month 0…1, illuminated fraction 0…1,
    index into MOON_NAMES)."""
    days = (when - NEW_MOON).total_seconds() / 86400
    age = (days % SYNODIC_MONTH) / SYNODIC_MONTH
    lit = (1 - math.cos(2 * math.pi * age)) / 2
    return age, lit, int(age * 8 + 0.5) % 8


def load_tasks(text):
    """Validated tasks from JSON: [{"text": str, "done": bool}]."""
    try:
        raw = json.loads(text or "[]")
    except ValueError:
        return []
    return [{"text": str(t.get("text", ""))[:500], "done": bool(t.get("done"))}
            for t in raw if isinstance(t, dict) and str(t.get("text", "")).strip()]


def data_path(name):
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "aurora", "widgets", name)


# --- To Do ------------------------------------------------------------------------

class TodoWidget(DesktopWidget):
    """A checklist: type a task and press Enter; tick it when done."""
    kind = "todo"
    OPTIONS = (("title", N_("Title"), "text", "", None),
               ("hide_done", N_("Hide finished tasks"), "switch", False, None))

    def build(self):
        self.title = Gtk.Label(xalign=0, css_classes=["widget-title"])
        self.count = Gtk.Label(xalign=1, hexpand=True, css_classes=["widget-caption"])
        head = Gtk.Box()
        head.append(self.title)
        head.append(self.count)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        scroller = Gtk.ScrolledWindow(child=self.list, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.entry = Gtk.Entry(placeholder_text=_("Add a task…"),
                               css_classes=["widget-entry"])
        self.entry.connect("activate", self._add_task)
        for w in (head, scroller, self.entry):
            self.body.append(w)
        self.tasks = self._load()

    def _path(self):
        return data_path(f"todo-{self.item['id']}.json")

    def _load(self):
        try:
            with open(self._path(), encoding="utf-8") as f:
                return load_tasks(f.read())
        except OSError:
            return []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path()), exist_ok=True)
            with open(self._path(), "w", encoding="utf-8") as f:
                json.dump(self.tasks, f)
        except OSError as err:
            print(f"aurora: tasks not saved: {err}")

    def _add_task(self, entry):
        text = entry.get_text().strip()
        if text:
            self.tasks.append({"text": text, "done": False})
            entry.set_text("")
            self._save()
            self.update()

    def _toggle(self, task, check):
        task["done"] = check.get_active()
        self._save()
        GLib.timeout_add(250, lambda: self.update() or False)

    def _delete(self, task):
        self.tasks.remove(task)
        self._save()
        self.update()

    def update(self):
        self.title.set_label(self.option("title") or _("To Do"))
        left = sum(not t["done"] for t in self.tasks)
        self.count.set_label(ngettext("{n} left", "{n} left", left).format(n=left)
                             if self.tasks else "")
        while (row := self.list.get_first_child()) is not None:
            self.list.remove(row)
        hide = self.option("hide_done")
        # Open tasks first, then the finished ones.
        for task in sorted(self.tasks, key=lambda t: t["done"]):
            if hide and task["done"]:
                continue
            row = Gtk.Box(spacing=4, css_classes=["widget-task"])
            check = Gtk.CheckButton(active=task["done"], valign=Gtk.Align.CENTER)
            check.connect("toggled", lambda c, t=task: self._toggle(t, c))
            label = Gtk.Label(label=task["text"], xalign=0, hexpand=True, wrap=True,
                              wrap_mode=Pango.WrapMode.WORD_CHAR, lines=2,
                              ellipsize=Pango.EllipsizeMode.END)
            if task["done"]:
                label.add_css_class("done")
            delete = Gtk.Button(icon_name="window-close-symbolic",
                                css_classes=["flat", "circular", "widget-task-delete"],
                                valign=Gtk.Align.CENTER, tooltip_text=_("Delete"))
            delete.connect("clicked", lambda _b, t=task: self._delete(t))
            row.append(check)
            row.append(label)
            row.append(delete)
            self.list.append(row)
        if not self.tasks:
            self.list.append(Gtk.Label(label=_("Nothing to do. Enjoy!"), xalign=0,
                                       css_classes=["widget-caption"]))


# --- Countdown ------------------------------------------------------------------

class CountdownWidget(DesktopWidget):
    """Days to a date that matters: a trip, a birthday, a deadline."""
    interval = 60
    kind = "countdown"
    OPTIONS = (("title", N_("Event"), "text", "", None),
               ("date", N_("Date"), "date", "", None),
               ("style", N_("Color"), "choice", "accent",
                [("accent", N_("Accent")), ("sunset", N_("Sunset")), ("ocean", N_("Ocean")),
                 ("forest", N_("Forest"))]))
    STYLES = ("accent", "sunset", "ocean", "forest")

    def build(self):
        self.title = Gtk.Label(xalign=0, css_classes=["widget-title"],
                               ellipsize=Pango.EllipsizeMode.END)
        self.number = Gtk.Label(xalign=0, vexpand=True, valign=Gtk.Align.END,
                                css_classes=["widget-countdown", "numeric"])
        self.unit = Gtk.Label(xalign=0, css_classes=["widget-caption"])
        self.when = Gtk.Label(xalign=0, css_classes=["widget-caption"])
        for w in (self.title, self.number, self.unit, self.when):
            self.body.append(w)

    def options_changed(self):
        for style in self.STYLES:
            self.card.remove_css_class(f"countdown-{style}")
        self.card.add_css_class(f"countdown-{self.option('style')}")
        self.update()

    def target(self):
        today = datetime.date.today()
        return parse_date(self.option("date"), today + datetime.timedelta(days=30))

    def update(self):
        if not any(self.card.has_css_class(f"countdown-{s}") for s in self.STYLES):
            self.card.add_css_class(f"countdown-{self.option('style')}")
        target = self.target()
        days = days_until(target, datetime.date.today())
        name = self.option("title") or _("My Event")
        self.title.set_label(name)
        if days > 0:
            self.number.set_label(str(days))
            self.unit.set_label(ngettext("day to go", "days to go", days))
        elif days == 0:
            self.number.set_label("🎉")
            self.unit.set_label(_("It's today!"))
        else:
            self.number.set_label(str(-days))
            self.unit.set_label(ngettext("day ago", "days ago", -days))
        self.when.set_label(GLib.DateTime.new_local(target.year, target.month, target.day,
                                                    0, 0, 0).format("%a %-d %b %Y")
                            .replace("  ", " "))


# --- Sun & Moon -----------------------------------------------------------------

class SunWidget(DesktopWidget):
    """Sunrise, sunset and daylight where you are, and tonight's moon."""
    interval = 300
    kind = "sun"
    OPTIONS = (("moon", N_("Show the moon"), "switch", True, None),)

    def build(self):
        self.body.append(Gtk.Label(label=_("Sun & Moon"), xalign=0,
                                   css_classes=["widget-title"]))
        self.arc = Gtk.DrawingArea(content_width=120, content_height=46, vexpand=True)
        self.arc.set_draw_func(self._draw)
        self.body.append(self.arc)
        row = Gtk.Box(homogeneous=True)
        self.rise = Gtk.Label(css_classes=["widget-row-time", "numeric"])
        self.set_ = Gtk.Label(css_classes=["widget-row-time", "numeric"])
        row.append(self.rise)
        row.append(self.set_)
        self.body.append(row)
        self.detail = Gtk.Label(css_classes=["widget-caption"],
                                ellipsize=Pango.EllipsizeMode.END)
        self.body.append(self.detail)
        self._times = None

    def _location(self):
        from aurora import weather
        loc, _name = weather.place()
        return loc

    def update(self):
        from aurora import sun
        now = datetime.datetime.now().astimezone()
        loc = self._location()
        self._times = sun.sun_times(loc[0], loc[1], now.date(), now.tzinfo) if loc else None
        if self._times:
            rise, set_ = self._times
            self.rise.set_label("↑ " + rise.strftime("%H:%M"))
            self.set_.set_label("↓ " + set_.strftime("%H:%M"))
            length = set_ - rise
            hours, minutes = divmod(int(length.total_seconds() // 60), 60)
            text = _("{h} h {m} min of daylight").format(h=hours, m=minutes)
            self.set_tooltip_text(text)
        else:
            self.rise.set_label("")
            self.set_.set_label("")
            text = _("Choose your city in Weather") if loc is None else ""
        if self.option("moon"):
            # One short line: the daylight is in the tooltip then.
            _age, lit, index = moon(now)
            text = _(MOON_NAMES[index])
            self.set_tooltip_text(_("{phase} · {lit:.0f}% lit").format(
                phase=_(MOON_NAMES[index]), lit=lit * 100))
        self.detail.set_label(text)
        self.arc.queue_draw()

    def _draw(self, _area, cr, width, height):
        fg = self.arc.get_color()
        accent = accent_rgba()
        # The sky's arc from sunrise to sunset, with the sun where it is now.
        cx, base, r = width / 2, height - 4, min(width / 2 - 8, height - 10)
        cr.set_line_width(2)
        cr.set_dash([3, 4])
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.3)
        cr.arc(cx, base, r, math.pi, 2 * math.pi)
        cr.stroke()
        cr.set_dash([])
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.18)
        cr.move_to(cx - r - 6, base)
        cr.line_to(cx + r + 6, base)
        cr.stroke()
        now = datetime.datetime.now().astimezone()
        if self._times:
            rise, set_ = self._times
            t = (now - rise) / (set_ - rise)
            if 0 <= t <= 1:
                a = math.pi + math.pi * t
                x, y = cx + r * math.cos(a), base + r * math.sin(a)
                cr.set_source_rgba(1.0, 0.72, 0.3, 0.3)
                cr.arc(x, y, 10, 0, 2 * math.pi)
                cr.fill()
                cr.set_source_rgba(1.0, 0.78, 0.35, 1)
                cr.arc(x, y, 6, 0, 2 * math.pi)
                cr.fill()
                return
        if self.option("moon"):
            age, _lit, _index = moon(now)
            self._draw_moon(cr, cx, base - r * 0.55, 9, age, fg, accent)

    @staticmethod
    def _draw_moon(cr, x, y, radius, age, fg, _accent):
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.15)
        cr.arc(x, y, radius, 0, 2 * math.pi)
        cr.fill()
        # The lit part: the half disc on the sunny side, closed by the
        # terminator, half an ellipse that bulges toward the lit side while a
        # crescent and away from it while gibbous.
        waxing = age < 0.5
        k = math.cos(2 * math.pi * age)
        cr.save()
        cr.translate(x, y)
        cr.new_path()
        if waxing:
            cr.arc(0, 0, radius, -math.pi / 2, math.pi / 2)            # right half
        else:
            cr.arc_negative(0, 0, radius, -math.pi / 2, -3 * math.pi / 2)  # left half
        cr.save()
        cr.scale(max(abs(k), 0.001), 1)
        if (waxing and k > 0) or (not waxing and k < 0):
            cr.arc_negative(0, 0, radius, math.pi / 2, -math.pi / 2)   # through the right
        else:
            cr.arc(0, 0, radius, math.pi / 2, 3 * math.pi / 2)         # through the left
        cr.restore()
        cr.close_path()
        cr.set_source_rgba(0.96, 0.94, 0.85, 1)
        cr.fill()
        cr.restore()


# --- Progress ---------------------------------------------------------------------

class ProgressWidget(DesktopWidget):
    """How much of the day, week, month or year has gone by."""
    interval = 60
    kind = "progress"
    OPTIONS = (("period", N_("Show"), "choice", "year",
                [("day", N_("Today")), ("week", N_("This week")), ("month", N_("This month")),
                 ("year", N_("This year"))]),)

    def build(self):
        self.ring = Gtk.DrawingArea(content_width=72, content_height=72, vexpand=True)
        self.ring.set_draw_func(self._draw)
        self.caption = Gtk.Label(css_classes=["widget-caption"], wrap=True,
                                 justify=Gtk.Justification.CENTER)
        self.body.append(self.ring)
        self.body.append(self.caption)
        self.fraction = 0.0

    def update(self):
        now = datetime.datetime.now()
        period = self.option("period")
        self.fraction, start, end = period_progress(now, period)
        left = end - now
        if period == "day":
            hours = int(left.total_seconds() // 3600)
            text = ngettext("{n} hour left today", "{n} hours left today", hours).format(n=hours)
        elif period == "year":
            text = ngettext("{n} day left in {year}", "{n} days left in {year}",
                            left.days).format(n=left.days, year=start.year)
        else:
            days = max(left.days, 0)
            text = (ngettext("{n} day left this week", "{n} days left this week", days)
                    if period == "week" else
                    ngettext("{n} day left this month", "{n} days left this month", days)
                    ).format(n=days)
        self.caption.set_label(text)
        self.ring.queue_draw()

    def _draw(self, _area, cr, width, height):
        fg = self.ring.get_color()
        color = accent_rgba()
        _ring(cr, width / 2, height / 2, min(width, height) / 2 - 8, self.fraction, color,
              (fg.red, fg.green, fg.blue, 0.12))
        from gi.repository import PangoCairo
        layout = self.ring.create_pango_layout("")
        layout.set_markup(f"<b>{self.fraction * 100:.0f}%</b>", -1)
        w, h = layout.get_pixel_size()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 1)
        cr.move_to(width / 2 - w / 2, height / 2 - h / 2)
        PangoCairo.show_layout(cr, layout)


# --- Recent Files -----------------------------------------------------------------

class RecentWidget(DesktopWidget):
    """The files you opened last, one click away."""
    interval = 30
    kind = "recent"
    wide = True
    open_command = ["aurora-files", "recent:///"]
    OPTIONS = (("show", N_("Show"), "choice", "all",
                [("all", N_("All files")), ("documents", N_("Documents")),
                 ("images", N_("Pictures")), ("media", N_("Music and videos"))]),)
    GROUPS = {"documents": ("text/", "application/pdf", "application/vnd", "application/msword",
                            "application/x-", "application/json"),
              "images": ("image/",), "media": ("audio/", "video/")}

    def build(self):
        self.body.append(Gtk.Label(label=_("Recent Files"), xalign=0,
                                   css_classes=["widget-title"]))
        self.grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=2, max_children_per_line=2,
                                row_spacing=2, column_spacing=4, vexpand=True,
                                valign=Gtk.Align.START)
        self.body.append(self.grid)
        self.manager = Gtk.RecentManager.get_default()
        self._handler = self.manager.connect("changed", lambda *_a: self.update())
        self.connect("destroy", lambda *_a: self.manager.disconnect(self._handler))

    def _wanted(self, info):
        show = self.option("show")
        if show == "all":
            return True
        mime = info.get_mime_type() or ""
        return mime.startswith(self.GROUPS.get(show, ()))

    def update(self):
        items = [i for i in self.manager.get_items()
                 if i.is_local() and i.exists() and self._wanted(i)]
        items.sort(key=lambda i: i.get_modified().to_unix(), reverse=True)
        while (child := self.grid.get_first_child()) is not None:
            self.grid.remove(child)
        for info in items[:6]:
            button = Gtk.Button(css_classes=["flat", "widget-row"], tooltip_text=info.get_uri_display())
            row = Gtk.Box(spacing=6)
            row.append(Gtk.Image(gicon=info.get_gicon(), pixel_size=22))
            row.append(Gtk.Label(label=info.get_display_name(), xalign=0, hexpand=True,
                                 ellipsize=Pango.EllipsizeMode.MIDDLE, width_chars=4,
                                 max_width_chars=12))
            button.set_child(row)
            button.connect("clicked", lambda _b, u=info.get_uri(): self._open(u))
            self.grid.append(button)
        if not items:
            self.grid.append(Gtk.Label(label=_("Files you open appear here"), xalign=0,
                                       css_classes=["widget-caption"], wrap=True))
        child = self.grid.get_first_child()
        while child is not None:
            child.set_focusable(False)
            child = child.get_next_sibling()

    def _open(self, uri):
        if self.layer.editing:
            return
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as err:
            print(f"aurora: can't open {uri}: {err.message}")


# --- Clipboard --------------------------------------------------------------------

class ClipboardWidget(DesktopWidget):
    """What you copied lately: click one to copy it again."""
    interval = 5
    kind = "clipboard"
    wide = True
    OPTIONS = (("count", N_("Items"), "choice", "4",
                [("3", "3"), ("4", "4"), ("6", "6")]),)

    def build(self):
        head = Gtk.Box()
        head.append(Gtk.Label(label=_("Clipboard"), xalign=0, hexpand=True,
                              css_classes=["widget-title"]))
        self.flash = Gtk.Label(css_classes=["widget-caption"])
        head.append(self.flash)
        self.body.append(head)
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, vexpand=True)
        self.body.append(self.rows)
        self._shown = None

    def update(self):
        from aurora import clipboard
        try:
            count = int(self.option("count"))
        except ValueError:
            count = 4
        items = clipboard.load()[:count]
        if items == self._shown:
            return
        self._shown = items
        while (child := self.rows.get_first_child()) is not None:
            self.rows.remove(child)
        for text in items:
            one_line = " ".join(text.split())
            button = Gtk.Button(css_classes=["flat", "widget-row"], tooltip_text=_("Copy"))
            button.set_child(Gtk.Label(label=one_line, xalign=0,
                                       ellipsize=Pango.EllipsizeMode.END))
            button.connect("clicked", lambda _b, t=text: self._copy(t))
            self.rows.append(button)
        if not items:
            self.rows.append(Gtk.Label(label=_("Copied text appears here"), xalign=0,
                                       css_classes=["widget-caption"]))

    def _copy(self, text):
        if self.layer.editing:
            return
        Gdk.Display.get_default().get_clipboard().set(text)
        self.flash.set_label(_("Copied"))
        GLib.timeout_add(1500, lambda: self.flash.set_label("") or False)


__all__ = ["TodoWidget", "CountdownWidget", "SunWidget", "ProgressWidget", "RecentWidget",
           "ClipboardWidget", "apps"]
