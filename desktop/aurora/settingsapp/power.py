"""Power: screen blanking, lock, power profile, battery and battery health."""

import glob
import os
import shutil
import subprocess

from gi.repository import Adw

from aurora import settings
from aurora.i18n import N_, _, ngettext
from aurora.settingsapp.util import Page, apply_async, combo_row, run, switch_row, toast

LIMIT_FILE = "/etc/aurora/battery-limit"


def charge_limit_supported():
    """Laptops whose firmware lets the OS stop charging early (ThinkPad, ASUS,
    Dell, Framework, Huawei, LG, Samsung, System76…)."""
    return bool(glob.glob("/sys/class/power_supply/BAT*/charge_control_end_threshold"))


def charge_limit_on():
    return os.path.exists(LIMIT_FILE)

BLANK_MINUTES = [1, 2, 3, 5, 10, 15, 30, 0]
SUSPEND_MINUTES = [5, 10, 15, 20, 30, 45, 60, 90, 120, 0]
LOGIND_CONF = "/etc/systemd/logind.conf.d/50-aurora.conf"
POWER_KEY = [("poweroff", N_("Power Off")), ("suspend", N_("Suspend")),
             ("hibernate", N_("Hibernate")), ("ignore", N_("Nothing"))]
LID = [("suspend", N_("Suspend")), ("ignore", N_("Nothing"))]


def logind_value(key, default):
    try:
        with open(LOGIND_CONF) as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and k == key:
                    return v
    except OSError:
        pass
    return default


def has_lid():
    return bool(glob.glob("/proc/acpi/button/lid/*"))
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

            sus = self.group(_("Automatic Suspend"),
                             _("Suspend the computer when it has not been used for a while."))
            labels = [ngettext("{n} minute", "{n} minutes", m).format(n=m) if m else _("Never")
                      for m in SUSPEND_MINUTES]

            def suspend_row(title, key):
                cur = aurora.get_int(key)

                def changed(i):
                    aurora.set_int(key, SUSPEND_MINUTES[i])
                    restart_idle()
                return combo_row(title, labels, SUSPEND_MINUTES.index(cur)
                                 if cur in SUSPEND_MINUTES else len(SUSPEND_MINUTES) - 1,
                                 on_change=changed)
            if self._battery():
                sus.add(suspend_row(_("On battery"), "suspend-battery-minutes"))
            sus.add(suspend_row(_("When plugged in"), "suspend-ac-minutes"))

        buttons = self.group(_("Power Button and Lid"))
        ids = [k for k, _l in POWER_KEY]
        cur = logind_value("HandlePowerKey", "poweroff")
        self._power_index = ids.index(cur) if cur in ids else 0
        self.power_row = combo_row(_("Power button"), [_(label) for _k, label in POWER_KEY],
                                   self._power_index,
                                   on_change=lambda i: self._logind("power-key", i))
        buttons.add(self.power_row)
        if has_lid():
            lid_ids = [k for k, _l in LID]
            cur = logind_value("HandleLidSwitch", "suspend")
            self._lid_index = lid_ids.index(cur) if cur in lid_ids else 0
            self.lid_row = combo_row(_("Closing the lid"), [_(label) for _k, label in LID],
                                     self._lid_index,
                                     on_change=lambda i: self._logind("lid", i))
            buttons.add(self.lid_row)

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
            if aurora:
                b.add(switch_row(_("Show battery percentage"),
                                 aurora.get_boolean("show-battery-percentage"),
                                 lambda v: aurora.set_boolean("show-battery-percentage", v),
                                 subtitle=_("Next to the battery icon in the top bar")))
                levels = (0, 10, 20, 30, 50)
                cur = aurora.get_int("battery-saver-threshold")
                b.add(combo_row(_("Turn on Battery Saver"),
                                [_("Never"), _("At 10%"), _("At 20%"), _("At 30%"), _("At 50%")],
                                levels.index(cur) if cur in levels else 2,
                                subtitle=_("Power Saver mode on battery below this charge, "
                                           "off again when you plug in"),
                                on_change=lambda i: aurora.set_int("battery-saver-threshold",
                                                                   levels[i])))
            health = self._health()
            if health:
                b.add(Adw.ActionRow(title=_("Battery health"), subtitle=health))
            if charge_limit_supported():
                self._limit_on = charge_limit_on()
                self.limit_row = switch_row(_("Limit charging to 80%"), self._limit_on, self._set_limit,
                                 subtitle=_("Keeping a battery below full makes it last years "
                                            "longer. Turn off before a trip for a full charge."))
                b.add(self.limit_row)

    def _admin_change(self, control, what, value, completed):
        from aurora.settingsapp.system import admin

        def work():
            ok, err = admin(what, value)
            if not ok:
                raise RuntimeError(err)

        def finish(error):
            completed(error)
            if error:
                toast(self, error)
        apply_async(control, work, finish)

    def _logind(self, what, index):
        row, attr, choices = ((self.power_row, "_power_index", POWER_KEY) if what == "power-key"
                              else (self.lid_row, "_lid_index", LID))
        if getattr(row, "_command_pending", False) or index == getattr(self, attr):
            return

        def finish(error):
            if error:
                row.set_selected(getattr(self, attr))
            else:
                setattr(self, attr, index)
        self._admin_change(row, what, choices[index][0], finish)

    def _health(self):
        out = run(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"])
        for line in out.splitlines():
            k, sep, v = line.strip().partition(":")
            if sep and k.strip() == "capacity":
                return _("{pct} of its original capacity").format(pct=v.strip())
        return None

    def _set_limit(self, on):
        if getattr(self.limit_row, "_command_pending", False) or on == self._limit_on:
            return

        def finish(error):
            if error:
                self.limit_row.set_active(self._limit_on)
            else:
                self._limit_on = on
                toast(self, _("Charging stops at 80%") if on else _("Charging to 100%"))
        self._admin_change(self.limit_row, "battery-limit", "80" if on else "off", finish)

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
