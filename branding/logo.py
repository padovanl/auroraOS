#!/usr/bin/env python3
"""The Aurora OS logo and its boot animation, drawn with cairo.

The mark is two aurora ribbons forming an arch over a rising sun. The
animation has an intro (ribbons draw themselves in, sun rises, wordmark fades
in) followed by a seamless loop (a highlight travels along the ribbons while
the sun glows).

Usage:
  logo.py frames OUT_DIR [SIZE]   -> OUT_DIR/intro-NN.png, loop-NN.png
  logo.py gif OUT.gif [SIZE]      -> animated GIF on a dark tile (needs Pillow)
  logo.py webp OUT.webp [SIZE]    -> animated WebP with transparency, for the website
  logo.py png OUT.png [SIZE]      -> static logo with wordmark on a dark tile
  logo.py static OUT.png [SIZE]   -> static logo with wordmark, transparent
  logo.py mark OUT.png [SIZE]     -> the mark alone, transparent
"""

import math
import os
import sys

import cairo

VIOLET = (0.66, 0.44, 1.0)
ROSE = (1.0, 0.44, 0.57)
AMBER = (1.0, 0.64, 0.36)
TEXT = (0.95, 0.93, 0.98)
BG = (0.05, 0.03, 0.10)

INTRO_FRAMES = 36
LOOP_FRAMES = 48

# Paths in a 128x128 design space.
OUTER = [(24, 98), (38, 58, 58, 30, 64, 26), (70, 30, 90, 58, 104, 98)]
INNER = [(42, 98), (50, 76, 58, 62, 64, 58), (70, 62, 78, 76, 86, 98)]


def ease_out(t):
    return 1 - (1 - max(0.0, min(1.0, t))) ** 3


def _path(ctx, spec):
    ctx.move_to(*spec[0])
    for seg in spec[1:]:
        ctx.curve_to(*seg)


def _path_length(ctx, spec):
    ctx.new_path()
    _path(ctx, spec)
    flat = ctx.copy_path_flat()
    ctx.new_path()
    length, last = 0.0, None
    for kind, pts in flat:
        if kind in (cairo.PATH_MOVE_TO, cairo.PATH_LINE_TO):
            if last is not None and kind == cairo.PATH_LINE_TO:
                length += math.dist(last, pts)
            last = pts
    return length


def _gradient(x0, y0, x1, y1, shift=0.0):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    g.add_color_stop_rgb(0, *AMBER)
    g.add_color_stop_rgb(0.5, *ROSE)
    g.add_color_stop_rgb(1, *VIOLET)
    return g


def _ribbon(ctx, spec, width, progress, alpha, highlight=None):
    """Stroke a ribbon drawn up to `progress` (0..1), with optional travelling glint."""
    length = _path_length(ctx, spec)
    x0, y0 = spec[0]
    x1, y1 = spec[-1][-2:]
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)

    # Soft glow underneath.
    for w, a in ((width * 2.6, 0.10), (width * 1.8, 0.16)):
        ctx.new_path()
        _path(ctx, spec)
        ctx.set_dash([length * progress + 0.01, length * 2])
        ctx.set_line_width(w)
        ctx.set_source(_gradient(x0, y0, x1, 26))
        ctx.push_group()
        ctx.stroke()
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(a * alpha)

    ctx.new_path()
    _path(ctx, spec)
    ctx.set_dash([length * progress + 0.01, length * 2])
    ctx.set_line_width(width)
    ctx.set_source(_gradient(x0, y0, x1, 26))
    ctx.push_group()
    ctx.stroke()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(alpha)

    if highlight is not None:
        seg = length * 0.18
        ctx.new_path()
        _path(ctx, spec)
        ctx.set_dash([seg, length * 2], -(highlight * (length + seg)) + seg)
        ctx.set_line_width(width * 0.55)
        ctx.set_source_rgba(1, 1, 1, 0.55 * alpha)
        ctx.stroke()
    ctx.set_dash([])


