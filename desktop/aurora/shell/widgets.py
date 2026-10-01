"""Desktop widgets: glanceable cards on the desktop, under the windows.

Clock, calendar, weather, system, now playing, notes and battery. They follow
the system: light or dark style, accent color, 12- or 24-hour clock and
seconds, the language's date format and first day of the week, the Weather
app's city and units, and Settings → Desktop & Dock → Desktop widgets.

Drag a widget anywhere: it snaps to a grid, and a guide shows where it will
land. Right-click the desktop → Edit Widgets… (or a widget → Edit Widgets…) to
remove them with × and add more from the gallery at the bottom. Positions are
fractions of the screen and sizes follow its height, so after a resolution
change every widget keeps its place and proportions.
"""

import json
import math
import os
import shutil
import subprocess
import threading
import uuid

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402

from aurora import apps, settings  # noqa: E402
from aurora.i18n import N_, _  # noqa: E402

GRID = 16            # px: widgets snap to this grid when dropped
SMALL = 170          # px: a small widget is SMALL x SMALL on a 1080-pixel-high screen
WIDE = 2 * SMALL + GRID
DRAG_THRESHOLD = 6   # px the pointer moves before a press becomes a drag
TOP_INSET = 44       # keep clear of the top bar
EDGE_INSET = 12
SLOT_INSET = 9       # px around each card, where the × of edit mode sits


# --- the list of widgets (pure, tested) -----------------------------------------

def kinds():
    """kind -> (title, icon, class), in gallery order."""
    from aurora.shell import devwidgets as dev
    from aurora.shell import morewidgets as more
    return {
        "clock": (_("Clock"), "preferences-system-time-symbolic", ClockWidget),
        "calendar": (_("Calendar"), "x-office-calendar-symbolic", CalendarWidget),
        "weather": (_("Weather"), "weather-few-clouds-symbolic", WeatherWidget),
        "system": (_("System"), "utilities-system-monitor-symbolic", SystemWidget),
        "media": (_("Now Playing"), "audio-x-generic-symbolic", MediaWidget),
        "notes": (_("Notes"), "document-edit-symbolic", NotesWidget),
        "battery": (_("Battery"), "battery-good-symbolic", BatteryWidget),
        "world": (_("World Clock"), "preferences-system-time-symbolic", WorldClockWidget),
        "network": (_("Network"), "network-transmit-receive-symbolic", NetworkWidget),
        "focus": (_("Focus"), "alarm-symbolic", FocusWidget),
        "photo": (_("Photo"), "image-x-generic-symbolic", PhotoWidget),
        "sun": (_("Sun & Moon"), "weather-clear-symbolic", more.SunWidget),
        # Getting things done.
        "todo": (_("To Do"), "checkbox-checked-symbolic", more.TodoWidget),
        "countdown": (_("Countdown"), "x-office-calendar-symbolic", more.CountdownWidget),
        "progress": (_("Progress"), "content-loading-symbolic", more.ProgressWidget),
        "recent": (_("Recent Files"), "document-open-recent-symbolic", more.RecentWidget),
        "clipboard": (_("Clipboard"), "edit-paste-symbolic", more.ClipboardWidget),
        # For developers and gamers.
        "projects": (_("Projects"), "folder-code-symbolic", dev.ProjectsWidget),
        "ports": (_("Local Servers"), "network-server-symbolic", dev.PortsWidget),
        "containers": (_("Containers"), "application-x-executable-symbolic",
                       dev.ContainersWidget),
        "gpu": (_("GPU"), "video-display-symbolic", dev.GpuWidget),
        "games": (_("Games"), "applications-games-symbolic", dev.GamesWidget),
        "performance": (_("Performance"), "power-profile-performance-symbolic",
                        dev.PerformanceWidget),
    }


# The gallery's sections, in order.
SECTIONS = (
    ("everyday", ("clock", "calendar", "weather", "world", "sun", "photo", "media")),
    ("productivity", ("todo", "notes", "countdown", "focus", "progress", "recent",
                      "clipboard")),
    ("system", ("system", "network", "battery")),
    ("developers", ("projects", "ports", "containers")),
    ("gamers", ("games", "gpu", "performance")),
)
KIND_NAMES = tuple(kind for _section, kinds_ in SECTIONS for kind in kinds_)
STATEFUL = ("notes", "todo")     # kinds that keep their contents in a file of their own


def load_list(text):
    """Validated widget entries from the settings JSON; bad entries are dropped."""
    try:
        raw = json.loads(text or "[]")
    except ValueError:
        return []
    items = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict) or entry.get("kind") not in KIND_NAMES:
            continue
        try:
            x, y = float(entry.get("x", 0.5)), float(entry.get("y", 0.5))
        except (TypeError, ValueError):
            continue
        item = {"kind": entry["kind"], "x": min(max(x, 0.0), 1.0),
                "y": min(max(y, 0.0), 1.0)}
        if entry["kind"] in STATEFUL:
            ident = str(entry.get("id") or "")
            item["id"] = ident if ident.isalnum() else uuid.uuid4().hex[:12]
        options = entry.get("options")
        if isinstance(options, dict):
            kept = {str(k): v for k, v in options.items()
                    if isinstance(v, (str, bool, int)) and len(str(v)) < 4096}
            if kept:
                item["options"] = kept
        items.append(item)
    return items


def dump_list(items):
    return json.dumps(items)


def snap(value, grid=GRID):
    return int(round(value / grid)) * grid


def clamp_position(x, y, width, height, area_width, area_height,
                   top=0, edge=0):
    """Keep a widget of width x height fully inside the area (minus insets)."""
    return (min(max(edge, x), max(edge, area_width - width - edge)),
            min(max(top, y), max(top, area_height - height - edge)))


def align_to_neighbours(x, y, width, height, others, reach=GRID):
    """Line a dropped widget up with nearby widgets: its left, right, top or
    bottom edge jumps to a neighbour's edge (or the gap-spaced spot next to it)
    within `reach` px. `others` are (x, y, width, height) rectangles."""
    best_x, best_y = (reach + 1, x), (reach + 1, y)
    for ox, oy, ow, oh in others:
        for candidate in (ox, ox + ow - width, ox + ow + GRID, ox - width - GRID):
            if abs(candidate - x) < best_x[0]:
                best_x = (abs(candidate - x), candidate)
        for candidate in (oy, oy + oh - height, oy + oh + GRID, oy - height - GRID):
            if abs(candidate - y) < best_y[0]:
                best_y = (abs(candidate - y), candidate)
    return best_x[1], best_y[1]


def free_spot(width, height, others, area_width, area_height, top=0, edge=0,
              bottom=0, gap=GRID):
    """Where a new widget of width x height fits without covering another:
    columns from the right edge inward (next to the widgets already there),
    top to bottom in each. `others` are (x, y, width, height). None if the
    screen is full."""
    def blockers(x, y):
        return [(ox, oy, ow, oh) for ox, oy, ow, oh in others
                if not (x + width + gap <= ox or ox + ow + gap <= x or
                        y + height + gap <= oy or oy + oh + gap <= y)]
    x = area_width - edge - width
    while x >= edge:
        y = top
        while y + height <= area_height - bottom:
            hit = blockers(x, y)
            if not hit:
                return x, y
            y = max(oy + oh + gap for _ox, oy, _ow, oh in hit)   # just below them
        x -= GRID
    return None


