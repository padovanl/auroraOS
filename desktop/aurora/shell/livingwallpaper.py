"""Looping video wallpapers and optional light effects for static pictures.

Videos use Gtk.MediaFile/GStreamer, cover the screen, loop silently and pause
when covered or saving power. Posters keep thumbnails and the lock screen
static. Only the selected video is opened, and unmapping closes its decoder.

There is no way to draw a photograph: a scene made of lines and gradients
looks drawn, whatever is spent on it. So an animated background here is the
picture you already have with light added over it — curtains of aurora folding
across the sky of a night picture, stars coming and going, cloud crossing, the
water catching the light — and what is underneath stays a photograph.

The light is *added* (cairo's ADD operator), never painted on top: that is
what makes it read as light in the picture rather than as a shape over it, and
it is why the same layer works on a picture it was never made for.

Light is drawn at a quarter of the screen's size, fifteen times a second.
Water also moves in the photograph itself, at its original resolution.
The desktop pauses both effects and slow zoom while covered or saving power.
Settings shows the same renderer in its live preview.

Settings → Appearance → Background → Movement.
"""

import math
import os
import time

import cairo
from gi.repository import GdkPixbuf, GLib, Gtk

from aurora import settings, wallpapers

SCALE = 4               # the light is drawn this much smaller, then scaled up
FRAME_MS = 66           # 15 frames a second: this moves slowly on purpose

# What can be added over a picture. "auto" is the one to leave it on: the
# light that suits the picture, taken from the table below, which is the only
# way an aurora does not end up drawn over a photograph of a nebula.
MOTIONS = ("off", "auto", "zoom", "aurora", "stars", "clouds", "shimmer")
LAYERS = {
    "aurora": ("aurora",),
    "stars": ("stars",),
    "clouds": ("clouds",),
    "shimmer": ("shimmer",),
}

# Each picture Aurora installs, and what moves in it. "sky" is how far down
# the sky goes, "water" where the water starts, "sun" where the light comes
# from — all as a fraction of the picture, read off the picture itself.
PICTURES = {
    "aurora-northern-lights": {"layers": ("aurora", "stars", "shimmer"),
                               "sky": 0.52, "water": 0.81, "ripple": 0.81,
                               "ripple_strength": 0.003},
    "aurora-wave": {"layers": ("clouds", "shimmer"), "sky": 0.42, "water": 0.80,
                    "sun": (0.91, 0.50), "ripple": 0.72, "ripple_strength": 0.006},
    "aurora-nebula": {"layers": ("breathe", "stars"), "sky": 1.0,
                      "hearts": ((0.33, 0.46), (0.62, 0.40), (0.78, 0.62))},
    "aurora-milky-way": {"layers": ("stars", "meteor", "shimmer"),
                         "sky": 0.57, "water": 0.80, "ripple": 0.80,
                         "ripple_strength": 0.002},
    "aurora-sunrise": {"layers": ("rays", "clouds"), "sky": 0.40,
                       "sun": (0.32, 0.31)},
    "aurora-ringed-planet": {"layers": ("stars", "glint"), "sky": 0.35,
                             "sun": (0.27, 0.34)},
}
# The original day-cycle landscapes also keep their automatic movement.
for _series in ("starfall", "veil", "horizon"):
    for _phase in ("dawn", "day", "dusk", "night"):
        PICTURES[f"aurora-{_series}-{_phase}"] = {
            "layers": ("aurora", "stars") if _phase == "night" else ("clouds",),
            "sky": 0.50,
        }
# Auto leaves personal photographs and solid colours still.
UNKNOWN = {"layers": (), "sky": 0.55}


def style():
    s = settings.get()
    value = s.get_string("wallpaper-animation") if s is not None else "auto"
    return value if value in MOTIONS else "off"


def picture_key(path=None):
    """The name of the picture on the desktop, without folder or suffix: the
    key into the table of what moves in which picture."""
    if path is None:
        s = settings.get()
        if s is None:
            return ""
        if s.get_boolean("wallpaper-dynamic"):
            from aurora.shell.daycycle import dynamic_path
            from aurora import sun
            path = dynamic_path(sun.phase())
        else:
            path = s.get_string("wallpaper")
    return os.path.splitext(os.path.basename(path or ""))[0]


def place(path=None):
    """What is where in the picture: the sky, the water, the sun."""
    return PICTURES.get(picture_key(path), UNKNOWN)


