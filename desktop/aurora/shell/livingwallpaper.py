"""A background that moves — a photograph with light moving in it.

There is no way to draw a photograph: a scene made of lines and gradients
looks drawn, whatever is spent on it. So an animated background here is the
picture you already have with light added over it — curtains of aurora folding
across the sky of a night picture, stars coming and going, cloud crossing, the
water catching the light — and what is underneath stays a photograph.

The light is *added* (cairo's ADD operator), never painted on top: that is
what makes it read as light in the picture rather than as a shape over it, and
it is why the same layer works on a picture it was never made for.

It is cheap by construction. Everything is drawn into a surface a quarter of
the screen's size and scaled up — which is also where its softness comes from
— fifteen times a second, and nothing is drawn at all while a window covers
the desktop or the computer is saving power. The slow drift into the picture
("zoom") is a CSS animation on the picture itself, so GTK's renderer does all
of that one and the shell does none of it.

Settings → Appearance → Background → Movement.
"""

import math
import time

import cairo
from gi.repository import GLib, Gtk

from aurora import settings

SCALE = 4               # the light is drawn this much smaller, then scaled up
FRAME_MS = 66           # 15 frames a second: this moves slowly on purpose

# What can be added over a picture. Only the aurora so far: measured over the
# installed wallpaper, stars and cloud moved the picture by 0.08 of a grey
# level where the aurora moved it by 1.38 — which is a way of saying they were
# not there. They come back when they are worth looking at.
MOTIONS = ("off", "zoom", "aurora")
LAYERS = {"aurora": ("aurora",)}


def style():
    s = settings.get()
    value = s.get_string("wallpaper-animation") if s is not None else "aurora"
    return value if value in MOTIONS else "off"


def layers(name=None):
    """The light layers a motion is made of; none for "off" and "zoom"."""
    return LAYERS.get(name if name is not None else style(), ())


# --- the light ------------------------------------------------------------

def _rand(seed):
    """A fixed sequence: the same moment must look the same everywhere."""
    state = [seed * 2654435761 + 97]

    def nxt(n):
        state[0] = (state[0] * 1103515245 + 12345) % (1 << 31)
        return (state[0] >> 8) % n
    return nxt


def aurora_curtains(cr, width, height, phase, accent, sky=0.58):
    """Curtains of aurora over the top of the picture: each a comb of rays
    that folds as it drifts, green at the foot and violet at the crown.

    They fade out at their ends and at their feet, so none of them lands on
    the ground of the photograph."""
    curtains = (  # depth, colour at the foot, at the crown, centre, width, speed
        (0, (0.20, 1.00, 0.60), (0.70, 0.40, 1.00), 0.40, 0.78, 0.20),
        (1, (0.25, 0.95, 0.85), (0.95, 0.50, 0.95), 0.72, 0.56, 0.29),
        (2, (0.35, 1.00, 0.70), (0.60, 0.55, 1.00), 0.18, 0.44, 0.16))
    for depth, foot, crown, centre, span, speed in curtains:
        drift = phase * speed
        left, right = width * (centre - span / 2), width * (centre + span / 2)
        step = max(1.2, (right - left) / 90)
        cr.save()
        cr.set_operator(cairo.OPERATOR_ADD)
        x = left
        while x < right:
            across = (x - left) / max(1.0, right - left)
            fold = math.sin(across * 6.0 + drift) + 0.5 * math.sin(across * 15.0 - drift * 1.4)
            ray = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(across * 24.0 - drift * 2.2 + depth))
            edge = math.sin(math.pi * min(1.0, max(0.0, across))) ** 0.6
            top = height * (0.03 + 0.05 * depth) + fold * height * 0.05
            length = height * (sky - 0.08 - 0.05 * depth) + fold * height * 0.05
            strength = (0.20 - 0.05 * depth) * ray * edge
            if strength > 0.004:
                fade = cairo.LinearGradient(0, top, 0, top + length)
                fade.add_color_stop_rgba(0.0, *crown, 0.0)
                fade.add_color_stop_rgba(0.16, *crown, strength * 0.8)
                fade.add_color_stop_rgba(0.55, *foot, strength)
                fade.add_color_stop_rgba(1.0, *foot, 0.0)
                cr.set_source(fade)
                cr.rectangle(x, top, step * 1.4, length)
                cr.fill()
            x += step
        cr.restore()


PAINTERS = {"aurora": aurora_curtains}


def paint(names, cr, width, height, phase, accent, sky=0.58):
    """Add every layer of a motion over the picture, in order."""
    for name in names:
        painter = PAINTERS.get(name)
        if painter is not None:
            painter(cr, width, height, phase, accent, sky)


class LivingWallpaper(Gtk.DrawingArea):
    """The moving light. It sits over the picture and under everything else,
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
        drawing = bool(layers())
        wanted = drawing and self.get_mapped() and not self.covered() \
            and not self.saving_power()
        self.set_visible(drawing)
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
            return tuple(int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        except (ValueError, IndexError):
            return (0.66, 0.44, 1.0)

    def _draw(self, _area, cr, width, height):
        names = layers()
        if not names or width <= 0 or height <= 0:
            return
        phase = (time.monotonic() - self._started) * 0.6
        small = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                   max(1, width // SCALE), max(1, height // SCALE))
        paint(names, cairo.Context(small), width / SCALE, height / SCALE, phase,
              self._accent())
        cr.save()
        cr.scale(SCALE, SCALE)
        cr.set_source_surface(small, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_BILINEAR)
        cr.paint()
        cr.restore()