def rects_overlap(a, b):
    """Whether two (x, y, width, height) rectangles cover each other."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def widget_sizes(area_height):
    """(small, wide) side in px for a screen this high: 170 px at 1080 p,
    growing and shrinking with the screen, within readable limits."""
    small = int(round(min(max(SMALL * area_height / 1080, 156), 256)))
    return small, 2 * small + GRID


def first_weekday(locale_output=None):
    """Weekday (0 = Monday … 6 = Sunday) that starts the week in this locale."""
    if locale_output is None:
        try:
            locale_output = subprocess.run(["locale", "-k", "LC_TIME"], capture_output=True,
                                           text=True, timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):
            locale_output = ""
    fields = dict(line.split("=", 1) for line in locale_output.splitlines() if "=" in line)
    try:
        first = int(fields.get("first_weekday", "2"))
        base = fields.get("week-1stday", "19971130").strip('"')
    except ValueError:
        return 0
    # glibc counts first_weekday from week-1stday (19971130 is a Sunday).
    base_weekday = 6 if base == "19971130" else 0
    return (base_weekday + first - 1) % 7


def month_grid(year, month, first):
    """Weeks of the month, each 7 day numbers (0 outside the month)."""
    start = GLib.DateTime.new_local(year, month, 1, 0, 0, 0)
    days = GLib.Date.get_days_in_month(GLib.DateMonth(month), year)
    offset = (start.get_day_of_week() - 1 - first) % 7   # GLib: 1 = Monday
    cells = [0] * offset + list(range(1, days + 1))
    cells += [0] * (-len(cells) % 7)
    return [cells[i:i + 7] for i in range(0, len(cells), 7)]


# --- look ---------------------------------------------------------------------

def accent_rgba():
    from aurora.look import ACCENT_HEX
    iface = settings.interface()
    rgba = Gdk.RGBA()
    rgba.parse(ACCENT_HEX.get(iface.get_string("accent-color"), "#a970ff") if iface
               else "#a970ff")
    return rgba


def _ring(cr, cx, cy, radius, fraction, color, track, width=9):
    cr.new_path()   # or the arc starts with a line from the previous drawing
    cr.set_line_width(width)
    cr.set_line_cap(1)  # round
    cr.set_source_rgba(*track)
    cr.arc(cx, cy, radius, 0, 2 * math.pi)
    cr.stroke()
    if fraction > 0:
        cr.set_source_rgba(color.red, color.green, color.blue, 1)
        cr.arc(cx, cy, radius, -math.pi / 2, -math.pi / 2 + 2 * math.pi * min(fraction, 1))
        cr.stroke()


def usage_color(value, accent):
    """(r, g, b) for a gauge at value 0…1: the theme's accent while there's room,
    shading to amber from 60% and to rose-red from 85%."""
    amber, red = (1.0, 0.64, 0.36), (1.0, 0.33, 0.42)

    def mix(a, b, t):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    if value <= 0.6:
        return tuple(accent)
    if value <= 0.85:
        return mix(tuple(accent), amber, (value - 0.6) / 0.25)
    return mix(amber, red, min((value - 0.85) / 0.15, 1.0))


def _gauge(cr, cx, cy, radius, value, accent, fg, width=8):
    """A 270° gauge, open at the bottom, coloured by how full it is."""
    start, sweep = math.pi * 0.75, math.pi * 1.5
    cr.new_path()
    cr.set_line_cap(1)
    cr.set_line_width(width)
    cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.12)
    cr.arc(cx, cy, radius, start, start + sweep)
    cr.stroke()
    value = min(max(value, 0.0), 1.0)
    if value <= 0:
        return
    r, g, b = usage_color(value, (accent.red, accent.green, accent.blue))
    end = start + sweep * value
    cr.set_source_rgba(r, g, b, 0.22)            # soft glow under the arc
    cr.set_line_width(width + 6)
    cr.arc(cx, cy, radius, start, end)
    cr.stroke()
    cr.set_source_rgba(r, g, b, 1)
    cr.set_line_width(width)
    cr.arc(cx, cy, radius, start, end)
    cr.stroke()


# --- widgets ------------------------------------------------------------------

class DesktopWidget(Gtk.Widget):
    """A slot of exactly the layer's size holding the visible card.

    The overlay on the desktop gives children their natural size, so long text
    would make each card a different width; this widget measures itself instead
    (a Gtk.Box can't: its layout manager ignores do_measure). The card inside
    carries the style classes: desktop-widget, dragging, editing, light."""
    kind = ""
    wide = False
    open_command = None     # clicking the widget opens this
    interval = 0            # seconds between updates (0: only on demand)
    # Settings in the widget's "Customize…" popover:
    # (key, label, kind, default, choices) with kind "choice" (choices: [(value, label)]),
    # "switch" or "folder".
    OPTIONS = ()

    def option(self, key):
        for name, _label, _kind, default, _choices in self.OPTIONS:
            if name == key:
                return self.item.get("options", {}).get(key, default)
        raise KeyError(key)

    def set_option(self, key, value):
        self.item = dict(self.item)
        self.item["options"] = dict(self.item.get("options", {}), **{key: value})
        self.layer.save()
        self.options_changed()

    def options_changed(self):
        """An option changed: rebuild what depends on it."""
        self.update()

    def __init__(self, layer, item):
        super().__init__(halign=Gtk.Align.START, valign=Gtk.Align.START)
        self.layer, self.item = layer, item
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                            vexpand=True)
        overlay = Gtk.Overlay(child=self.body,
                              css_classes=["desktop-widget", f"widget-{self.kind}"])
        self.card = overlay
        self.remove_button = Gtk.Button(icon_name="window-close-symbolic",
                                        css_classes=["widget-remove", "circular"],
                                        halign=Gtk.Align.START, valign=Gtk.Align.START,
                                        visible=False, tooltip_text=_("Remove Widget"))
        self.remove_button.connect("clicked", lambda *_: layer.remove(self))
        overlay.set_parent(self)
        # The × sits on the card's corner, outside it, so it never covers text.
        self.remove_button.set_parent(self)
        self.build()

        click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        click.connect("released", self._on_click)
        self.add_controller(click)
        menu = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        menu.connect("pressed", self._on_menu)
        self.add_controller(menu)
        # Dragging is handled by the layer, on the desktop surface under the
        # widgets: a gesture on the widget itself would move with it, and each
        # step would shift its own coordinates (the widget jumps and flickers).

    def resize(self):
        self.queue_resize()

    def target_size(self):
        small, wide = self.layer.sizes
        return (wide if self.wide else small) + 2 * SLOT_INSET, small + 2 * SLOT_INSET

    def do_measure(self, orientation, for_size):
        # Exactly the layer's size, so every card lines up; more only if the
        # content can't shrink that far.
        minimum = self.card.measure(orientation, for_size)[0] + 2 * SLOT_INSET
        target = self.target_size()[0 if orientation == Gtk.Orientation.HORIZONTAL else 1]
        size = max(minimum, target)
        return size, size, -1, -1

    def do_size_allocate(self, width, height, baseline):
        from gi.repository import Graphene, Gsk
        inset = Gsk.Transform().translate(Graphene.Point().init(SLOT_INSET, SLOT_INSET))
        self.card.allocate(width - 2 * SLOT_INSET, height - 2 * SLOT_INSET, -1, inset)
        if self.remove_button.get_visible():
            size = self.remove_button.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            self.remove_button.allocate(size, size, -1, None)

    def do_dispose(self):
        for child in (self.card, self.remove_button):
            if child is not None and child.get_parent() is self:
                child.unparent()
        Gtk.Widget.do_dispose(self)

    def build(self):
        raise NotImplementedError

    def update(self):
        """Refresh the contents (called on the widget's own schedule)."""

    def restyle(self):
        """The accent color or light/dark style changed."""
        self.queue_draw()

    # interaction
    def _on_click(self, gesture, n_press, _x, _y):
        if self.layer.editing or not self.open_command or n_press != 1:
            return
        if self.layer.dragging(self) or self.layer.dragged_recently(self):
            return
        apps.spawn(self.open_command)

    def _on_menu(self, gesture, _n, x, y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)  # not the desktop's menu
        self.layer.show_menu(self, x, y)



class ClockWidget(DesktopWidget):
    interval = 1
    kind = "clock"
    open_command = ["gnome-clocks"]
    OPTIONS = (("style", N_("Style"), "choice", "analog",
                [("analog", N_("Analog")), ("digital", N_("Digital"))]),)

    def build(self):
        self.face = Gtk.DrawingArea(content_width=72, content_height=72, vexpand=True)
        self.face.set_draw_func(self._draw)
        self.time = Gtk.Label(css_classes=["widget-time", "numeric"])
        self.date = Gtk.Label(css_classes=["widget-caption"], ellipsize=Pango.EllipsizeMode.END)
        self.time.set_vexpand(False)
        for w in (self.face, self.time, self.date):
            self.body.append(w)
        self.body.set_valign(Gtk.Align.CENTER)

    def update(self):
        now = GLib.DateTime.new_now_local()
        analog = self.option("style") == "analog"
        self.face.set_visible(analog)
        (self.time.remove_css_class if analog else self.time.add_css_class)("widget-clock-big")
        s = settings.get()
        twelve = s is not None and s.get_string("clock-format") == "12h"
        seconds = s is not None and s.get_boolean("clock-show-seconds")
        fmt = ("%l:%M" if twelve else "%H:%M") + (":%S" if seconds else "") + (" %p" if twelve else "")
        self.time.set_label(now.format(fmt).strip())
        self.date.set_label(now.format("%a %-d %b").replace("  ", " "))
        self.face.queue_draw()

    def _draw(self, _area, cr, width, height):
        now = GLib.DateTime.new_now_local()
        fg = self.face.get_color()
        accent = accent_rgba()
        cx, cy, r = width / 2, height / 2, min(width, height) / 2 - 2
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.08)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()
        for tick in range(12):
            a = tick * math.pi / 6
            inner = r - (9 if tick % 3 == 0 else 6)
            cr.set_line_width(2.4 if tick % 3 == 0 else 1.4)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.75 if tick % 3 == 0 else 0.35)
            cr.move_to(cx + inner * math.sin(a), cy - inner * math.cos(a))
            cr.line_to(cx + (r - 3) * math.sin(a), cy - (r - 3) * math.cos(a))
            cr.stroke()
        hours = now.get_hour() % 12 + now.get_minute() / 60
        minutes = now.get_minute() + now.get_second() / 60
        cr.set_line_cap(1)
        for angle, length, width_ in ((hours * math.pi / 6, r * 0.5, 4),
                                      (minutes * math.pi / 30, r * 0.75, 3)):
            cr.set_line_width(width_)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.95)
            cr.move_to(cx, cy)
            cr.line_to(cx + length * math.sin(angle), cy - length * math.cos(angle))
            cr.stroke()
        second = now.get_second() * math.pi / 30
        cr.set_line_width(1.6)
        cr.set_source_rgba(accent.red, accent.green, accent.blue, 1)
        cr.move_to(cx - 10 * math.sin(second), cy + 10 * math.cos(second))
        cr.line_to(cx + r * 0.84 * math.sin(second), cy - r * 0.84 * math.cos(second))
        cr.stroke()
        cr.arc(cx, cy, 3.2, 0, 2 * math.pi)
        cr.fill()


