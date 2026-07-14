"""Power: screen blanking, lock, power profile, battery."""

import shutil
import subprocess

from gi.repository import Adw

from aurora import settings
from aurora.i18n import _, ngettext
from aurora.settingsapp.util import Page, combo_row, run, switch_row

BLANK_MINUTES = [1, 2, 3, 5, 10, 15, 30, 0]
PROFILES = [("power-saver", _("Power Saver")), ("balanced", _("Balanced")),
            ("performance", _("Performance"))]


def restart_idle():
    subprocess.run(["pkill", "-x", "swayidle"], check=False)
    subprocess.Popen(["aurora-idle"], start_new_session=True)


class Power(Page):
    page_id = "power"
    title = _("Power")
    icon_name = "battery-good-symbolic"

    def build(self):
        aurora = settings.get()
        g = self.group(_("Screen"))
        if aurora:
            labels = [ngettext("{n} minute", "{n} minutes", m).format(n=m) if m else _("Never")
                      for m in BLANK_MINUTES]
            cur = aurora.get_int("idle-dim-minutes")
            idx = BLANK_MINUTES.index(cur) if cur in BLANK_MINUTES else 3

            def set_blank(i):
                aurora.set_int("idle-dim-minutes", BLANK_MINUTES[i])
                restart_idle()

            def set_lock(v):
                aurora.set_boolean("idle-lock", v)
                restart_idle()

            g.add(combo_row(_("Screen blank"), labels, idx, on_change=set_blank,
                            subtitle=_("Turn the screen off after a period of inactivity")))
            g.add(switch_row(_("Automatic screen lock"), aurora.get_boolean("idle-lock"),
                             set_lock))

        if shutil.which("powerprofilesctl"):
            p = self.group(_("Power mode"))
            cur = run(["powerprofilesctl", "get"]).strip()
            ids = [x[0] for x in PROFILES]
            p.add(combo_row(_("Power mode"), [x[1] for x in PROFILES],
                            ids.index(cur) if cur in ids else 1,
                            on_change=lambda i: run(["powerprofilesctl", "set", ids[i]])))

        bat = self._battery()
        if bat:
            b = self.group(_("Battery"))
            b.add(Adw.ActionRow(title=_("Charge"), subtitle=bat))

    def _battery(self):
        out = run(["upower", "-i", "/org/freedesktop/UPower/devices/DisplayDevice"])
        info = {}
        for line in out.splitlines():
            k, sep, v = line.strip().partition(":")
            if sep:
                info[k.strip()] = v.strip()
        if info.get("power supply") == "yes" or info.get("percentage") and \
                info.get("state") not in (None, "unknown"):
            return f"{info.get('percentage', '?')} · {info.get('state', '')}"
        return None
