"""Date & Time: automatic/manual time, time zone and clock format."""
from gi.repository import Adw, GLib, Gtk

from aurora import settings
from aurora.i18n import _
from aurora.popovers import ContextMenu
from aurora.settingsapp.util import Page, apply_async, combo_row, run, switch_row, toast


def timedate_props():
    props = {}
    for line in run(["timedatectl", "show"]).splitlines():
        k, _s, v = line.partition("=")
        props[k] = v
    return props


class DateTime(Page):
    page_id = "datetime"
    title = _("Date & Time")
    icon_name = "preferences-system-time-symbolic"

    def build(self):
        props = timedate_props()
        self._clock_source = 0
        self._command_pending = False
        g = self.group()
        self.now_row = Adw.ActionRow(title=_("Current time"))
        g.add(self.now_row)
        self._tick()
        self.connect("realize", self._start_clock)
        self.connect("unrealize", self._stop_clock)

        self._ntp = props.get("NTP") == "yes"
        self.ntp_row = switch_row(_("Automatic date & time"), self._ntp, self._set_ntp,
                                  subtitle=_("Requires an internet connection"))
        g.add(self.ntp_row)
        self.zones = run(["timedatectl", "list-timezones"]).split() or ["UTC"]
        cur = props.get("Timezone", "UTC")
        self._zone_index = self.zones.index(cur) if cur in self.zones else 0
        self.zone_row = combo_row(_("Time zone"), [z.replace("_", " ") for z in self.zones],
                                  self._zone_index, search=True, on_change=self._set_zone)
        g.add(self.zone_row)
        aurora = settings.get()
        if aurora:
            g.add(switch_row(_("24-hour clock"), aurora.get_string("clock-format") == "24h",
                             lambda v: aurora.set_string("clock-format", "24h" if v else "12h")))

        self.manual_group = self.group(_("Set Date and Time"),
                                        _("Turn off automatic date & time to set the clock manually."))
        self.calendar = Gtk.Calendar()
        popover = ContextMenu(child=self.calendar)
        self.date_button = Gtk.MenuButton(popover=popover, valign=Gtk.Align.CENTER)
        self.calendar.connect("day-selected", lambda *_a: self._date_label())
        self._date_label()
        date_row = Adw.ActionRow(title=_("Date"))
        date_row.add_suffix(self.date_button)
        self.manual_group.add(date_row)
        now = GLib.DateTime.new_now_local()
        self.hour = Gtk.SpinButton.new_with_range(0, 23, 1)
        self.minute = Gtk.SpinButton.new_with_range(0, 59, 1)
        self.hour.set_value(now.get_hour())
        self.minute.set_value(now.get_minute())
        for spin in (self.hour, self.minute):
            spin.set_numeric(True)
            spin.set_valign(Gtk.Align.CENTER)
        time_row = Adw.ActionRow(title=_("Time"), subtitle=_("Hours and minutes, in 24-hour format"))
        time_row.add_suffix(self.hour)
        time_row.add_suffix(Gtk.Label(label=":"))
        time_row.add_suffix(self.minute)
        self.manual_group.add(time_row)
        self.apply_button = Adw.ButtonRow(title=_("Apply Date and Time"))
        self.apply_button.connect("activated", lambda *_a: self._apply_time())
        self.manual_group.add(self.apply_button)
        self.manual_group.set_sensitive(not self._ntp)

    def _date_label(self):
        self.date_button.set_label(self.calendar.get_date().format("%x"))

    def _start_clock(self, *_args):
        self._tick()
        if not self._clock_source:
            self._clock_source = GLib.timeout_add_seconds(1, self._tick)

    def _stop_clock(self, *_args):
        if self._clock_source:
            GLib.source_remove(self._clock_source)
            self._clock_source = 0

    def _tick(self):
        self.now_row.set_subtitle(GLib.DateTime.new_now_local().format("%c"))
        return GLib.SOURCE_CONTINUE

    def _change(self, args, completed):
        def finish(error):
            completed(error)
            if error:
                toast(self, error)
        apply_async(self, lambda: run(["timedatectl", *args], check=True, timeout=300), finish)

    def _set_zone(self, i):
        if self._command_pending or i == self._zone_index:
            return

        def finish(error):
            if error:
                self.zone_row.set_selected(self._zone_index)
            else:
                self._zone_index = i
        self._change(["set-timezone", self.zones[i]], finish)

    def _set_ntp(self, enabled):
        if self._command_pending or enabled == self._ntp:
            return

        def finish(error):
            if error:
                self.ntp_row.set_active(self._ntp)
            else:
                self._ntp = enabled
            self.manual_group.set_sensitive(not self._ntp)
        self._change(["set-ntp", "true" if enabled else "false"], finish)

    def _apply_time(self):
        if self._ntp or self._command_pending:
            return
        self.hour.update()
        self.minute.update()
        value = (self.calendar.get_date().format("%Y-%m-%d") +
                 f" {self.hour.get_value_as_int():02}:{self.minute.get_value_as_int():02}:00")

        def finish(error):
            if not error:
                self._tick()
                toast(self, _("Date and time updated"))
        self._change(["set-time", value], finish)
