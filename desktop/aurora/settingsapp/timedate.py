"""Date & Time: time zone, network time, clock format."""

from gi.repository import Adw, GLib

from aurora import settings
from aurora.i18n import _
from aurora.settingsapp.util import Page, combo_row, run, switch_row, toast


def timedate_props():
    out = run(["timedatectl", "show"])
    props = {}
    for line in out.splitlines():
        k, _s, v = line.partition("=")
        props[k] = v
    return props


class DateTime(Page):
    page_id = "datetime"
    title = _("Date & Time")
    icon_name = "preferences-system-time-symbolic"

    def build(self):
        props = timedate_props()
        g = self.group()
        self.now_row = Adw.ActionRow(title=_("Current time"))
        g.add(self.now_row)
        self._tick()
        GLib.timeout_add_seconds(1, self._tick)

        g.add(switch_row(_("Automatic date & time"), props.get("NTP") == "yes",
                         self._set_ntp, subtitle=_("Requires an internet connection")))

        zones = run(["timedatectl", "list-timezones"]).split() or ["UTC"]
        cur = props.get("Timezone", "UTC")
        self.zones = zones
        g.add(combo_row(_("Time zone"), [z.replace("_", " ") for z in zones],
                        zones.index(cur) if cur in zones else 0, search=True,
                        on_change=self._set_zone))

        aurora = settings.get()
        if aurora:
            g.add(switch_row(_("24-hour clock"), aurora.get_string("clock-format") == "24h",
                             lambda v: aurora.set_string("clock-format", "24h" if v else "12h")))

    def _tick(self):
        now = GLib.DateTime.new_now_local()
        self.now_row.set_subtitle(now.format("%c"))
        return GLib.SOURCE_CONTINUE

    def _set_zone(self, i):
        try:
            run(["timedatectl", "set-timezone", self.zones[i]], check=True)
        except RuntimeError as err:
            toast(self, str(err))

    def _set_ntp(self, enabled):
        try:
            run(["timedatectl", "set-ntp", "true" if enabled else "false"], check=True)
        except RuntimeError as err:
            toast(self, str(err))
