#!/usr/bin/env python3
"""Render raster branding assets with cairo (no SVG renderer needed).

Usage: render.py OUTPUT_DIR
Writes the plymouth animation frames and the GRUB theme images.
"""

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
    ctx.translate(960 - 64, 150)
    logo.draw_mark(ctx, 128)
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