def layers(name=None, path=None):
    """The light layers a motion is made of. "auto" asks the picture; "off"
    and "zoom" add nothing, the first because it was asked to and the second
    because GTK animates the picture itself."""
    name = name if name is not None else style()
    if name == "auto":
        return tuple(place(path)["layers"])
    return LAYERS.get(name, ())


# --- the light ------------------------------------------------------------

def _rand(seed):
    """A fixed sequence: the same moment must look the same everywhere."""
    state = [seed * 2654435761 + 97]

    def nxt(n):
        state[0] = (state[0] * 1103515245 + 12345) % (1 << 31)
        return (state[0] >> 8) % n
    return nxt


def aurora_curtains(cr, width, height, phase, accent, place):
    """Curtains of aurora over the top of the picture: each a comb of rays
    that folds as it drifts, green at the foot and violet at the crown.

    They fade out at their ends and at their feet, so none of them lands on
    the ground of the photograph."""
    sky = place.get("sky", 0.58)
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
            strength = (0.42 - 0.10 * depth) * ray * edge
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


def twinkle(cr, width, height, phase, accent, place):
    """Stars coming and going in the sky of the picture. Added, so on a bright
    sky they are nothing and on a dark one they are stars."""
    sky = place.get("sky", 0.55)
    rnd = _rand(11)
    unit = max(0.6, width / 480)
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    for index in range(220):
        x = rnd(1000) / 1000 * width
        y = (rnd(1000) / 1000) ** 1.3 * height * sky
        size = (0.18 + rnd(9) / 20) * unit
        offset = rnd(628) / 100
        speed = 0.6 + rnd(14) / 10
        strength = 0.65 * max(0.0, math.sin(phase * speed + offset)) ** 2
        if strength < 0.03:
            continue
        if index % 11 == 0:
            glow = cairo.RadialGradient(x, y, 0, x, y, size * 8)
            glow.add_color_stop_rgba(0.0, 0.85, 0.92, 1.0, 0.55 * strength)
            glow.add_color_stop_rgba(1.0, 0.85, 0.92, 1.0, 0.0)
            cr.set_source(glow)
            cr.arc(x, y, size * 8, 0, math.pi * 2)
            cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.9 * strength)
        cr.arc(x, y, size, 0, math.pi * 2)
        cr.fill()
    cr.restore()


def clouds(cr, width, height, phase, accent, place):
    """Cloud crossing the sky: soft lenses, slow, faint enough to pass over
    what is in the picture without hiding it."""
    sky = place.get("sky", 0.55)
    rnd = _rand(5)
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    for _cloud in range(10):
        y = height * sky * (0.10 + rnd(80) / 100)
        length = width * (0.22 + rnd(45) / 100)
        thickness = height * (0.012 + rnd(26) / 1000)
        start = rnd(1000) / 1000 * width
        speed = 0.025 + rnd(14) / 1000
        x = ((phase * speed * width + start) % (width + length * 2)) - length
        cr.save()
        cr.translate(x + length / 2, y)
        cr.scale(length / 2, thickness)
        shape = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
        shape.add_color_stop_rgba(0.0, 1.0, 0.95, 0.88, 0.26)
        shape.add_color_stop_rgba(1.0, 1.0, 0.94, 0.86, 0.0)
        cr.set_source(shape)
        cr.arc(0, 0, 1, 0, math.pi * 2)
        cr.fill()
        cr.restore()
    cr.restore()


def shimmer(cr, width, height, phase, accent, place):
    """The light moving on the water at the foot of the picture: short bright
    dashes, longer and rarer as they come towards you."""
    water = place.get("water", 0.78)
    rnd = _rand(61)
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    for _dash in range(160):
        depth = (rnd(1000) / 1000) ** 1.4
        y = height * (water + depth * (1 - water))
        x = (rnd(1000) / 1000 * width + math.sin(phase * 1.5 + depth * 12) * width * 0.012)
        long_ = width * (0.008 + depth * 0.045)
        tall = max(0.6, height * (0.0014 + depth * 0.004))
        wave = 0.5 + 0.5 * math.sin(phase * 1.8 + depth * 18 + x * 0.015)
        strength = (0.55 - 0.20 * depth) * wave ** 2
        if strength < 0.012:
            continue
        # A soft lens, rather than a rectangle sitting on the water.
        cr.save()
        cr.translate(x, y)
        cr.scale(long_, tall)
        glow = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
        glow.add_color_stop_rgba(0, 0.80, 0.90, 1.0, strength)
        glow.add_color_stop_rgba(1, 0.80, 0.90, 1.0, 0)
        cr.set_source(glow)
        cr.arc(0, 0, 1, 0, math.pi * 2)
        cr.fill()
        cr.restore()
    cr.restore()


