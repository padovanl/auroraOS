"""Settings → Screen Time: today's total, the last seven days as bars, each app's
time today with an optional daily limit (a reminder when it's reached)."""

import datetime
import json

from gi.repository import Adw, Gdk, Gtk, Pango

from aurora import apps, screentime, settings
from aurora.i18n import _
from aurora.settingsapp.util import Page, switch_row, toast

LIMITS = (0, 15, 30, 60, 120, 180)


def limit_labels():
    return [_("No limit"), _("15 min"), _("30 min"), _("1 hour"), _("2 hours"), _("3 hours")]


class ScreenTime(Page):
    page_id = "screentime"
    title = _("Screen Time")
    icon_name = "preferences-system-time-symbolic"

    def build(self):
        self.s = settings.get()
        head = self.group(_("Today"))
        self.total = Gtk.Label(xalign=0, css_classes=["title-1"])
        self.compare = Gtk.Label(xalign=0, css_classes=["dim-label"])
        self.chart = Gtk.DrawingArea(content_height=150, hexpand=True, margin_top=12)
        self.chart.set_draw_func(self._draw_week)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_bottom=8)
        for w in (self.total, self.compare, self.chart):
            box.append(w)
        head.add(box)
        self.apps_group = self.group(_("Apps today"),
                                     _("Set a daily limit and Aurora reminds you when it's "
                                       "reached."))
        self._rows = []
        if self.s is not None:
            privacy = self.group(_("Privacy"), _("Screen time stays on this computer. Days "
                                                 "older than five weeks are forgotten."))
            privacy.add(switch_row(_("Count screen time"), self.s.get_boolean("screen-time"),
                                   lambda v: self.s.set_boolean("screen-time", v)))
            clear = Adw.ButtonRow(title=_("Clear Screen Time History"))
            clear.add_css_class("destructive-action")
            clear.connect("activated", lambda *_a: (screentime.clear(), self.refresh(),
                                                    toast(self, _("History cleared"))))
            privacy.add(clear)
        self._week = []
        self.connect("map", lambda *_a: self.refresh())

    def refresh(self):
        today = datetime.date.today()
        usage = screentime.load(today)
        self._week = screentime.week(today)
        total = sum(usage.values())
        self.total.set_label(screentime.duration(total))
        past = [t for _d, t in self._week[:-1] if t]
        if past:
            average = sum(past) / len(past)
            self.compare.set_label(_("Daily average this week: {time}").format(
                time=screentime.duration(average)))
        else:
            self.compare.set_label(_("Screen time is counted while you use apps"))
        self.chart.queue_draw()

        for row in self._rows:
            self.apps_group.remove(row)
        self._rows = []
        limits = screentime.limits(self.s.get_string("screen-time-limits")) if self.s else {}
        ranked = screentime.top(usage)
        for app_id, seconds in ranked[:15]:
            info = apps.find_app(app_id)
            row = Adw.ActionRow(title=info.get_display_name() if info else app_id,
                                subtitle=screentime.duration(seconds))
            icon = Gtk.Image(pixel_size=32)
            if info is not None and info.get_icon() is not None:
                icon.set_from_gicon(info.get_icon())
            else:
                icon.set_from_icon_name("application-x-executable")
            row.add_prefix(icon)
            current = limits.get(app_id, 0)
            limit = Gtk.DropDown.new_from_strings(limit_labels())
            limit.set_valign(Gtk.Align.CENTER)
            limit.set_selected(LIMITS.index(current) if current in LIMITS else 0)
            limit.connect("notify::selected", lambda d, _p, a=app_id: self._set_limit(
                a, LIMITS[d.get_selected()]))
            row.add_suffix(limit)
            self.apps_group.add(row)
            self._rows.append(row)
        if not ranked:
            empty = Adw.ActionRow(title=_("Nothing yet today"))
            self.apps_group.add(empty)
            self._rows.append(empty)

    def _set_limit(self, app_id, minutes):
        if self.s is None:
            return
        current = screentime.limits(self.s.get_string("screen-time-limits"))
        if minutes:
            current[app_id] = minutes
        else:
            current.pop(app_id, None)
        self.s.set_string("screen-time-limits", json.dumps(current))

    def _draw_week(self, area, cr, width, height):
        """Seven bars, today's in the accent color, with day names under them."""
        from gi.repository import PangoCairo
        fg = area.get_color()
        accent = Gdk.RGBA()
        from aurora.look import ACCENT_HEX
        iface = settings.interface()
        accent.parse(ACCENT_HEX.get(iface.get_string("accent-color"), "#a970ff")
                     if iface else "#a970ff")
        if not self._week:
            return
        label_h = 18
        top = max(max(t for _d, t in self._week), 3600)
        n = len(self._week)
        slot = width / n
        bar_w = min(slot * 0.55, 46)
        for i, (day, total) in enumerate(self._week):
            h = (height - label_h - 6) * total / top
            x = i * slot + (slot - bar_w) / 2
            y = height - label_h - h
            today = i == n - 1
            if today:
                cr.set_source_rgba(accent.red, accent.green, accent.blue, 1)
            else:
                cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.22)
            radius = min(6, bar_w / 2, h / 2) if h > 0 else 0
            if h > 0:
                cr.new_sub_path()
                cr.arc(x + bar_w - radius, y + radius, radius, -1.5708, 0)
                cr.line_to(x + bar_w, y + h)
                cr.line_to(x, y + h)
                cr.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
                cr.close_path()
                cr.fill()
            layout = PangoCairo.create_layout(cr)
            layout.set_text(day.strftime("%a"), -1)
            desc = Pango.FontDescription.from_string("Sans 9")
            layout.set_font_description(desc)
            w, _h = layout.get_pixel_size()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 1 if today else 0.6)
            cr.move_to(i * slot + (slot - w) / 2, height - label_h + 2)
            PangoCairo.show_layout(cr, layout)
