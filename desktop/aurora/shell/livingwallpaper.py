"""A background that moves: the aurora itself, drifting over the picture.

Drawn with Cairo, not a GPU shader, because Aurora renders in software in a
virtual machine and a shader would be a slide show there. It is cheap by
construction: the ribbons are drawn into a surface a quarter of the screen's
size and scaled up — which is what gives them their softness as well — at
fifteen frames a second, and nothing is drawn at all while a window covers the
desktop, so it costs nothing while you work.

Two kinds: "aurora", bands of light leaning across the top of the screen, drawn
here, and "zoom", a very slow drift into the picture, which is a CSS animation
on the picture itself and costs us nothing at all. Settings → Appearance →
Background → Movement.
"""

import math
import time

import cairo
from gi.repository import GLib, Gtk

from aurora import settings

SCALE = 4               # the ribbons are drawn this much smaller, then scaled up
FRAME_MS = 66           # 15 frames a second: this moves slowly on purpose
RIBBONS = 4


def style():
    s = settings.get()
    value = s.get_string("wallpaper-animation") if s is not None else "aurora"
    return value if value in ("off", "aurora", "zoom") else "off"


def ribbon(phase, index, width, height):
    """The points of one band of light, left to right across the screen."""
    points = []
    base = height * (0.16 + 0.11 * index)
    swing = height * (0.05 + 0.02 * index)
    speed = 0.25 + 0.08 * index
    for step in range(25):
        x = width * step / 24
        angle = phase * speed + step * 0.42 + index * 1.7
        y = base + math.sin(angle) * swing + math.sin(angle * 0.37 + index) * swing * 0.5
        points.append((x, y))
    return points


class LivingWallpaper(Gtk.DrawingArea):
    """The moving layer. It sits over the picture and under everything else,
    takes no input, and stops itself whenever it cannot be seen."""

    def __init__(self, shell):
        super().__init__(can_target=False, hexpand=True, vexpand=True)
        self.shell = shell
        self.set_draw_func(self._draw)
        self._tick = 0
        self._last = 0.0
        self._started = time.monotonic()
        s = settings.get()
        if s is not None:
            s.connect("changed::wallpaper-animation", lambda *_a: self.refresh())
            s.connect("changed::accent-color", lambda *_a: self.queue_draw())
        shell.toplevels.connect("changed", lambda *_a: self.refresh())
        self.connect("map", lambda *_a: self.refresh())
        self.connect("unmap", lambda *_a: self._stop())
        self.refresh()

    # --- when it runs ---

    def covered(self):
        """A maximized or fullscreen window: there is no desktop to look at."""
        for window in getattr(self.shell.toplevels, "toplevels", []):
            if window.minimized:
                continue
            if window.fullscreen or window.maximized:
                return True
        return False

    def saving_power(self):
        profiles = getattr(self.shell, "power_profiles", None)
        active = getattr(profiles, "active", None) if profiles is not None else None
        return active == "power-saver"

    def refresh(self):
        wanted = style() == "aurora" and self.get_mapped() and not self.covered() \
            and not self.saving_power()
        self.set_visible(style() == "aurora")
        if wanted and not self._tick:
            self._last = 0.0
            self._tick = self.add_tick_callback(self._frame)
        elif not wanted:
            self._stop()
        self.queue_draw()

    def _stop(self):
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0

    def _frame(self, _widget, clock):
        now = clock.get_frame_time() / 1000.0        # microseconds to milliseconds
        if now - self._last < FRAME_MS:
            return GLib.SOURCE_CONTINUE
        self._last = now
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    # --- what it draws ---

    def _accent(self):
        from aurora import look
        colour = look.accent_hex()
        try:
            r = int(colour[1:3], 16) / 255
            g = int(colour[3:5], 16) / 255
            b = int(colour[5:7], 16) / 255
        except (ValueError, IndexError):
            r, g, b = 0.66, 0.44, 1.0
        return r, g, b

    def _draw(self, _area, cr, width, height):
        if style() != "aurora" or width <= 0 or height <= 0:
            return
        phase = (time.monotonic() - self._started) * 0.6
        small = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                   max(1, width // SCALE), max(1, height // SCALE))
        inner = cairo.Context(small)
        self._draw_ribbons(inner, width / SCALE, height / SCALE, phase)
        cr.save()
        cr.scale(SCALE, SCALE)
        cr.set_source_surface(small, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_BILINEAR)
        cr.paint()
        cr.restore()

    def _draw_ribbons(self, cr, width, height, phase):
        r, g, b = self._accent()
        for index in range(RIBBONS):
            points = ribbon(phase, index, width, height)
            cr.move_to(*points[0])
            for i in range(1, len(points) - 1):
                x0, y0 = points[i]
                x1, y1 = points[i + 1]
                cr.curve_to(x0, y0, x0, y0, (x0 + x1) / 2, (y0 + y1) / 2)
            thickness = height * (0.12 + 0.035 * index)
            fade = cairo.LinearGradient(0, 0, 0, height)
            alpha = 0.22 - index * 0.03
            # The far end of each band leans towards the accent, the near end
            # towards the green an aurora actually is.
            fade.add_color_stop_rgba(0.0, r, g, b, 0.0)
            fade.add_color_stop_rgba(0.45, r, g, b, max(0.03, alpha))
            fade.add_color_stop_rgba(1.0, 0.35, 0.95, 0.75, 0.0)
            cr.set_source(fade)
            cr.set_line_width(thickness)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.stroke()
