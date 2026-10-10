"""Animated backgrounds: the picture itself is drawn, frame by frame.

Settings → Appearance → Background → Animated. Six scenes, all drawn with
Cairo rather than by a GPU shader, because Aurora renders in software in a
virtual machine and a shader would be a slide show there:

    aurora         the northern lights over hills, their glow on the ridges
    nebula         dust and star clouds, with the galaxy's band across them
    waves          long bands of light sliding over one another, like silk
    constellation  points drifting in the dark, joined when two come close
    sunrise        the sun low over hills, clouds crossing it, the sky turning
    rings          arcs turning around a point below the screen

Light is added rather than painted on (cairo's ADD operator): that is what
makes a glow look like light instead of a grey shape, and what lets two
colours meet in a third rather than one covering the other. Everything is
drawn into a surface a quarter of the screen's size and scaled up, which is
both cheap and where the softness comes from, and takes the accent colour so
the desktop stays of a piece. Nothing is drawn while a window covers the
desktop or the computer is saving power (see livingwallpaper.py).

A scene is a pure function of (width, height, phase): the same moment always
paints the same picture, which is what lets a still of one be its own preview
in Settings, and what lets a test say anything about it at all.
"""

import math

import cairo

SCENES = ("aurora", "nebula", "waves", "constellation", "sunrise", "rings")


# --- the things the scenes are made of ------------------------------------

def _rand(seed):
    """A fixed sequence: a scene must paint the same picture everywhere."""
    state = [seed * 2654435761 + 97]

    def nxt(n):
        state[0] = (state[0] * 1103515245 + 12345) % (1 << 31)
        return (state[0] >> 8) % n
    return nxt


def _sky(cr, width, height, stops):
    """The ground colour: a gradient of as many stops as the scene wants."""
    sky = cairo.LinearGradient(0, 0, 0, height)
    for position, colour in stops:
        sky.add_color_stop_rgb(position, *colour)
    cr.set_source(sky)
    cr.rectangle(0, 0, width, height)
    cr.fill()


def _glow(cr, x, y, radius, colour, alpha, softness=1.0):
    """A ball of light, added to what is there rather than painted over it."""
    if radius <= 0 or alpha <= 0:
        return
    light = cairo.RadialGradient(x, y, 0, x, y, radius)
    light.add_color_stop_rgba(0.0, *colour, alpha)
    light.add_color_stop_rgba(min(0.9, 0.35 * softness), *colour, alpha * 0.45)
    light.add_color_stop_rgba(1.0, *colour, 0.0)
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    cr.set_source(light)
    cr.arc(x, y, radius, 0, math.pi * 2)
    cr.fill()
    cr.restore()


def _vignette(cr, width, height, strength=0.4):
    """The corners fall away: without it a drawn background reads as a flat
    fill, which is the difference between a wallpaper and a colour."""
    shade = cairo.RadialGradient(width * 0.5, height * 0.45, min(width, height) * 0.25,
                                 width * 0.5, height * 0.5, max(width, height) * 0.78)
    shade.add_color_stop_rgba(0.0, 0, 0, 0, 0.0)
    shade.add_color_stop_rgba(1.0, 0, 0, 0, strength)
    cr.set_source(shade)
    cr.rectangle(0, 0, width, height)
    cr.fill()


def _stars(cr, width, height, phase, count=150, below=0.8, seed=11, bright=6):
    """Stars of several sizes, a few of them with a halo, each twinkling at
    its own pace and dimmer towards the horizon, as they are."""
    rnd = _rand(seed)
    unit = width / 480
    for index in range(count):
        x = rnd(1000) / 1000 * width
        y = (rnd(1000) / 1000) ** 1.4 * height * below
        size = (0.35 + rnd(14) / 10) * unit
        offset = rnd(628) / 100
        twinkle = 0.3 + 0.7 * (1 + math.sin(phase * (0.6 + rnd(9) / 10) + offset)) / 2
        depth = (1 - y / max(1.0, height * below)) ** 0.6
        alpha = min(1.0, 0.25 + 0.55 * twinkle) * depth
        if index < bright:
            _glow(cr, x, y, size * 9, (0.85, 0.90, 1.0), alpha * 0.5)
        cr.set_source_rgba(1, 1, 1, alpha)
        cr.arc(x, y, size, 0, math.pi * 2)
        cr.fill()