def breathe(cr, width, height, phase, accent, place):
    """A nebula is lit from inside: its bright hearts swell and fade, very
    slowly, each at its own pace."""
    hearts = place.get("hearts", ((0.5, 0.5),))
    for index, (cx, cy) in enumerate(hearts):
        pulse = 0.5 + 0.5 * math.sin(phase * (0.22 + 0.07 * index) + index * 1.7)
        radius = max(width, height) * (0.16 + 0.05 * index) * (0.85 + 0.3 * pulse)
        colour = ((1.0, 0.72, 0.45), (0.70, 0.55, 1.0), (0.45, 0.75, 1.0))[index % 3]
        glow = cairo.RadialGradient(width * cx, height * cy, 0,
                                    width * cx, height * cy, radius)
        glow.add_color_stop_rgba(0.0, *colour, 0.08 + 0.38 * pulse)
        glow.add_color_stop_rgba(0.4, *colour, 0.04 + 0.19 * pulse)
        glow.add_color_stop_rgba(1.0, *colour, 0.0)
        cr.save()
        cr.set_operator(cairo.OPERATOR_ADD)
        cr.set_source(glow)
        cr.arc(width * cx, height * cy, radius, 0, math.pi * 2)
        cr.fill()
        cr.restore()


def meteor(cr, width, height, phase, accent, place):
    """One streak every few seconds, across the sky in half of one."""
    sky = place.get("sky", 0.6)
    cycle = 7.0
    index = int(phase / cycle)
    along = (phase % cycle) / cycle
    if along > 0.14:
        return
    progress = along / 0.14
    rnd = _rand(100 + index)
    start_x = width * (0.1 + rnd(70) / 100)
    start_y = height * sky * (0.05 + rnd(45) / 100)
    length = width * (0.08 + rnd(8) / 100)
    x = start_x + length * progress
    y = start_y + length * 0.42 * progress
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    tail = cairo.LinearGradient(x - length * 0.6, y - length * 0.25, x, y)
    tail.add_color_stop_rgba(0.0, 1, 1, 1, 0.0)
    tail.add_color_stop_rgba(1.0, 1, 1, 1, 0.9 * math.sin(math.pi * progress))
    cr.set_source(tail)
    cr.set_line_width(max(0.8, height * 0.0035))
    cr.move_to(x - length * 0.6, y - length * 0.25)
    cr.line_to(x, y)
    cr.stroke()
    cr.restore()


def rays(cr, width, height, phase, accent, place):
    """Light from where the sun is in the picture, swinging very slowly: the
    shafts you see when air is full of cloud."""
    sun_x, sun_y = place.get("sun", (0.5, 0.35))
    x, y = width * sun_x, height * sun_y
    swing = math.sin(phase * 0.07) * 0.10
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    for spoke in range(14):
        angle = spoke * math.pi * 2 / 14 + swing
        length = max(width, height) * (0.35 + 0.30 * ((spoke % 5) / 4))
        breadth = 0.008 + 0.010 * ((spoke + 1) % 3)
        strength = 0.12 + 0.22 * (0.5 + 0.5 * math.sin(phase * 0.8 + spoke))
        ray = cairo.LinearGradient(x, y, x + math.cos(angle) * length,
                                   y + math.sin(angle) * length)
        ray.add_color_stop_rgba(0.0, 1.0, 0.90, 0.70, strength)
        ray.add_color_stop_rgba(1.0, 1.0, 0.80, 0.55, 0.0)
        cr.set_source(ray)
        cr.move_to(x, y)
        cr.line_to(x + math.cos(angle - breadth) * length,
                   y + math.sin(angle - breadth) * length)
        cr.line_to(x + math.cos(angle + breadth) * length,
                   y + math.sin(angle + breadth) * length)
        cr.close_path()
        cr.fill()
    cr.restore()