class CalendarWidget(DesktopWidget):
    interval = 1
    kind = "calendar"
    open_command = ["gnome-calendar"]

    def build(self):
        self.title = Gtk.Label(xalign=0, css_classes=["widget-title"])
        self.grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True, vexpand=True)
        self.body.append(self.title)
        self.body.append(self.grid)
        self._shown = None

    def update(self):
        now = GLib.DateTime.new_now_local()
        key = (now.get_year(), now.get_month(), now.get_day_of_month())
        if key == self._shown:
            return
        self._shown = key
        self.title.set_label(now.format("%B"))
        while (child := self.grid.get_first_child()) is not None:
            self.grid.remove(child)
        first = first_weekday()
        monday = GLib.DateTime.new_local(2024, 1, 1, 0, 0, 0)  # a Monday
        for col in range(7):
            name = monday.add_days((first + col) % 7).format("%a")[:2]
            self.grid.attach(Gtk.Label(label=name, css_classes=["widget-weekday"]), col, 0, 1, 1)
        for row, week in enumerate(month_grid(key[0], key[1], first), start=1):
            for col, day in enumerate(week):
                label = Gtk.Label(label=str(day) if day else "", css_classes=["widget-day",
                                                                              "numeric"])
                if day == key[2]:
                    label.add_css_class("today")
                self.grid.attach(label, col, row, 1, 1)