def _ridges(cr, width, height, layers):
    """Hills, each filled with a gradient rather than flat, the nearest
    darkest, with a thread of light along the top of the ones behind."""
    for index, (base, amplitude, top_colour, bottom_colour, rim) in enumerate(layers):
        points = []
        for step in range(49):
            x = width * step / 48
            y = height * base + math.sin(step * 0.31 + index * 2.3) * height * amplitude \
                + math.sin(step * 0.12 + index) * height * amplitude * 0.55
            points.append((x, y))
        cr.move_to(0, height)
        for x, y in points:
            cr.line_to(x, y)
        cr.line_to(width, height)
        cr.close_path()
        fill = cairo.LinearGradient(0, height * base - height * amplitude, 0, height)
        fill.add_color_stop_rgb(0.0, *top_colour)
        fill.add_color_stop_rgb(1.0, *bottom_colour)
        cr.set_source(fill)
        cr.fill()
        if rim is not None:
            cr.save()
            cr.set_operator(cairo.OPERATOR_ADD)
            cr.set_line_width(max(1.0, height * 0.004))
            cr.set_source_rgba(*rim)
            cr.move_to(*points[0])
            for x, y in points[1:]:
                cr.line_to(x, y)
            cr.stroke()
            cr.restore()


# --- the scenes ------------------------------------------------------------

def aurora(cr, width, height, phase, accent):
    """The northern lights: three curtains, each a comb of rays that folds as
    it drifts, green at the foot and violet at the crown, with their light
    lying along the ridges below."""
    _sky(cr, width, height, ((0.0, (0.02, 0.02, 0.07)),
                             (0.55, (0.05, 0.05, 0.14)),
                             (1.0, (0.08, 0.09, 0.19))))
    _stars(cr, width, height, phase, count=170, below=0.72)
    _glow(cr, width * 0.5, height * 0.74, width * 0.55, (0.15, 0.55, 0.45), 0.10)

    curtains = (  # depth, colour at the foot, at the crown, centre, width, speed
        (0, (0.20, 0.95, 0.55), (0.55, 0.35, 1.00), 0.42, 0.62, 0.22),
        (1, (0.25, 0.85, 0.90), (0.90, 0.40, 0.85), 0.70, 0.46, 0.31),
        (2, (0.35, 0.95, 0.70), (0.60, 0.50, 1.00), 0.18, 0.38, 0.17))
    for depth, foot, crown, centre, span, speed in curtains:
        drift = phase * speed
        left, right = width * (centre - span / 2), width * (centre + span / 2)
        step = max(2.0, (right - left) / 46)
        cr.save()
        cr.set_operator(cairo.OPERATOR_ADD)
        x = left
        while x < right:
            across = (x - left) / max(1.0, right - left)
            # Two waves for the hanging edge and a third for the brightness,
            # so the curtain folds instead of rippling evenly.
            fold = math.sin(across * 7.0 + drift) + 0.5 * math.sin(across * 17.0 - drift * 1.4)
            glow = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(across * 11.0 - drift * 1.9 + depth))
            edge = math.sin(math.pi * min(1.0, max(0.0, across))) ** 0.7
            top = height * (0.07 + 0.06 * depth) + fold * height * 0.055
            length = height * (0.40 - 0.06 * depth) + fold * height * 0.05
            strength = (0.26 - 0.06 * depth) * glow * edge
            if strength > 0.004:
                fade = cairo.LinearGradient(0, top, 0, top + length)
                fade.add_color_stop_rgba(0.0, *crown, 0.0)
                fade.add_color_stop_rgba(0.18, *crown, strength)
                fade.add_color_stop_rgba(0.55, *foot, strength * 0.95)
                fade.add_color_stop_rgba(1.0, *foot, 0.0)
                cr.set_source(fade)
                cr.rectangle(x, top, step * 1.25, length)
                cr.fill()
            x += step
        cr.restore()
        _glow(cr, width * centre, height * (0.26 + 0.05 * depth), width * span * 0.75,
              foot, 0.055)

    _ridges(cr, width, height, (
        (0.72, 0.045, (0.10, 0.16, 0.22), (0.05, 0.08, 0.14), (0.20, 0.65, 0.45, 0.30)),
        (0.80, 0.035, (0.05, 0.07, 0.12), (0.02, 0.03, 0.07), (0.12, 0.40, 0.32, 0.18)),
        (0.90, 0.025, (0.02, 0.02, 0.05), (0.01, 0.01, 0.02), None)))
    _vignette(cr, width, height, 0.40)


