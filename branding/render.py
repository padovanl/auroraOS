#!/usr/bin/env python3
"""Render raster branding assets with cairo (no SVG renderer needed).

Usage: render.py OUTPUT_DIR
Writes the plymouth animation frames and the GRUB theme images.
"""

import math
import os
import sys

import cairo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "wallpapers"))
sys.path.insert(0, HERE)
import generate  # noqa: E402
import logo  # noqa: E402

def plymouth(out):
    logo.write_frames(out, 300)


def grub(out):
    os.makedirs(out, exist_ok=True)
    path = generate.render("aurora-dawn", 1920, 1080, out)
    os.replace(path, os.path.join(out, "background.png"))
    surf = cairo.ImageSurface.create_from_png(os.path.join(out, "background.png"))
    ctx = cairo.Context(surf)
    # Darken so the menu stays readable, then stamp the logo on top.
    ctx.set_source_rgba(0.03, 0.02, 0.06, 0.55)
    ctx.paint()
    ctx.translate(960 - 70, 200)
    logo.draw_mark(ctx, 140)
    surf.write_to_png(os.path.join(out, "background.png"))

    # Menu highlight: a rounded rectangle cut into GRUB's 9-slice pieces.
    r, size = 10, 30
    sel = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    c = cairo.Context(sel)
    c.new_sub_path()
    for cx, cy, a in ((size - r, r, -math.pi / 2), (size - r, size - r, 0),
                      (r, size - r, math.pi / 2), (r, r, math.pi)):
        c.arc(cx, cy, r, a, a + math.pi / 2)
    c.close_path()
    grad = cairo.LinearGradient(0, 0, size, 0)
    grad.add_color_stop_rgba(0, 0.66, 0.44, 1.0, 0.55)
    grad.add_color_stop_rgba(1, 1.0, 0.44, 0.57, 0.45)
    c.set_source(grad)
    c.fill()
    pieces = {"nw": (0, 0, r, r), "n": (r, 0, size - 2 * r, r), "ne": (size - r, 0, r, r),
              "w": (0, r, r, size - 2 * r), "c": (r, r, size - 2 * r, size - 2 * r),
              "e": (size - r, r, r, size - 2 * r), "sw": (0, size - r, r, r),
              "s": (r, size - r, size - 2 * r, r), "se": (size - r, size - r, r, r)}
    for name, (x, y, w, h) in pieces.items():
        piece = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        pc = cairo.Context(piece)
        pc.set_source_surface(sel, -x, -y)
        pc.paint()
        piece.write_to_png(os.path.join(out, f"select_{name}.png"))

    box = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
    c = cairo.Context(box)
    c.set_source_rgba(0.08, 0.06, 0.12, 0.9)
    c.paint()
    box.write_to_png(os.path.join(out, "terminal_box_c.png"))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build"
    plymouth(os.path.join(out, "plymouth"))
    grub(os.path.join(out, "grub"))


if __name__ == "__main__":
    main()