class WeatherWidget(DesktopWidget):
    interval = 15 * 60
    kind = "weather"
    open_command = ["gnome-weather"]

    def build(self):
        self.place = Gtk.Label(xalign=0, css_classes=["widget-title"],
                               ellipsize=Pango.EllipsizeMode.END)
        row = Gtk.Box(spacing=8)
        self.temp = Gtk.Label(xalign=0, css_classes=["widget-big", "numeric"])
        self.icon = Gtk.Image(pixel_size=36, hexpand=True, halign=Gtk.Align.END)
        row.append(self.temp)
        row.append(self.icon)
        self.sky = Gtk.Label(xalign=0, css_classes=["widget-caption"], wrap=True, lines=2,
                             ellipsize=Pango.EllipsizeMode.END)
        self.range = Gtk.Label(xalign=0, css_classes=["widget-caption"])
        for w in (self.place, row, self.sky, self.range):
            self.body.append(w)
        self.place.set_label(_("Weather"))
        self.sky.set_label(_("Loading…"))
        self._busy = False
        from aurora import weather
        # The city picked in the Weather app shows at once, not at the next update.
        self._watch = weather.watch(self.update)
        self.connect("destroy", lambda *_: weather.unwatch(self._watch))

    def update(self):
        from aurora import weather
        weather.locate_then(self.update)
        loc, name = weather.place()
        self.place.set_label(name or _("Weather"))
        if loc is None:
            self.temp.set_label("")
            self.icon.set_from_icon_name("find-location-symbolic")
            self.sky.set_label(_("Choose your city in Weather"))
            return
        fahrenheit = weather.uses_fahrenheit()
        data = weather.cached(*loc, fahrenheit=fahrenheit)
        if data is not None:
            self._show(data)
            return
        if self._busy:
            return
        self._busy = True

        def work():
            try:
                result = weather.fetch(*loc, fahrenheit=fahrenheit)
            except Exception:  # noqa: BLE001 - offline is normal
                result = None
            GLib.idle_add(lambda: (self._done(result), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _done(self, data):
        self._busy = False
        if data is None:
            self.sky.set_label(_("Offline"))
        else:
            self._show(data)

    def _show(self, data):
        from aurora import weather
        text, icon = weather.describe(data["code"], data["is_day"])
        self.temp.set_label(f"{data['temp']:.0f}°")
        self.icon.set_from_icon_name(icon)
        self.sky.set_label(_(text))
        self.range.set_label(_("H {high:.0f}° L {low:.0f}°").format(high=data["high"],
                                                                   low=data["low"]))


class SystemWidget(DesktopWidget):
    interval = 3
    kind = "system"
    open_command = ["aurora-settings", "--page", "health"]
    wide = True
    OPTIONS = (("cpu", N_("Processor"), "switch", True, None),
               ("memory", N_("Memory"), "switch", True, None),
               ("disk", N_("Disk"), "switch", True, None),
               ("temperature", N_("Temperature"), "switch", False, None))

    def build(self):
        from aurora.shell import sysmon
        self.sysmon = sysmon
        self.gauges = Gtk.DrawingArea(content_height=96, vexpand=True, hexpand=True)
        self.gauges.set_draw_func(self._draw)
        self.body.append(self.gauges)
        self._cpu = sysmon.cpu_times(sysmon._read("/proc/stat"))
        self.values = []

    def update(self):
        s = self.sysmon
        values = []
        cpu = s.cpu_times(s._read("/proc/stat"))
        if self.option("cpu"):
            values.append((_("Processor"), s.cpu_percent(self._cpu, cpu) / 100, None))
        self._cpu = cpu
        if self.option("memory"):
            used, total = s.memory(s._read("/proc/meminfo"))
            values.append((_("Memory"), used / total if total else 0.0, None))
        if self.option("disk"):
            disk = shutil.disk_usage("/")
            values.append((_("Disk"), disk.used / disk.total if disk.total else 0.0, None))
        if self.option("temperature"):
            temp = s.temperature()
            values.append((_("Temperature"), (temp or 0) / 100,
                           f"{temp:.0f}°" if temp is not None else "—"))
        self.values = values
        self.gauges.queue_draw()

    def _draw(self, _area, cr, width, height):
        from gi.repository import PangoCairo
        if not self.values:
            return
        fg = self.gauges.get_color()
        accent = accent_rgba()
        n = len(self.values)
        caption = self.gauges.create_pango_layout("")
        font = caption.get_context().get_font_description()
        font.set_size(int(font.get_size() * 0.82))
        caption.set_font_description(font)
        caption.set_text("Ag", -1)
        caption_h = caption.get_pixel_size()[1]
        slot = width / n
        radius = max(min((height - caption_h - 6) / 2 - 5, slot / 2 - 9), 12)
        value_layout = self.gauges.create_pango_layout("")
        for i, (label, value, text) in enumerate(self.values):
            cx = slot * (i + 0.5)
            cy = (height - (2 * radius + caption_h + 2)) / 2 + radius
            _gauge(cr, cx, cy, radius, value, accent, fg, width=max(6, radius / 5))
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 1)
            value_layout.set_markup(f"<b>{text or f'{value * 100:.0f}%'}</b>", -1)
            w, h = value_layout.get_pixel_size()
            cr.move_to(cx - w / 2, cy - h / 2)
            PangoCairo.show_layout(cr, value_layout)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.65)
            caption.set_text(label, -1)
            caption.set_width(int(slot * 1024))
            caption.set_ellipsize(Pango.EllipsizeMode.END)
            w, h = caption.get_pixel_size()
            cr.move_to(cx - w / 2, cy + radius + 2)
            PangoCairo.show_layout(cr, caption)


class MediaWidget(DesktopWidget):
    interval = 15 * 60
    kind = "media"
    wide = True

    def build(self):
        row = Gtk.Box(spacing=12, vexpand=True)
        self.art = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=64,
                             css_classes=["widget-art"])
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER,
                       hexpand=True)
        self.title = Gtk.Label(xalign=0, css_classes=["widget-title"],
                               ellipsize=Pango.EllipsizeMode.END)
        self.artist = Gtk.Label(xalign=0, css_classes=["widget-caption"],
                                ellipsize=Pango.EllipsizeMode.END)
        text.append(self.title)
        text.append(self.artist)
        row.append(self.art)
        row.append(text)
        self.body.append(row)
        controls = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        media = self.layer.shell.media
        for icon, command in (("media-skip-backward-symbolic", "previous"),
                              ("media-playback-start-symbolic", "play_pause"),
                              ("media-skip-forward-symbolic", "next")):
            button = Gtk.Button(icon_name=icon, css_classes=["circular", "flat"])
            button.connect("clicked", lambda _b, c=command: media.command(c))
            controls.append(button)
            if command == "play_pause":
                self.play = button
        self.body.append(controls)
        self._handler = media.connect("changed", lambda *_: self.update())
        self.connect("destroy", lambda *_: media.disconnect(self._handler))

    def update(self):
        info = self.layer.shell.media.info()
        if info is None:
            self.title.set_label(_("Nothing playing"))
            self.artist.set_label(_("Music and videos appear here"))
            self.play.set_icon_name("media-playback-start-symbolic")
            return
        title, artist, playing = info
        self.title.set_label(title)
        self.artist.set_label(artist)
        self.play.set_icon_name("media-playback-pause-symbolic" if playing
                                else "media-playback-start-symbolic")


