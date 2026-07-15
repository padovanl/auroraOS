#!/usr/bin/env python3
"""Render raster branding assets with cairo (no SVG renderer needed).

Usage: render.py OUTPUT_DIR
Writes plymouth/{logo,dot}.png and grub/{background.png}.
"""

import math
import os
import sys

import cairo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "wallpapers"))
import generate  # noqa: E402

VIOLET = (0.66, 0.44, 1.0)
ROSE = (1.0, 0.44, 0.57)
AMBER = (1.0, 0.64, 0.36)


def ribbon_gradient(x0, y0, x1, y1):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    g.add_color_stop_rgb(0, *AMBER)
    g.add_color_stop_rgb(0.5, *ROSE)
    g.add_color_stop_rgb(1, *VIOLET)
    return g


def draw_logo(ctx, size):
    """The Aurora mark (two arcs + dot), matching aurora-logo.svg without the tile."""
    s = size / 128.0
    ctx.save()
    ctx.scale(s, s)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_source(ribbon_gradient(24, 98, 104, 26))
    ctx.set_line_width(12)
    ctx.move_to(24, 98)
    ctx.curve_to(38, 58, 58, 30, 64, 26)
    ctx.curve_to(70, 30, 90, 58, 104, 98)
    ctx.stroke()
    ctx.set_line_width(8)
    ctx.push_group()
    ctx.set_source(ribbon_gradient(42, 98, 86, 58))
    ctx.move_to(42, 98)
    ctx.curve_to(50, 76, 58, 62, 64, 58)
    ctx.curve_to(70, 62, 78, 76, 86, 98)
    ctx.stroke()
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(0.75)
    ctx.set_source_rgb(*AMBER)
    ctx.arc(64, 92, 6, 0, 2 * math.pi)
    ctx.fill()
    ctx.restore()


def plymouth(out):
    os.makedirs(out, exist_ok=True)
    size = 160
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    draw_logo(cairo.Context(surf), size)
    surf.write_to_png(os.path.join(out, "logo.png"))

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 12, 12)
    ctx = cairo.Context(surf)
    ctx.set_source_rgb(0.95, 0.93, 0.98)
    ctx.arc(6, 6, 5, 0, 2 * math.pi)
    ctx.fill()
    surf.write_to_png(os.path.join(out, "dot.png"))


def grub(out):
    os.makedirs(out, exist_ok=True)
    path = generate.render("aurora-dawn", 1920, 1080, out)
    os.replace(path, os.path.join(out, "background.png"))
    surf = cairo.ImageSurface.create_from_png(os.path.join(out, "background.png"))
    ctx = cairo.Context(surf)
    # Darken so the menu stays readable, then stamp the logo on top.
    ctx.set_source_rgba(0.03, 0.02, 0.06, 0.55)
    ctx.paint()
    ctx.translate(960 - 64, 150)
    draw_logo(ctx, 128)
    surf.write_to_png(os.path.join(out, "background.png"))

    # Menu highlight and terminal box (centre pieces of GRUB's 9-slice images).
    for name, rgba in (("select_c.png", (0.66, 0.44, 1.0, 0.35)),
                       ("terminal_box_c.png", (0.08, 0.06, 0.12, 0.9))):
        piece = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
        c = cairo.Context(piece)
        c.set_source_rgba(*rgba)
        c.paint()
        piece.write_to_png(os.path.join(out, name))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build"
    plymouth(os.path.join(out, "plymouth"))
    grub(os.path.join(out, "grub"))


if __name__ == "__main__":
    main()