def glint(cr, width, height, phase, accent, place):
    """A bright point travelling across the picture, the way the sun catches
    something turning: for the rings of a planet."""
    sun_x, sun_y = place.get("sun", (0.26, 0.47))
    run = (phase * 0.06) % 1.0
    # Follow the visible left-hand arc of the rings, away from the planet.
    x = width * (0.27 - 0.18 * math.sin(math.pi * run) + 0.28 * run)
    y = height * (0.40 + 0.56 * run)
    fade = math.sin(math.pi * run) ** 1.5
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    glow = cairo.RadialGradient(x, y, 0, x, y, width * 0.05)
    glow.add_color_stop_rgba(0.0, 1.0, 0.95, 0.82, 0.65 * fade)
    glow.add_color_stop_rgba(1.0, 1.0, 0.9, 0.75, 0.0)
    cr.set_source(glow)
    cr.arc(x, y, width * 0.05, 0, math.pi * 2)
    cr.fill()
    cr.restore()
    # And the star itself, breathing where it stands in the picture.
    pulse = 0.5 + 0.5 * math.sin(phase * 0.6)
    _add_glow(cr, width * sun_x, height * sun_y, width * 0.07,
              (1.0, 0.92, 0.70), 0.08 + 0.30 * pulse)


def _add_glow(cr, x, y, radius, colour, alpha):
    glow = cairo.RadialGradient(x, y, 0, x, y, radius)
    glow.add_color_stop_rgba(0.0, *colour, alpha)
    glow.add_color_stop_rgba(1.0, *colour, 0.0)
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    cr.set_source(glow)
    cr.arc(x, y, radius, 0, math.pi * 2)
    cr.fill()
    cr.restore()


PAINTERS = {"aurora": aurora_curtains, "stars": twinkle, "clouds": clouds,
            "shimmer": shimmer, "breathe": breathe, "meteor": meteor,
            "rays": rays, "glint": glint}


def paint(names, cr, width, height, phase, accent, place=None):
    """Add every layer of a motion over the picture, in order."""
    place = place or {}
    for name in names:
        painter = PAINTERS.get(name)
        if painter is not None:
            painter(cr, width, height, phase, accent, place)


def cover_geometry(width, height, picture_width, picture_height):
    """The same centred crop as Gtk.Picture(content_fit=COVER)."""
    scale = max(width / picture_width, height / picture_height)
    return (scale, (width - picture_width * scale) / 2,
            (height - picture_height * scale) / 2)


def draw_ripples(cr, width, height, phase, picture, scene):
    """Move the photograph's own water, keeping its original resolution.

    Adjacent narrow strips shift continuously; the displacement fades in at
    the waterline. PAD keeps the edges filled on wide monitors.
    """
    pw, ph = picture.get_width(), picture.get_height()
    scale, x, y = cover_geometry(width, height, pw, ph)
    top = max(0, y + ph * scale * scene["ripple"])
    span = max(1, height - top)
    strength = width * scene.get("ripple_strength", 0.003)
    cr.save()
    # Four screen pixels per strip, independent of monitor scaling.
    for row in range(math.ceil(top), height, 4):
        depth = (row - top) / span
        shift = strength * min(1, depth * 6) * math.sin(phase * 2.2 + depth * 18)
        cr.save()
        cr.rectangle(0, row, width, min(4, height - row))
        cr.clip()
        cr.translate(x + shift, y)
        cr.scale(scale, scale)
        cr.set_source_surface(picture, 0, 0)
        cr.get_source().set_extend(cairo.EXTEND_PAD)
        cr.paint()
        cr.restore()
    cr.restore()


def draw_light(cr, width, height, phase, motion, path, picture_size, accent, picture=None):
    """Render in picture coordinates so the light follows COVER on any monitor."""
    names = layers(motion, path)
    if not names or width <= 0 or height <= 0:
        return
    scene = place(path)
    if motion == "auto" and picture is not None and "ripple" in scene:
        draw_ripples(cr, width, height, phase, picture, scene)
    small_w, small_h = max(1, math.ceil(width / SCALE)), max(1, math.ceil(height / SCALE))
    small = cairo.ImageSurface(cairo.FORMAT_ARGB32, small_w, small_h)
    light = cairo.Context(small)
    pw, ph = picture_size
    scale, x, y = cover_geometry(small_w, small_h, pw, ph)
    light.translate(x, y)
    # Use the covered picture's dimensions, keeping brush sizes in screen pixels.
    paint(names, light, pw * scale, ph * scale, phase, accent, place(path))
    cr.save()
    cr.scale(width / small_w, height / small_h)
    cr.set_source_surface(small, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_BILINEAR)
    cr.paint()
    cr.restore()