class NotesWidget(DesktopWidget):
    kind = "notes"
    COLORS = ("glass", "yellow", "pink", "blue", "green")
    OPTIONS = (("color", N_("Color"), "choice", "glass",
                [("glass", N_("Glass")), ("yellow", N_("Yellow")), ("pink", N_("Pink")),
                 ("blue", N_("Blue")), ("green", N_("Green"))]),)

    def options_changed(self):
        for color in self.COLORS:
            self.card.remove_css_class(f"note-{color}")
        self.card.add_css_class(f"note-{self.option('color')}")

    def build(self):
        self.view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, vexpand=True,
                                 css_classes=["widget-notes"], top_margin=4, left_margin=4,
                                 right_margin=4)
        self.view.get_buffer().set_text(self._load())
        self.hint = Gtk.Label(label=_("Write a note…"), xalign=0, yalign=0, can_target=False,
                              css_classes=["widget-caption"], margin_start=6, margin_top=4)
        self.view.get_buffer().connect("changed", lambda *_: self._save_later())
        scroller = Gtk.ScrolledWindow(child=self.view, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        stack = Gtk.Overlay(child=scroller, vexpand=True)
        stack.add_overlay(self.hint)
        self.body.append(Gtk.Label(label=_("Notes"), xalign=0, css_classes=["widget-title"]))
        self.body.append(stack)
        self._sync_hint()
        self.view.get_buffer().connect("changed", lambda *_a: self._sync_hint())
        self.options_changed()
        self._save_source = 0

    def _sync_hint(self):
        self.hint.set_visible(self.view.get_buffer().get_char_count() == 0)

    def _path(self):
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        return os.path.join(base, "aurora", "widgets", f"notes-{self.item['id']}.txt")

    def _load(self):
        try:
            with open(self._path(), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def _save_later(self):
        if self._save_source:
            GLib.source_remove(self._save_source)
        self._save_source = GLib.timeout_add(600, self._save)

    def _save(self):
        self._save_source = 0
        buf = self.view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        try:
            os.makedirs(os.path.dirname(self._path()), exist_ok=True)
            with open(self._path(), "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as err:
            print(f"aurora: notes not saved: {err}")
        return GLib.SOURCE_REMOVE


class BatteryWidget(DesktopWidget):
    interval = 30
    kind = "battery"
    open_command = ["aurora-settings", "--page", "power"]

    def build(self):
        self.ring = Gtk.DrawingArea(content_width=72, content_height=72, vexpand=True)
        self.ring.set_draw_func(self._draw)
        self.caption = Gtk.Label(css_classes=["widget-caption"])
        self.body.append(self.ring)
        self.body.append(self.caption)
        battery = self.layer.shell.battery
        self._handler = battery.connect("changed", lambda *_: self.update())
        self.connect("destroy", lambda *_: battery.disconnect(self._handler))

    def update(self):
        bat = self.layer.shell.battery
        if not bat.present:
            self.caption.set_label(_("No battery"))
        elif bat.charging:
            self.caption.set_label(_("Charging"))
        else:
            self.caption.set_label(_("On battery"))
        self.ring.queue_draw()

    def _draw(self, _area, cr, width, height):
        bat = self.layer.shell.battery
        fg = self.ring.get_color()
        level = bat.percentage / 100 if bat.present else 0.0
        color = accent_rgba()
        if bat.present and not bat.charging and bat.percentage <= 15:
            color.parse("#ff6f91")
        _ring(cr, width / 2, height / 2, min(width, height) / 2 - 8, level, color,
              (fg.red, fg.green, fg.blue, 0.12))
        from gi.repository import PangoCairo
        layout = self.ring.create_pango_layout("")
        layout.set_markup(f"<b>{bat.percentage:.0f}%</b>" if bat.present else "—", -1)
        w, h = layout.get_pixel_size()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 1)
        cr.move_to(width / 2 - w / 2, height / 2 - h / 2)
        PangoCairo.show_layout(cr, layout)


class WorldClockWidget(DesktopWidget):
    """The cities chosen in Clocks (or a few well-known ones), with day/night."""
    interval = 30
    kind = "world"
    open_command = ["gnome-clocks"]

    def build(self):
        self.body.append(Gtk.Label(label=_("World Clock"), xalign=0,
                                   css_classes=["widget-title"]))
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, vexpand=True,
                            valign=Gtk.Align.CENTER)
        self.body.append(self.rows)

    @staticmethod
    def cities():
        """[(name, GLib.TimeZone)] from Clocks' world clocks."""
        found = []
        try:
            gi.require_version("GWeather", "4.0")
            from gi.repository import Gio, GWeather
            source = Gio.SettingsSchemaSource.get_default()
            if source is not None and source.lookup("org.gnome.clocks", True) is not None:
                world = GWeather.Location.get_world()
                for entry in Gio.Settings.new("org.gnome.clocks").get_value("world-clocks"):
                    loc = world.deserialize(entry["location"]) if "location" in entry else None
                    if loc is not None and loc.get_timezone() is not None:
                        found.append((loc.get_city_name() or loc.get_name(), loc.get_timezone()))
        except Exception:  # noqa: BLE001 - no GWeather or no Clocks
            pass
        if not found:
            found = [(name, GLib.TimeZone.new_identifier(zone)) for name, zone in
                     (("New York", "America/New_York"), ("London", "Europe/London"),
                      ("Tokyo", "Asia/Tokyo"))]
        return [(n, z) for n, z in found if z is not None][:4]

    def update(self):
        while (child := self.rows.get_first_child()) is not None:
            self.rows.remove(child)
        s = settings.get()
        twelve = s is not None and s.get_string("clock-format") == "12h"
        here = GLib.DateTime.new_now_local()
        for name, zone in self.cities():
            now = GLib.DateTime.new_now(zone)
            row = Gtk.Box(spacing=6)
            day = 7 <= now.get_hour() < 19
            row.append(Gtk.Image(icon_name="weather-clear-symbolic" if day
                                 else "weather-clear-night-symbolic",
                                 css_classes=["widget-daynight", "day" if day else "night"]))
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            text.append(Gtk.Label(label=name, xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                  css_classes=["widget-row-title"]))
            hours = (now.get_utc_offset() - here.get_utc_offset()) / 3_600_000_000
            offset = (_("same time") if hours == 0 else
                      (f"+{hours:g} h" if hours > 0 else f"{hours:g} h"))
            text.append(Gtk.Label(label=offset, xalign=0, css_classes=["widget-caption"]))
            row.append(text)
            row.append(Gtk.Label(label=now.format("%l:%M %p" if twelve else "%H:%M").strip(),
                                 css_classes=["widget-row-time", "numeric"],
                                 valign=Gtk.Align.CENTER))
            self.rows.append(row)


class NetworkWidget(DesktopWidget):
    """Download and upload speed, with the last minute as a graph."""
    interval = 2
    kind = "network"
    open_command = ["aurora-settings", "--page", "network"]
    HISTORY = 30
    OPTIONS = (("graph", N_("Show the graph"), "switch", True, None),)

    def options_changed(self):
        self.graph.set_visible(self.option("graph"))

    def build(self):
        from aurora.shell import sysmon
        self.sysmon = sysmon
        self.body.append(Gtk.Label(label=_("Network"), xalign=0, css_classes=["widget-title"]))
        row = Gtk.Box(spacing=10)
        self.down = Gtk.Label(xalign=0, css_classes=["widget-rate", "numeric"], hexpand=True)
        self.up = Gtk.Label(xalign=0, css_classes=["widget-rate", "numeric"], hexpand=True)
        row.append(self.down)
        row.append(self.up)
        self.body.append(row)
        self.graph = Gtk.DrawingArea(vexpand=True, content_height=40)
        self.graph.set_draw_func(self._draw)
        self.body.append(self.graph)
        self._last = (GLib.get_monotonic_time(), *sysmon.network_bytes())
        self.history = [(0.0, 0.0)] * self.HISTORY
        self.graph.set_visible(self.option("graph"))

    def update(self):
        now, (rx, tx) = GLib.get_monotonic_time(), self.sysmon.network_bytes()
        then, rx0, tx0 = self._last
        seconds = max((now - then) / 1e6, 0.001)
        down, up = max(rx - rx0, 0) / seconds, max(tx - tx0, 0) / seconds
        self._last = (now, rx, tx)
        self.history = self.history[1:] + [(down, up)]
        self.down.set_label("↓ " + self.sysmon.human_rate(down))
        self.up.set_label("↑ " + self.sysmon.human_rate(up))
        self.graph.queue_draw()

    def _draw(self, _area, cr, width, height):
        peak = max(max(max(d, u) for d, u in self.history), 1024)
        accent = accent_rgba()
        step = width / (self.HISTORY - 1)
        for index, alpha in ((0, 0.9), (1, 0.45)):
            cr.move_to(0, height)
            for i, sample in enumerate(self.history):
                cr.line_to(i * step, height - 2 - (height - 4) * sample[index] / peak)
            cr.line_to(width, height)
            cr.close_path()
            cr.set_source_rgba(accent.red, accent.green, accent.blue, alpha * 0.35)
            cr.fill_preserve()
            cr.set_source_rgba(accent.red, accent.green, accent.blue, alpha)
            cr.set_line_width(1.5)
            cr.stroke()


class FocusWidget(DesktopWidget):
    """A focus timer: 25 minutes of work, then a notification."""
    kind = "focus"
    interval = 1
    MINUTES = (25, 50, 15)
    OPTIONS = (("minutes", N_("Length"), "choice", "25",
                [("15", N_("15 minutes")), ("25", N_("25 minutes")),
                 ("50", N_("50 minutes"))]),)

    def options_changed(self):
        self.minutes = int(self.option("minutes"))
        self.length.set_label(str(self.minutes))
        self.reset()

    def build(self):
        self.ring = Gtk.DrawingArea(content_width=72, content_height=72, vexpand=True)
        self.ring.set_draw_func(self._draw)
        self.body.append(self.ring)
        controls = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        self.start = Gtk.Button(icon_name="media-playback-start-symbolic",
                                css_classes=["circular", "widget-accent-button"],
                                tooltip_text=_("Start or pause"))
        self.start.connect("clicked", lambda *_a: self.toggle())
        self.length = Gtk.Button(label="25", css_classes=["circular", "flat", "numeric"],
                                 tooltip_text=_("Change the length"))
        self.length.connect("clicked", lambda *_a: self.cycle())
        reset = Gtk.Button(icon_name="view-refresh-symbolic", css_classes=["circular", "flat"],
                           tooltip_text=_("Reset"))
        reset.connect("clicked", lambda *_a: self.reset())
        for w in (self.length, self.start, reset):
            controls.append(w)
        self.body.append(controls)
        self.minutes = int(self.option("minutes"))
        self.length.set_label(str(self.minutes))
        self.reset()

    def reset(self):
        self.left = self.minutes * 60
        self.running = False
        self.start.set_icon_name("media-playback-start-symbolic")
        self.ring.queue_draw()

    def cycle(self):
        following = self.MINUTES[(self.MINUTES.index(self.minutes) + 1) % len(self.MINUTES)
                                 if self.minutes in self.MINUTES else 0]
        self.set_option("minutes", str(following))

    def toggle(self):
        self.running = not self.running
        self.start.set_icon_name("media-playback-pause-symbolic" if self.running
                                 else "media-playback-start-symbolic")

    def update(self):
        if not self.running:
            return
        self.left -= 1
        if self.left <= 0:
            self.reset()
            sysnotify = getattr(self.layer.shell, "sysnotify", None)
            if sysnotify is not None:
                sysnotify.notify(_("Focus time is over"),
                                 _("Take a short break."), "alarm-symbolic")
        self.ring.queue_draw()

    def _draw(self, _area, cr, width, height):
        fg = self.ring.get_color()
        total = self.minutes * 60
        _ring(cr, width / 2, height / 2, min(width, height) / 2 - 7, self.left / total,
              accent_rgba(), (fg.red, fg.green, fg.blue, 0.12), width=7)
        from gi.repository import PangoCairo
        layout = self.ring.create_pango_layout("")
        layout.set_markup(f"<b>{self.left // 60:02d}:{self.left % 60:02d}</b>", -1)
        w, h = layout.get_pixel_size()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 1)
        cr.move_to(width / 2 - w / 2, height / 2 - h / 2)
        PangoCairo.show_layout(cr, layout)