def nebula(cr, width, height, phase, accent):
    """Dust and star clouds, with the galaxy's band lying across them."""
    r, g, b = accent
    _sky(cr, width, height, ((0.0, (0.02, 0.02, 0.07)),
                             (0.5, (0.04, 0.03, 0.10)),
                             (1.0, (0.02, 0.02, 0.06))))
    cr.save()
    cr.translate(width * 0.5, height * 0.5)
    cr.rotate(-0.42)
    band = cairo.LinearGradient(0, -height * 0.42, 0, height * 0.42)
    for position, alpha in ((0.0, 0.0), (0.42, 0.10), (0.5, 0.16), (0.58, 0.10), (1.0, 0.0)):
        band.add_color_stop_rgba(position, 0.80, 0.82, 1.00, alpha)
    cr.set_operator(cairo.OPERATOR_ADD)
    cr.set_source(band)
    cr.rectangle(-width, -height * 0.42, width * 2, height * 0.84)
    cr.fill()
    cr.restore()

    clouds = (((r, g, b), 0.30, 0.34, 0.40, 0.17, 0.22),
              ((0.25, 0.80, 0.80), 0.66, 0.62, 0.34, -0.13, 0.18),
              ((1.00, 0.40, 0.62), 0.78, 0.28, 0.28, 0.21, 0.20),
              ((0.55, 0.45, 1.00), 0.16, 0.72, 0.30, -0.24, 0.16),
              ((0.95, 0.65, 0.35), 0.48, 0.50, 0.22, 0.28, 0.12))
    for colour, cx, cy, size, speed, alpha in clouds:
        x = width * (cx + 0.05 * math.sin(phase * speed))
        y = height * (cy + 0.04 * math.cos(phase * speed * 0.85))
        _glow(cr, x, y, max(width, height) * size, colour, alpha, softness=1.3)
    # Dust: dark veils over the light, so it is not all glow.
    for index in range(3):
        x = width * (0.3 + 0.25 * index + 0.03 * math.sin(phase * 0.1 + index))
        y = height * (0.35 + 0.18 * index)
        dark = cairo.RadialGradient(x, y, 0, x, y, max(width, height) * 0.26)
        dark.add_color_stop_rgba(0.0, 0.01, 0.01, 0.04, 0.5)
        dark.add_color_stop_rgba(1.0, 0.01, 0.01, 0.04, 0.0)
        cr.set_source(dark)
        cr.rectangle(0, 0, width, height)
        cr.fill()
    _stars(cr, width, height, phase, count=220, below=1.0, seed=29, bright=10)
    _vignette(cr, width, height, 0.42)


def waves(cr, width, height, phase, accent):
    """Long bands of light sliding over one another, like silk: each with a
    bright line along its fold, and where two cross, their colours add."""
    r, g, b = accent
    _sky(cr, width, height, ((0.0, (0.05, 0.04, 0.12)),
                             (0.6, (0.03, 0.03, 0.09)),
                             (1.0, (0.01, 0.01, 0.04))))
    _glow(cr, width * 0.5, height * 0.62, max(width, height) * 0.55, (r, g, b), 0.12)
    colours = ((r, g, b), (0.25, 0.85, 0.80), (1.0, 0.45, 0.70),
               (0.60, 0.50, 1.0), (0.98, 0.72, 0.42))
    for band, colour in enumerate(colours):
        offset = phase * (0.18 + 0.055 * band)
        points = []
        for step in range(65):
            x = -10 + (width + 20) * step / 64
            y = height * (0.30 + 0.115 * band) \
                + math.sin(step * 0.17 + offset) * height * 0.075 \
                + math.sin(step * 0.061 - offset * 0.73) * height * 0.05
            points.append((x, y))
        cr.save()
        cr.set_operator(cairo.OPERATOR_ADD)
        cr.move_to(points[0][0], height + 10)
        for x, y in points:
            cr.line_to(x, y)
        cr.line_to(points[-1][0], height + 10)
        cr.close_path()
        top = min(y for _x, y in points)
        fill = cairo.LinearGradient(0, top, 0, height)
        fill.add_color_stop_rgba(0.0, *colour, 0.30)
        fill.add_color_stop_rgba(0.35, *colour, 0.10)
        fill.add_color_stop_rgba(1.0, *colour, 0.0)
        cr.set_source(fill)
        cr.fill()
        cr.set_line_width(max(1.2, height * 0.005))
        cr.set_source_rgba(min(1.0, colour[0] + 0.3), min(1.0, colour[1] + 0.3),
                           min(1.0, colour[2] + 0.3), 0.55)
        cr.move_to(*points[0])
        for x, y in points[1:]:
            cr.line_to(x, y)
        cr.stroke()
        cr.restore()
    _vignette(cr, width, height, 0.35)