def draw_mark(ctx, size, t_outer=1.0, t_inner=1.0, sun=1.0, glint=None, glow=0.0):
    ctx.save()
    ctx.scale(size / 128.0, size / 128.0)
    _ribbon(ctx, OUTER, 12, ease_out(t_outer), 1.0, glint)
    _ribbon(ctx, INNER, 8, ease_out(t_inner), 0.8,
            None if glint is None else (glint + 0.35) % 1.0)
    if sun > 0:
        rise = ease_out(sun)
        cy = 104 - 12 * rise
        halo = cairo.RadialGradient(64, cy, 0, 64, cy, 20 + 6 * glow)
        halo.add_color_stop_rgba(0, *AMBER, 0.55 * rise)
        halo.add_color_stop_rgba(1, *AMBER, 0.0)
        ctx.set_source(halo)
        ctx.arc(64, cy, 26 + 6 * glow, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(*AMBER, rise)
        ctx.arc(64, cy, 6 + glow, 0, 2 * math.pi)
        ctx.fill()
    ctx.restore()


def draw_wordmark(ctx, cx, y, size, alpha):
    if alpha <= 0:
        return
    ctx.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    text = "aurora"
    spacing = size * 0.18
    widths = [ctx.text_extents(c).x_advance for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = cx - total / 2
    ctx.set_source_rgba(*TEXT, alpha)
    for c, w in zip(text, widths):
        ctx.move_to(x, y)
        ctx.show_text(c)
        x += w + spacing


def frame(size, kind, i, background=False, word_y=0.86):
    """Render one animation frame: a square canvas, mark above wordmark."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surf)
    if background:
        ctx.set_source_rgb(*BG)
        ctx.paint()
    mark = size * 0.62
    ctx.save()
    ctx.translate((size - mark) / 2, size * 0.04)
    if kind == "intro":
        t = i / (INTRO_FRAMES - 1)
        draw_mark(ctx, mark, t_outer=t / 0.6, t_inner=(t - 0.2) / 0.6, sun=(t - 0.5) / 0.5)
        word = (t - 0.6) / 0.4
    elif kind == "loop":
        t = i / LOOP_FRAMES
        draw_mark(ctx, mark, glint=t, glow=0.5 + 0.5 * math.sin(2 * math.pi * t))
        word = 1.0
    else:  # static
        draw_mark(ctx, mark, glow=0.5)
        word = 1.0
    ctx.restore()
    draw_wordmark(ctx, size / 2, size * word_y, size * 0.1, max(0.0, min(1.0, word)))
    return surf


def write_frames(out, size):
    os.makedirs(out, exist_ok=True)
    for i in range(INTRO_FRAMES):
        frame(size, "intro", i).write_to_png(os.path.join(out, f"intro-{i:02d}.png"))
    for i in range(LOOP_FRAMES):
        frame(size, "loop", i).write_to_png(os.path.join(out, f"loop-{i:02d}.png"))


def write_gif(path, size):
    from PIL import Image
    images = []
    for kind, n in (("intro", INTRO_FRAMES), ("loop", LOOP_FRAMES), ("loop", LOOP_FRAMES)):
        for i in range(n):
            s = frame(size, kind, i, background=True)
            img = Image.frombuffer("RGBA", (size, size), bytes(s.get_data()),
                                   "raw", "BGRA", s.get_stride(), 1).convert("RGB")
            images.append(img.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    images[0].save(path, save_all=True, append_images=images[1:], duration=33, loop=0,
                   optimize=True)


def write_webp(path, size):
    """The same animation with real transparency (the glow blends into any page)."""
    from PIL import Image
    images = []
    for kind, n in (("intro", INTRO_FRAMES), ("loop", LOOP_FRAMES), ("loop", LOOP_FRAMES)):
        for i in range(n):
            # The website shows it large: the name sits closer under the mark.
            s = frame(size, kind, i, word_y=0.70)
            # cairo stores premultiplied BGRA; Pillow's "RGBa" mode undoes the premultiply.
            images.append(Image.frombuffer("RGBa", (size, size), bytes(s.get_data()),
                                           "raw", "BGRa", s.get_stride(), 1).convert("RGBA"))
    images[0].save(path, save_all=True, append_images=images[1:], duration=33, loop=0,
                   quality=90, method=6, lossless=False, allow_mixed=True)


def main():
    cmd, out = sys.argv[1], sys.argv[2]
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 256
    if cmd == "frames":
        write_frames(out, size)
    elif cmd == "gif":
        write_gif(out, size)
    elif cmd == "webp":
        write_webp(out, size)
    elif cmd == "png":
        frame(size, "static", 0, background=True).write_to_png(out)
    elif cmd == "static":
        frame(size, "static", 0).write_to_png(out)
    elif cmd == "mark":
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        draw_mark(cairo.Context(surf), size, glow=0.5)
        surf.write_to_png(out)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