def pictures(folder=None, limit=400):
    """Image files in the Pictures folder (and one level of subfolders)."""
    folder = folder or GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) \
        or os.path.expanduser("~/Pictures")
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")] if root == folder else []
        for name in sorted(files):
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                found.append(os.path.join(root, name))
                if len(found) >= limit:
                    return found
    return found


class PhotoWidget(DesktopWidget):
    """A photo from Pictures, a different one every ten minutes."""
    kind = "photo"
    wide = True
    OPTIONS = (("folder", N_("Folder"), "folder", "", None),
               ("minutes", N_("Change every"), "choice", "10",
                [("1", N_("Minute")), ("10", N_("10 minutes")), ("60", N_("Hour"))]))

    @property
    def interval(self):
        return int(self.option("minutes")) * 60

    def build(self):
        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, vexpand=True,
                                   hexpand=True, can_shrink=True,
                                   css_classes=["widget-photo"])
        self.empty = Gtk.Label(label=_("Photos in your Pictures folder appear here"),
                               wrap=True, vexpand=True, css_classes=["widget-caption"])
        self.body.append(self.picture)
        self.body.append(self.empty)
        self.card.add_css_class("widget-photo-card")
        self.path = None

    def update(self):
        import random
        found = pictures(self.option("folder") or None)
        self.path = random.choice(found) if found else None
        self.picture.set_visible(self.path is not None)
        self.empty.set_visible(self.path is None)
        if self.path:
            self.picture.set_filename(self.path)

    def _on_click(self, gesture, n_press, _x, _y):
        if self.path and n_press == 1 and not self.layer.editing \
                and not self.layer.dragging(self) and not self.layer.dragged_recently(self):
            apps.spawn(["xdg-open", self.path])


# --- the layer on the desktop ------------------------------------------------------