def constellation(cr, width, height, phase, accent):
    """Points drifting in the dark, joined by a line whenever two come close:
    a sky that draws itself and undraws itself."""
    r, g, b = accent
    _sky(cr, width, height, ((0.0, (0.05, 0.04, 0.12)), (1.0, (0.01, 0.01, 0.05))))
    _glow(cr, width * 0.62, height * 0.38, max(width, height) * 0.5, (r, g, b), 0.10)
    _stars(cr, width, height, phase, count=90, below=1.0, seed=41, bright=0)
    rnd = _rand(23)
    points = []
    for _index in range(40):
        base_x = rnd(1000) / 1000 * width
        base_y = rnd(1000) / 1000 * height
        speed = 0.07 + rnd(18) / 100
        offset = rnd(628) / 100
        reach = (0.015 + rnd(4) / 100) * min(width, height)
        warm = rnd(100) < 35
        points.append((base_x + math.sin(phase * speed + offset) * reach,
                       base_y + math.cos(phase * speed * 0.8 + offset) * reach,
                       0.9 + rnd(14) / 10, warm))
    near = min(width, height) * 0.24
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    cr.set_line_width(max(0.5, width / 1100))
    for i, (x1, y1, _s1, _w1) in enumerate(points):
        for x2, y2, _s2, _w2 in points[i + 1:]:
            distance = math.hypot(x1 - x2, y1 - y2)
            if distance > near:
                continue
            cr.set_source_rgba(r, g, b, 0.30 * (1 - distance / near) ** 1.4)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()
    cr.restore()
    for x, y, size, warm in points:
        colour = (1.0, 0.72, 0.45) if warm else (r, g, b)
        dot = size * (width / 480)
        _glow(cr, x, y, dot * 7, colour, 0.55)
        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.arc(x, y, dot * 0.8, 0, math.pi * 2)
        cr.fill()
    _vignette(cr, width, height, 0.40)


