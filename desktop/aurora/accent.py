"""The accent color taken from the background picture.

Settings → Appearance → Style → "Color from the background" picks the most
vivid color of the picture on screen and uses it as the accent everywhere,
instead of one of the nine fixed ones. The picture is read small (64×64), its
colors are gathered into hue buckets, and the heaviest bucket wins; the color
is then pulled into a range that still reads under white text, so a washed-out
or very dark picture never gives an unusable accent.

~/.cache/aurora/wallpaper always points at the picture on screen (the lock
screen uses it too), so this works from any process and follows the background
through the day.
"""

import colorsys
import os

HUE_BUCKETS = 18        # 20° each
MIN_WEIGHT = 0.02       # of the pixels looked at: below this the picture is grey


def _path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aurora", "wallpaper")


def _usable(hue, sat, val):
    """Pull a color into the range an accent has to live in: vivid enough to
    read as a color, dark enough for white text on top (yellows and greens
    have to come down further than blues and violets)."""
    sat = min(0.85, max(0.45, sat * 1.15))
    ceiling = 0.70 if 40 <= hue * 360 <= 190 else 0.88
    return hue, sat, min(ceiling, max(0.65, val))


def from_picture(path, size=64):
    """'#rrggbb' for this picture, or None if it has no color worth using."""
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
    except Exception:       # noqa: BLE001 - any unreadable picture: keep the chosen accent
        return None
    if pix is None:
        return None
    data = pix.get_pixels()
    stride, channels = pix.get_rowstride(), pix.get_n_channels()
    width, height = pix.get_width(), pix.get_height()

    buckets = [[0.0, 0.0, 0.0, 0.0] for _ in range(HUE_BUCKETS)]   # weight, h, s, v
    total = 0
    for y in range(height):
        row = y * stride
        for x in range(width):
            i = row + x * channels
            r, g, b = data[i] / 255, data[i + 1] / 255, data[i + 2] / 255
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            total += 1
            # Skip what is nearly black, nearly white or nearly grey: a
            # picture is mostly sky and shadow, and neither is an accent.
            if v < 0.12 or v > 0.97 or s < 0.18:
                continue
            weight = s * s * v
            slot = buckets[min(HUE_BUCKETS - 1, int(h * HUE_BUCKETS))]
            slot[0] += weight
            slot[1] += h * weight
            slot[2] += s * weight
            slot[3] += v * weight

    best = max(buckets, key=lambda slot: slot[0])
    if not total or best[0] / total < MIN_WEIGHT:
        return None
    h, s, v = _usable(best[1] / best[0], best[2] / best[0], best[3] / best[0])
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


_cache = {}


def current():
    """The accent for the picture on screen now, or None. Worked out once per
    picture: this runs whenever the style is applied."""
    path = _path()
    try:
        real = os.path.realpath(path)
        stamp = os.stat(real).st_mtime
    except OSError:
        return None
    key = (real, stamp)
    if key not in _cache:
        _cache.clear()
        _cache[key] = from_picture(real)
    return _cache[key]