class WidgetLayer:
    """Adds the widgets to the wallpaper's overlay (primary monitor)."""

    def __init__(self, shell, overlay, monitor):
        self.shell, self.overlay, self.monitor = shell, overlay, monitor
        self.widgets = []
        self.editing = False
        self.s = settings.get()
        self.sizes = widget_sizes(self.area()[1])
        # Where a dragged widget will land, under the widgets.
        self.ghost = Gtk.Box(css_classes=["widget-ghost"], can_target=False, visible=False,
                             halign=Gtk.Align.START, valign=Gtk.Align.START)
        overlay.add_overlay(self.ghost)
        self.gallery = self._build_gallery()
        overlay.add_overlay(self.gallery)
        self._menu = None
        self._drag = None           # (widget, start x, start y, moved)
        self._dropped = (None, 0)   # (widget, time) of the last drop: that click opens nothing
        monitor.connect("notify::geometry", lambda *_: self.relayout())
        style = Adw.StyleManager.get_default()
        style.connect("notify::dark", lambda *_: self._restyle())
        iface = settings.interface()
        if iface is not None:
            iface.connect("changed::accent-color", lambda *_: self._restyle())
        if self.s is not None:
            self.s.connect("changed::desktop-widgets", lambda *_: self.reload())
            self.s.connect("changed::desktop-widget-list", lambda *_: self._external_change())
            for key in ("clock-format", "clock-show-seconds"):
                self.s.connect(f"changed::{key}", lambda *_: self._tick_all())
        self._saving = False
        self.reload()
        self._seconds = 0
        GLib.timeout_add_seconds(1, self._every_second)

    # geometry
    def area(self):
        geometry = self.monitor.get_geometry()
        return geometry.width, geometry.height

    def clamp(self, widget, x, y):
        small, wide = self.sizes
        w = max(widget.get_width(), wide if widget.wide else small)
        h = max(widget.get_height(), small)
        return clamp_position(x, y, w, h, *self.area(), top=TOP_INSET, edge=EDGE_INSET)

    def _place(self, widget):
        width, height = self.area()
        x, y = self.clamp(widget, int(widget.item["x"] * width), int(widget.item["y"] * height))
        widget.set_margin_start(int(x))
        widget.set_margin_top(int(y))

    def relayout(self):
        """The resolution changed: same places (fractions of the screen), sizes
        in proportion to its height."""
        self.sizes = widget_sizes(self.area()[1])
        self._gallery_width()
        for widget in self.widgets:
            widget.resize()
            self._place(widget)
        self._separate()

    def _separate(self):
        """Widgets keep their places as fractions of the screen, but not below
        a readable size: on a smaller screen (or a larger scale) neighbours
        can overlap. Move each one that does just clear of the others, the
        same way a new widget finds its spot; what is saved stays as it was,
        so they return to their places on the larger screen."""
        width, height = self.area()
        if width < 320 or height < 240:
            return      # the monitor's size isn't known yet
        placed = []
        for widget in sorted(self.widgets, key=lambda w: (w.get_margin_start(),
                                                         w.get_margin_top())):
            # The sizes the layout gives them: allocations may still be from
            # the previous screen size.
            w, h = widget.target_size()
            x, y = widget.get_margin_start(), widget.get_margin_top()
            if any(rects_overlap((x, y, w, h), o) for o in placed):
                below = [o for o in placed if rects_overlap((x, y, w, h), o)]
                ny = max(oy + oh for _ox, oy, _ow, oh in below)
                if ny + h <= height - EDGE_INSET and not any(
                        rects_overlap((x, ny, w, h), o) for o in placed):
                    y = ny
                else:
                    spot = free_spot(w, h, placed, width, height, top=TOP_INSET,
                                     edge=EDGE_INSET, gap=0)
                    if spot is not None:
                        x, y = (int(v) for v in spot)
                widget.set_margin_start(int(x))
                widget.set_margin_top(int(y))
            placed.append((x, y, w, h))

    # dragging (driven by the desktop surface's drag gesture, see wallpaper.py)
    def widget_at(self, picked):
        """The widget a press on `picked` should drag, or None (text is selected
        by dragging, not moved)."""
        node = picked
        while node is not None and not isinstance(node, DesktopWidget):
            if isinstance(node, (Gtk.TextView, Gtk.Entry, Gtk.Text)):
                return None
            node = node.get_parent()
        return node

    def drag_begin(self, widget, x, y):
        self._drag = [widget, widget.get_margin_start(), widget.get_margin_top(), False]

    def drag_update(self, dx, dy):
        if self._drag is None:
            return
        widget, x0, y0, moved = self._drag
        if not moved:
            if abs(dx) < DRAG_THRESHOLD and abs(dy) < DRAG_THRESHOLD:
                return
            self._drag[3] = True
            widget.card.add_css_class("dragging")
            # The guide has the card's size; its CSS margin is the slot's inset.
            self.ghost.set_size_request(max(widget.get_width() - 2 * SLOT_INSET, 1),
                                        max(widget.get_height() - 2 * SLOT_INSET, 1))
            self.ghost.set_visible(True)
        x, y = self.clamp(widget, x0 + dx, y0 + dy)
        widget.set_margin_start(int(x))
        widget.set_margin_top(int(y))
        gx, gy = self._landing(widget, x, y)
        self.ghost.set_margin_start(int(gx))
        self.ghost.set_margin_top(int(gy))

    def drag_end(self):
        if self._drag is None:
            return
        widget, _x0, _y0, moved = self._drag
        self._drag = None
        if not moved:
            return
        self.ghost.set_visible(False)
        widget.card.remove_css_class("dragging")
        x, y = self._landing(widget, widget.get_margin_start(), widget.get_margin_top())
        widget.set_margin_start(int(x))
        widget.set_margin_top(int(y))
        self._dropped = (widget, GLib.get_monotonic_time())
        self.moved(widget)

    def _landing(self, widget, x, y):
        """Where a widget dropped at x, y lands: next to or in line with a
        neighbour when close to one, else on the grid."""
        width, height = widget.get_width(), widget.get_height()
        others = [(o.get_margin_start(), o.get_margin_top(), o.get_width(), o.get_height())
                  for o in self.widgets if o is not widget]
        ax, ay = align_to_neighbours(x, y, width, height, others)
        return self.clamp(widget, ax if ax != x else snap(x), ay if ay != y else snap(y))

    def dragging(self, widget):
        """This widget is being moved (the widget's click arrives before the
        desktop's drag ends)."""
        return self._drag is not None and self._drag[0] is widget and self._drag[3]

    def dragged_recently(self, widget):
        dropped, when = self._dropped
        return dropped is widget and GLib.get_monotonic_time() - when < 400_000

    # contents
    def reload(self):
        for widget in self.widgets:
            self.overlay.remove_overlay(widget)
        self.widgets = []
        enabled = self.s is None or self.s.get_boolean("desktop-widgets")
        if not enabled:
            self.set_editing(False)
            return
        items = load_list(self.s.get_string("desktop-widget-list") if self.s else "")
        for item in items:
            self._add_widget(item)
        self._restyle()
        self._tick_all()
        self._separate()

    def _external_change(self):
        if not self._saving:
            self.reload()

    def _add_widget(self, item):
        cls = kinds()[item["kind"]][2]
        widget = cls(self, item)
        self._place(widget)
        widget.remove_button.set_visible(self.editing)
        if self.editing:
            widget.card.add_css_class("editing")
        self.overlay.add_overlay(widget)
        # Keep the gallery on top of every widget.
        self.overlay.remove_overlay(self.gallery)
        self.overlay.add_overlay(self.gallery)
        self.widgets.append(widget)
        return widget

    def save(self):
        width, height = self.area()
        items = []
        for widget in self.widgets:
            item = dict(widget.item)
            item["x"] = round(widget.get_margin_start() / width, 4) if width else 0
            item["y"] = round(widget.get_margin_top() / height, 4) if height else 0
            widget.item = item
            items.append(item)
        if self.s is not None:
            self._saving = True
            self.s.set_string("desktop-widget-list", dump_list(items))
            self._saving = False

    def moved(self, _widget):
        self.save()

    def remove(self, widget):
        self.overlay.remove_overlay(widget)
        self.widgets.remove(widget)
        self.save()

    def add(self, kind):
        width, height = self.area()
        item = {"kind": kind, "x": 0.5, "y": 0.35}
        if kind in STATEFUL:
            item["id"] = uuid.uuid4().hex[:12]
        widget = self._add_widget(item)
        small, wide = self.sizes
        w = (wide if widget.wide else small) + 2 * SLOT_INSET
        h = small + 2 * SLOT_INSET
        others = [(o.get_margin_start(), o.get_margin_top(),
                   max(o.get_width(), (wide if o.wide else small) + 2 * SLOT_INSET),
                   max(o.get_height(), h)) for o in self.widgets if o is not widget]
        # Clear of the others, and above the gallery while it's open.
        spot = free_spot(w, h, others, width, height, top=TOP_INSET, edge=EDGE_INSET,
                         bottom=max(EDGE_INSET, self.gallery.get_height() + 110), gap=0)
        if spot is None:
            spot = clamp_position(snap(width / 2 - w / 2), snap(height * 0.35), w, h, width,
                                  height, top=TOP_INSET, edge=EDGE_INSET)
        x, y = (int(v) for v in spot)
        widget.set_margin_start(x)
        widget.set_margin_top(y)
        widget.update()
        self._restyle()
        self.save()

    # edit mode
    def set_editing(self, on):
        if on != self.editing:
            self._clear_windows() if on else self._restore_windows()
        self.editing = on
        self.gallery.set_visible(on)
        for widget in self.widgets:
            widget.remove_button.set_visible(on)
            (widget.card.add_css_class if on else widget.card.remove_css_class)("editing")

    def _clear_windows(self):
        """Minimize the open windows while widgets are edited, like Show Desktop;
        _restore_windows() brings them back, the focused one on top."""
        tracker = self.shell.toplevels
        self._hidden_windows = [t for t in tracker.toplevels if not t.minimized]
        self._hidden_windows.sort(key=lambda t: t.activated)
        for t in self._hidden_windows:
            t.minimize()
        tracker.flush()

    def _restore_windows(self):
        tracker = self.shell.toplevels
        for t in getattr(self, "_hidden_windows", []):
            if t in tracker.toplevels and t.minimized:
                t.activate()
        self._hidden_windows = []
        tracker.flush()

    def _build_gallery(self):
        """The gallery of edit mode: a compact bar at the bottom. One tab per
        group and one row of widgets that scrolls sideways, so it never grows
        over the desktop however many widgets there are."""
        titles = {"everyday": _("Everyday"), "productivity": _("Productivity"),
                  "system": _("System"), "developers": _("Developers"),
                  "gamers": _("Gamers")}
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       css_classes=["widget-gallery"], halign=Gtk.Align.CENTER,
                       valign=Gtk.Align.END, margin_bottom=104, margin_start=16,
                       margin_end=16, visible=False)
        head = Gtk.Box(spacing=12)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                       valign=Gtk.Align.CENTER)
        text.append(Gtk.Label(label=_("Widgets"), xalign=0,
                              css_classes=["widget-gallery-title"]))
        text.append(Gtk.Label(label=_("Click to add · drag to move · right-click to customize"),
                              xalign=0, css_classes=["widget-gallery-hint"],
                              ellipsize=Pango.EllipsizeMode.END))
        head.append(text)
        done = Gtk.Button(label=_("Done"), css_classes=["pill", "suggested-action"],
                          valign=Gtk.Align.CENTER)
        done.connect("clicked", lambda *_a: self.set_editing(False))
        head.append(done)
        card.append(head)

        stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                          transition_duration=160, hhomogeneous=True, vhomogeneous=True)
        tabs = Gtk.Box(spacing=6, css_classes=["widget-gallery-tabs"])
        tab_scroller = Gtk.ScrolledWindow(child=tabs, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                          hscrollbar_policy=Gtk.PolicyType.EXTERNAL)
        first = None
        for section, members in SECTIONS:
            tab = Gtk.ToggleButton(css_classes=["widget-gallery-tab", f"section-{section}"],
                                   group=first)
            inner = Gtk.Box(spacing=6)
            inner.append(Gtk.Box(css_classes=["widget-gallery-dot"], valign=Gtk.Align.CENTER))
            inner.append(Gtk.Label(label=titles[section]))
            tab.set_child(inner)
            tab.connect("toggled", lambda t, name=section: t.get_active()
                        and stack.set_visible_child_name(name))
            tabs.append(tab)
            if first is None:
                first = tab
            row = Gtk.Box(spacing=8, margin_bottom=4)
            for kind in members:
                title, icon, _cls = kinds()[kind]
                button = Gtk.Button(css_classes=["flat", "widget-gallery-item"],
                                    tooltip_text=_("Add {name}").format(name=title))
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
                badge = Gtk.Image(icon_name=icon, pixel_size=22,
                                  css_classes=["widget-gallery-icon", f"section-{section}"],
                                  halign=Gtk.Align.CENTER)
                inner.append(badge)
                inner.append(Gtk.Label(label=title, css_classes=["caption"],
                                       ellipsize=Pango.EllipsizeMode.END, max_width_chars=12))
                button.set_child(inner)
                button.connect("clicked", lambda _b, k=kind: self.add(k))
                row.append(button)
            scroller = Gtk.ScrolledWindow(child=row, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                          hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                          propagate_natural_height=True)
            # The wheel scrolls the row sideways.
            wheel = Gtk.EventControllerScroll(
                flags=Gtk.EventControllerScrollFlags.VERTICAL)
            wheel.connect("scroll", lambda _c, _dx, dy, sc=scroller: self._scroll_row(sc, dy))
            scroller.add_controller(wheel)
            stack.add_named(scroller, section)
        first.set_active(True)
        card.append(tab_scroller)
        card.append(stack)
        self._gallery_width(card)
        return card

    @staticmethod
    def _scroll_row(scroller, dy):
        adj = scroller.get_hadjustment()
        adj.set_value(adj.get_value() + dy * 60)
        return True

    def _gallery_width(self, card=None):
        """As wide as its contents need, but never wider than the screen allows."""
        card = card or self.gallery
        width, _height = self.area()
        card.set_size_request(min(760, max(320, width - 64)), -1)

    def show_menu(self, widget, x, y):
        if self._menu is not None:
            self._menu.unparent()
        pop = Gtk.Popover(has_arrow=False, css_classes=["aurora-context-menu"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, margin_top=3,
                      margin_bottom=3, margin_start=3, margin_end=3)
        entries = [(_("Edit Widgets…"), lambda: self.set_editing(True))]
        if widget.OPTIONS:
            entries.insert(0, (_("Customize…"), lambda: self.customize(widget)))
        for label, callback in (*entries,
                                (_("Remove Widget"), lambda: self.remove(widget)),
                                (_("Widget Settings…"),
                                 lambda: apps.spawn(["aurora-settings", "--page", "desktop"]))):
            button = Gtk.Button(label=label, css_classes=["flat", "context-action"])
            button.get_child().set_xalign(0)
            button.connect("clicked", lambda _b, cb=callback: (pop.popdown(), cb()))
            box.append(button)
        pop.set_child(box)
        pop.set_parent(widget)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        self._menu = pop
        pop.popup()

    def customize(self, widget):
        """A popover with the widget's own options, applied as they change."""
        pop = Gtk.Popover(css_classes=["widget-customize"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=12,
                      margin_bottom=12, margin_start=14, margin_end=14)
        box.append(Gtk.Label(label=kinds()[widget.kind][0], xalign=0,
                             css_classes=["widget-customize-title"]))
        for key, label, kind, _default, choices in widget.OPTIONS:
            row = Gtk.Box(spacing=16)
            row.append(Gtk.Label(label=_(label), xalign=0, hexpand=True))
            value = widget.option(key)
            if kind == "switch":
                control = Gtk.Switch(active=bool(value), valign=Gtk.Align.CENTER)
                control.connect("notify::active",
                                lambda sw, _p, k=key: widget.set_option(k, sw.get_active()))
            elif kind == "choice":
                values = [v for v, _l in choices]
                control = Gtk.DropDown.new_from_strings([_(l) for _v, l in choices])
                control.set_selected(values.index(value) if value in values else 0)
                control.connect("notify::selected", lambda dd, _p, k=key, vs=values:
                                widget.set_option(k, vs[dd.get_selected()]))
            elif kind == "text":
                control = Gtk.Entry(text=str(value), width_chars=16,
                                    placeholder_text=kinds()[widget.kind][0])
                control.connect("changed", lambda e, k=key: widget.set_option(k, e.get_text()))
            elif kind == "date":
                control = self._date_button(widget, key, value)
            else:  # folder
                control = Gtk.Button(label=os.path.basename(value) if value else _("Pictures"))
                control.connect("clicked", lambda b, k=key: self._pick_folder(widget, k, b))
            row.append(control)
            box.append(row)
        pop.set_child(box)
        pop.set_parent(widget)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()

    def _date_button(self, widget, key, value):
        """A button showing the date; it opens a calendar to pick another."""
        import datetime
        try:
            day = datetime.date.fromisoformat(str(value))
        except ValueError:
            day = datetime.date.today() + datetime.timedelta(days=30)
        button = Gtk.MenuButton(label=day.strftime("%x"))
        calendar = Gtk.Calendar()
        calendar.select_day(GLib.DateTime.new_local(day.year, day.month, day.day, 0, 0, 0))

        def picked(cal):
            d = cal.get_date()
            iso = f"{d.get_year():04d}-{d.get_month():02d}-{d.get_day_of_month():02d}"
            widget.set_option(key, iso)
            button.set_label(datetime.date.fromisoformat(iso).strftime("%x"))
            button.popdown()
        calendar.connect("day-selected", picked)
        button.set_popover(Gtk.Popover(child=calendar))
        return button

    def _pick_folder(self, widget, key, button):
        dialog = Gtk.FileDialog(title=_("Choose a Folder"))

        def done(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:
                return
            if folder is not None and folder.get_path():
                widget.set_option(key, folder.get_path())
                button.set_label(os.path.basename(folder.get_path()))
        dialog.select_folder(None, None, done)

    # style and schedules
    def _restyle(self):
        light = not Adw.StyleManager.get_default().get_dark()
        for widget in self.widgets:
            (widget.card.add_css_class if light else widget.card.remove_css_class)("light")
            widget.restyle()

    def _tick_all(self):
        for widget in self.widgets:
            widget.update()

    def _every_second(self):
        self._seconds += 1
        for widget in self.widgets:
            if widget.interval and self._seconds % widget.interval == 0:
                widget.update()
        return GLib.SOURCE_CONTINUE
