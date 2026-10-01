"""Counts screen time for the app in front of you (see aurora.screentime) and
reminds you once when an app passes the daily limit you set for it."""

import datetime
import subprocess

from gi.repository import GLib

from aurora import apps, screentime, settings
from aurora.i18n import _

TICK_S = 30


def locked():
    """The lock screen is up."""
    try:
        return subprocess.run(["pgrep", "-x", "gtklock"], capture_output=True,
                              timeout=2).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class ScreenTimeTracker:
    def __init__(self, shell):
        self.shell = shell
        self.day = datetime.date.today()
        self.usage = screentime.load(self.day)
        self.reminded = set()
        screentime.prune(self.day)
        GLib.timeout_add_seconds(TICK_S, self._tick)

    def _focused(self):
        for t in self.shell.toplevels.toplevels:
            if t.activated and not t.minimized:
                return t.app_id
        return None

    def _tick(self):
        s = settings.get()
        if s is not None and not s.get_boolean("screen-time"):
            return GLib.SOURCE_CONTINUE
        today = datetime.date.today()
        if today != self.day:
            self.day, self.usage, self.reminded = today, screentime.load(today), set()
        app = self._focused()
        if app and not locked():
            self.usage = screentime.add(today, app, TICK_S, self.usage)
            try:
                screentime.save(today, self.usage)
            except OSError:
                pass
            self._check_limits(s)
        return GLib.SOURCE_CONTINUE

    def _check_limits(self, s):
        if s is None:
            return
        app_limits = screentime.limits(s.get_string("screen-time-limits"))
        for app_id in screentime.over_limit(self.usage, app_limits):
            if app_id in self.reminded:
                continue
            self.reminded.add(app_id)
            info = apps.find_app(app_id)
            name = info.get_display_name() if info else app_id
            self.shell.notifications.notify(
                _("Screen Time"), 0, "preferences-system-time-symbolic",
                _("Time's up for {app}").format(app=name),
                _("You've used it for {time} today, your daily limit.").format(
                    time=screentime.duration(self.usage.get(app_id, 0))),
                [], {}, -1)