class LivingWallpaper(Gtk.Overlay):
    """Moving light on the desktop or in Settings' live preview.

    The owner supplies the actual displayed path, including slideshows and
    downloaded pictures. Subscriptions exist only while the widget is mapped.
    """

    def __init__(self, shell=None, activity=None):
        super().__init__(can_target=False, hexpand=True, vexpand=True)
        self.shell = shell
        self._activity = activity
        self.path = ""
        self.picture_size = (1920, 1080)
        self._picture = None
        self.media = None
        self._media_handlers = []
        self._video = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True,
                                  can_target=False, hexpand=True, vexpand=True, visible=False)
        self._light = Gtk.DrawingArea(can_target=False, hexpand=True, vexpand=True)
        self.set_child(self._light)
        self.add_overlay(self._video)
        self.running = False
        self._handlers = []
        self._tick = 0
        self._started = time.monotonic()
        self._light.set_draw_func(self._draw)
        self.connect("map", self._mapped)
        self.connect("unmap", self._unmapped)

    def set_picture(self, path):
        path = path or ""
        if path != self.path:
            self._release_media()
            self.path = path
            self._started = time.monotonic()
            try:
                _info, width, height = GdkPixbuf.Pixbuf.get_file_info(wallpapers.poster_path(path))
                self.picture_size = (width, height) if width > 0 and height > 0 else (1920, 1080)
            except (GLib.Error, OSError):
                self.picture_size = (1920, 1080)
            self._picture = None
            if "ripple" in place(path):
                try:
                    self._picture = cairo.ImageSurface.create_from_png(path)
                except (cairo.Error, OSError):
                    pass
        self.refresh()

    def _listen(self, obj, signal):
        if obj is not None:
            self._handlers.append((obj, obj.connect(signal, lambda *_a: self.refresh())))

    def _mapped(self, *_args):
        s = settings.get()
        self._listen(s, "changed::wallpaper-animation")
        self._listen(s, "changed::accent-color")
        if self.shell is not None:
            self._listen(self.shell.toplevels, "changed")
            self._listen(getattr(self.shell, "power_profiles", None), "changed")
        self.refresh()

    def _unmapped(self, *_args):
        self._stop()
        self._release_media()
        self.running = False
        if self._activity is not None:
            self._activity(False)
        for obj, handler in self._handlers:
            obj.disconnect(handler)
        self._handlers.clear()

    def covered(self):
        if self.shell is None:
            return False
        return any(not window.minimized and (window.fullscreen or window.maximized)
                   for window in self.shell.toplevels.toplevels)

    def saving_power(self):
        profiles = getattr(self.shell, "power_profiles", None)
        return getattr(profiles, "current", None) == "power-saver"

    def refresh(self):
        motion = style()
        video = wallpapers.is_video(self.path)
        drawing = not video and bool(layers(motion, self.path))
        enabled = motion != "off" if video else drawing or motion == "zoom"
        if video and enabled and self.get_mapped() and self.media is None:
            self.media = Gtk.MediaFile.new_for_filename(self.path)
            self.media.set_loop(True)
            self.media.set_muted(True)
            self._media_handlers = [self.media.connect("notify::" + prop,
                                    lambda *_args: self.refresh()) for prop in ("prepared", "error")]
            self._video.set_paintable(self.media)
        playable = self.media is not None and self.media.get_error() is None
        self._video.set_visible(video and enabled and playable and self.media.is_prepared())
        self._light.set_visible(not video)
        self.running = enabled and (not video or playable) and self.get_mapped() \
            and not self.covered() and not self.saving_power()
        if self.media is not None:
            self.media.set_playing(self.running)
        if self.running and drawing and not self._tick:
            self._tick = GLib.timeout_add(FRAME_MS, self._frame)
        elif not self.running or not drawing:
            self._stop()
        if self._activity is not None:
            self._activity(self.running)
        self._light.queue_draw()

    def _release_media(self):
        if self.media is not None:
            for handler in self._media_handlers:
                self.media.disconnect(handler)
            self._media_handlers.clear()
            self.media.pause()
            self.media.clear()
            self.media = None
        self._video.set_paintable(None)
        self._video.set_visible(False)

    def _stop(self):
        if self._tick:
            GLib.source_remove(self._tick)
            self._tick = 0

    def _frame(self):
        self._light.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _accent(self):
        from aurora import look
        colour = look.accent_hex()
        try:
            return tuple(int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        except (ValueError, IndexError):
            return (0.66, 0.44, 1.0)

    def _draw(self, _area, cr, width, height):
        # Pausing leaves the photograph clean, with no frozen light overlay.
        if not self.running:
            return
        phase = (time.monotonic() - self._started) * 0.6
        draw_light(cr, width, height, phase, style(), self.path,
                   self.picture_size, self._accent(), self._picture)