def sunrise(cr, width, height, phase, accent):
    """The hour the light turns: the sun low over the hills, clouds crossing
    it, and the colour of the whole sky moving with it."""
    walk = (math.sin(phase * 0.05) + 1) / 2                # 0..1, very slowly
    sun_x = width * (0.20 + 0.60 * walk)
    sun_y = height * (0.70 - 0.26 * math.sin(math.pi * walk))
    warmth = 0.30 + 0.70 * math.sin(math.pi * walk)
    _sky(cr, width, height, (
        (0.0, (0.07 + 0.04 * warmth, 0.07 + 0.05 * warmth, 0.22 + 0.14 * warmth)),
        (0.45, (0.26 + 0.26 * warmth, 0.18 + 0.16 * warmth, 0.36 + 0.10 * warmth)),
        (0.72, (0.62 + 0.30 * warmth, 0.32 + 0.24 * warmth, 0.36)),
        (1.0, (0.35 + 0.30 * warmth, 0.20 + 0.16 * warmth, 0.28))))
    _glow(cr, sun_x, sun_y, min(width, height) * 1.25, (1.0, 0.68, 0.38),
          0.30 + 0.25 * warmth, softness=1.6)
    _glow(cr, sun_x, sun_y, min(width, height) * 0.22, (1.0, 0.88, 0.62), 0.55)
    cr.set_source_rgba(1.0, 0.96, 0.86, 0.95)
    cr.arc(sun_x, sun_y, min(width, height) * 0.035, 0, math.pi * 2)
    cr.fill()
    # Clouds: soft lenses, not bars, each crossing at its own pace and lit by
    # how near it passes the sun.
    rnd = _rand(5)
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    for cloud in range(9):
        y = height * (0.16 + 0.055 * cloud)
        speed = 0.010 + rnd(12) / 1200
        length = width * (0.22 + rnd(45) / 100)
        thickness = height * (0.016 + rnd(22) / 1000)
        start = rnd(1000) / 1000 * width
        x = ((phase * speed * width + start) % (width + length * 2)) - length
        lit = max(0.0, 1 - abs((x + length / 2) - sun_x) / (width * 0.6))
        alpha = (0.05 + 0.16 * lit) * (0.5 + 0.5 * warmth)
        cr.save()
        cr.translate(x + length / 2, y)
        cr.scale(length / 2, thickness)
        shape = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
        shape.add_color_stop_rgba(0.0, 1.0, 0.92 - 0.1 * lit, 0.86 - 0.2 * lit, alpha)
        shape.add_color_stop_rgba(1.0, 1.0, 0.9, 0.85, 0.0)
        cr.set_source(shape)
        cr.arc(0, 0, 1, 0, math.pi * 2)
        cr.fill()
        cr.restore()
    cr.restore()
    _ridges(cr, width, height, (
        (0.78, 0.040, (0.34, 0.22, 0.34), (0.22, 0.13, 0.26), (0.45, 0.28, 0.18, 0.35)),
        (0.86, 0.030, (0.20, 0.12, 0.22), (0.12, 0.07, 0.15), (0.30, 0.16, 0.12, 0.22)),
        (0.94, 0.020, (0.09, 0.05, 0.11), (0.05, 0.03, 0.07), None)))
    _vignette(cr, width, height, 0.30)


def rings(cr, width, height, phase, accent):
    """Arcs turning around a point below the screen, each with its own glow:
    the quietest of the six, and the only one that is a pattern, not a place."""
    r, g, b = accent
    _sky(cr, width, height, ((0.0, (0.06, 0.05, 0.14)), (1.0, (0.01, 0.01, 0.05))))
    centre_x, centre_y = width * 0.36, height * 1.16
    _glow(cr, centre_x, centre_y, max(width, height) * 0.8, (r, g, b), 0.16)
    longest = math.hypot(width, height)
    colours = ((r, g, b), (0.30, 0.85, 0.80), (1.0, 0.50, 0.70), (0.98, 0.72, 0.45),
               (0.60, 0.55, 1.0))
    cr.save()
    cr.set_operator(cairo.OPERATOR_ADD)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for ring in range(13):
        radius = longest * (0.09 + 0.082 * ring)
        speed = 0.07 + 0.035 * (ring % 5)
        start = phase * speed * (1 if ring % 2 else -1) + ring * 0.7
        sweep = 1.7 + 0.6 * math.sin(phase * 0.16 + ring)
        colour = colours[ring % len(colours)]
        thickness = max(1.6, height * (0.020 - 0.0009 * ring))
        for pass_width, alpha in ((thickness * 4.0, 0.06), (thickness, 0.40 - 0.02 * ring)):
            cr.set_line_width(pass_width)
            cr.set_source_rgba(*colour, max(0.0, alpha))
            cr.arc(centre_x, centre_y, radius, start, start + sweep)
            cr.stroke()
        cr.set_line_width(thickness * 0.6)
        cr.set_source_rgba(*colour, max(0.0, 0.18 - 0.01 * ring))
        cr.arc(centre_x, centre_y, radius, start + sweep + 0.7,
               start + sweep + 0.7 + sweep * 0.4)
        cr.stroke()
    cr.restore()
    _vignette(cr, width, height, 0.38)


PAINTERS = {"aurora": aurora, "nebula": nebula, "waves": waves,
            "constellation": constellation, "sunrise": sunrise, "rings": rings}


def paint(name, cr, width, height, phase, accent):
    """One frame of a scene. An unknown name paints the aurora."""
    PAINTERS.get(name, aurora)(cr, width, height, phase, accent)


def still(name, width, height, accent, phase=3.0):
    """One frame as an image surface: the preview in Settings is the scene
    itself, not a picture of it made by hand."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, width), max(1, height))
    paint(name, cairo.Context(surface), width, height, phase, accent)
    return surface
