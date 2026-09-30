"""Things that follow the sun: dynamic wallpaper, automatic dark style, Night Light.

Checks once a minute where the sun is (aurora.sun, location from the time
zone) and:
- picks the dynamic wallpaper for the part of the day (dawn, day, dusk, night);
- switches the color scheme at sunrise and sunset when "Auto" is chosen;
- runs wlsunset with the schedule chosen for Night Light.

It also keeps ~/.cache/aurora/wallpaper pointing to the picture on screen, so
the lock screen shows the same background.
"""

import os
import shutil
import subprocess
import time

from gi.repository import GLib, GObject

from aurora import settings, sun

BACKGROUNDS = "/usr/share/backgrounds/aurora"
DEFAULT_WALLPAPER = os.path.join(BACKGROUNDS, "aurora-dawn.png")
PHASES = ("dawn", "day", "dusk", "night")


def dynamic_path(phase):
    return os.path.join(BACKGROUNDS, f"aurora-dynamic-{phase}.png")


def cache_link():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aurora", "wallpaper")


class DayCycle(GObject.Object):
    __gsignals__ = {"wallpaper-changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self.location = sun.location()
        self.phase = sun.phase(loc=self.location)
        self._night_light = None
        self._night_args = None
        self._slide_started = time.monotonic()
        self._slide_index = 0
        s = settings.get()
        if s:
            for key in ("wallpaper", "wallpaper-dynamic", "wallpaper-slideshow",
                        "wallpaper-slideshow-minutes", "wallpaper-slideshow-folder",
                        "wallpaper-slideshow-shuffle", "wallpaper-daily"):
                s.connect(f"changed::{key}", lambda *a: self._wallpaper_changed())
            s.connect("changed::wallpaper-daily", lambda *a: self._fetch_daily())
            s.connect("changed::color-scheme-auto", lambda *a: self._sync_scheme())
            for key in ("night-light", "night-light-schedule", "night-light-from",
                        "night-light-to", "night-light-temperature"):
                s.connect(f"changed::{key}", lambda *a: self.sync_night_light())
        self._sync_scheme()
        self.sync_night_light()
        self._update_link()
        GLib.timeout_add_seconds(60, self._tick)
        GLib.timeout_add_seconds(20, lambda: self._fetch_daily() or False)

    # --- wallpaper ---

    def wallpaper(self):
        """The picture to show now."""
        s = settings.get()
        if s is not None and s.get_boolean("wallpaper-slideshow"):
            pictures = self._slides()
            if pictures:
                return pictures[self._slide_index % len(pictures)]
        if s is not None and s.get_string("wallpaper-daily"):
            from aurora import dailypicture
            info = dailypicture.latest(s.get_string("wallpaper-daily"))
            if info:
                return info["path"]
        if s is None or s.get_boolean("wallpaper-dynamic"):
            path = dynamic_path(self.phase)
            if os.path.exists(path):
                return path
        path = s.get_string("wallpaper") if s else ""
        for candidate in (path, DEFAULT_WALLPAPER):
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    @staticmethod
    def _slides():
        """The slideshow's pictures: the chosen folder (and its subfolders), else
        the included gallery; shuffled in a stable order when asked."""
        s = settings.get()
        folder = (s.get_string("wallpaper-slideshow-folder") if s else "") or BACKGROUNDS
        found = []
        for root, _dirs, names in os.walk(folder):
            found += [os.path.join(root, name) for name in names
                      if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                      and not name.startswith("aurora-dynamic-")]
            if len(found) > 5000:
                break
        found.sort()
        if s is not None and s.get_boolean("wallpaper-slideshow-shuffle"):
            import random
            random.Random(len(found)).shuffle(found)
        return found

    def _wallpaper_changed(self):
        self._update_link()
        self.emit("wallpaper-changed")

    def _update_link(self):
        path, link = self.wallpaper(), cache_link()
        if path is None:
            return
        try:
            os.makedirs(os.path.dirname(link), exist_ok=True)
            tmp = link + ".new"
            if os.path.lexists(tmp):
                os.remove(tmp)
            os.symlink(path, tmp)
            os.replace(tmp, link)
        except OSError:
            pass

    # --- the clock ---

    def _tick(self):
        # Re-read the time zone: the user may have changed it in Settings.
        self.location = sun.location()
        phase = sun.phase(loc=self.location)
        if phase != self.phase:
            self.phase = phase
            s = settings.get()
            if s is None or s.get_boolean("wallpaper-dynamic"):
                self._wallpaper_changed()
        s = settings.get()
        if s is not None and s.get_boolean("wallpaper-slideshow"):
            interval = max(5, s.get_int("wallpaper-slideshow-minutes")) * 60
            if time.monotonic() - self._slide_started >= interval:
                self._slide_started = time.monotonic()
                self._slide_index += 1
                self._wallpaper_changed()
        self._fetch_daily()
        self._sync_scheme()
        return GLib.SOURCE_CONTINUE

    # --- picture of the day ---

    def _fetch_daily(self):
        """Get today's picture once a day, in the background, then show it."""
        s = settings.get()
        source = s.get_string("wallpaper-daily") if s else ""
        if not source or getattr(self, "_daily_busy", False):
            return
        from aurora import dailypicture
        if dailypicture.cached(source) is not None:
            return
        # Offline or refused: try again in an hour, not every minute.
        if time.monotonic() - getattr(self, "_daily_tried", -3600) < 3600 \
                and getattr(self, "_daily_source", None) == source:
            return
        self._daily_busy, self._daily_tried, self._daily_source = True, time.monotonic(), source
        import threading

        def work():
            try:
                dailypicture.fetch(source)
                ok = True
            except Exception as err:  # noqa: BLE001 - network, format, no picture today
                print(f"aurora: picture of the day unavailable: {err}")
                ok = False
            GLib.idle_add(done, ok)

        def done(ok):
            self._daily_busy = False
            if ok:
                self._wallpaper_changed()
            return False
        threading.Thread(target=work, daemon=True).start()

    # --- automatic dark style ---

    def _sync_scheme(self):
        s, iface = settings.get(), settings.interface()
        if s is None or iface is None or not s.get_boolean("color-scheme-auto"):
            return
        want = "prefer-dark" if sun.is_dark(loc=self.location) else "default"
        if iface.get_string("color-scheme") != want:
            iface.set_string("color-scheme", want)

    # --- Night Light ---

    def night_light_args(self):
        """wlsunset arguments for the current settings, or None when off."""
        s = settings.get()
        if s is None or not s.get_boolean("night-light"):
            return None
        temp = s.get_int("night-light-temperature")
        schedule = s.get_string("night-light-schedule")
        if schedule == "always":
            # Day and night temperatures one kelvin apart: warm all the time.
            return ["-t", str(temp), "-T", str(temp + 1)]
        args = ["-t", str(temp), "-T", "6500"]
        if schedule == "sunset" and self.location is not None:
            lat, lon = self.location
            return args + ["-l", f"{lat:.2f}", "-L", f"{lon:.2f}"]
        return args + ["-s", s.get_string("night-light-from") or "20:00",
                       "-S", s.get_string("night-light-to") or "07:00"]

    def sync_night_light(self):
        args = self.night_light_args()
        if args == self._night_args and (args is None or self._night_light is not None):
            return
        if self._night_light is not None:
            self._night_light.terminate()
            self._night_light = None
        self._night_args = args
        if args is not None and shutil.which("wlsunset"):
            self._night_light = subprocess.Popen(["wlsunset"] + args)
