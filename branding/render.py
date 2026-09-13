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


def _rounded(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _nine_slice(out, prefix, size, r, paint):
    """Draw a rounded box of size x size and cut it into GRUB's 9-slice pieces
    (PREFIX_nw.png … PREFIX_se.png), so GRUB can stretch it to any size."""
    box = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    paint(cairo.Context(box), size)
    pieces = {"nw": (0, 0, r, r), "n": (r, 0, size - 2 * r, r), "ne": (size - r, 0, r, r),
              "w": (0, r, r, size - 2 * r), "c": (r, r, size - 2 * r, size - 2 * r),
              "e": (size - r, r, r, size - 2 * r), "sw": (0, size - r, r, r),
              "s": (r, size - r, size - 2 * r, r), "se": (size - r, size - r, r, r)}
    for name, (x, y, w, h) in pieces.items():
        piece = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        pc = cairo.Context(piece)
        pc.set_source_surface(box, -x, -y)
        pc.paint()
        piece.write_to_png(os.path.join(out, f"{prefix}_{name}.png"))


def _grub_background(path, w=1920, h=1080):
    """Calm night sky: the aurora only glows along the top, nothing behind the menu."""
    import random
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    c = cairo.Context(surf)
    base = cairo.LinearGradient(0, 0, 0, h)
    base.add_color_stop_rgb(0, 0.055, 0.043, 0.098)
    base.add_color_stop_rgb(1, 0.035, 0.027, 0.063)
    c.set_source(base)
    c.paint()
    for cx, cy, rad, (r, g, b), a in ((0.18, -0.10, 0.55, (0.33, 0.88, 0.72), 0.20),
                                     (0.50, -0.18, 0.60, (0.66, 0.44, 1.00), 0.30),
                                     (0.84, -0.08, 0.50, (1.00, 0.44, 0.57), 0.20)):
        g_ = cairo.RadialGradient(cx * w, cy * h, 0, cx * w, cy * h, rad * w)
        g_.add_color_stop_rgba(0, r, g, b, a)
        g_.add_color_stop_rgba(1, r, g, b, 0)
        c.set_source(g_)
        c.paint()
    rnd = random.Random(7)
    for _ in range(170):
        x, y = rnd.random() * w, rnd.random() * h * 0.75
        c.set_source_rgba(1, 1, 1, 0.15 + rnd.random() * 0.45)
        c.arc(x, y, 0.5 + rnd.random() * 1.1, 0, 2 * math.pi)
        c.fill()
    vignette = cairo.RadialGradient(w / 2, h * 0.45, h * 0.35, w / 2, h * 0.45, w * 0.75)
    vignette.add_color_stop_rgba(0, 0, 0, 0, 0)
    vignette.add_color_stop_rgba(1, 0, 0, 0, 0.45)
    c.set_source(vignette)
    c.paint()
    surf.write_to_png(path)


ICON = 24


def _icon(out, name, draw):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ICON, ICON)
    c = cairo.Context(surf)
    c.set_source_rgba(0.95, 0.93, 0.98, 0.95)
    c.set_line_width(1.8)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    draw(c)
    surf.write_to_png(os.path.join(out, f"{name}.png"))


def _grub_icons(out):
    """One small line icon per boot entry (menuentry --class NAME)."""
    os.makedirs(out, exist_ok=True)

    def play(c):  # Try: start the live system
        c.arc(12, 12, 9.2, 0, 2 * math.pi)
        c.stroke()
        c.move_to(10, 8.2)
        c.line_to(16, 12)
        c.line_to(10, 15.8)
        c.close_path()
        c.fill()

    def install(c):  # Install: arrow down into a drive
        c.move_to(12, 3.5)
        c.line_to(12, 13)
        c.move_to(8, 9.5)
        c.line_to(12, 13.5)
        c.line_to(16, 9.5)
        c.stroke()
        _rounded(c, 3.5, 15.5, 17, 5.5, 1.8)
        c.stroke()

    def safe(c):  # Safe graphics: a screen
        _rounded(c, 3, 4.5, 18, 12, 2)
        c.stroke()
        c.move_to(9, 20)
        c.line_to(15, 20)
        c.move_to(12, 16.5)
        c.line_to(12, 20)
        c.stroke()

    def language(c):  # Languages: a globe
        c.arc(12, 12, 9, 0, 2 * math.pi)
        c.stroke()
        c.save()
        c.translate(12, 12)
        c.scale(0.45, 1)
        c.arc(0, 0, 9, 0, 2 * math.pi)
        c.restore()
        c.stroke()
        c.move_to(3.3, 9)
        c.line_to(20.7, 9)
        c.move_to(3.3, 15)
        c.line_to(20.7, 15)
        c.stroke()

    def disk(c):  # Boot from hard disk
        _rounded(c, 3, 6, 18, 12, 2.5)
        c.stroke()
        c.arc(16.5, 12, 1.4, 0, 2 * math.pi)
        c.fill()
        c.move_to(6.5, 12)
        c.line_to(11, 12)
        c.stroke()

    def firmware(c):  # UEFI firmware settings: a gear
        c.arc(12, 12, 3.2, 0, 2 * math.pi)
        c.stroke()
        for k in range(8):
            a = k * math.pi / 4
            c.move_to(12 + 6.2 * math.cos(a), 12 + 6.2 * math.sin(a))
            c.line_to(12 + 9.2 * math.cos(a), 12 + 9.2 * math.sin(a))
        c.stroke()
        c.arc(12, 12, 6.2, 0, 2 * math.pi)
        c.stroke()

    for name, draw in (("try", play), ("install", install), ("safe", safe),
                       ("language", language), ("disk", disk), ("firmware", firmware)):
        _icon(out, name, draw)


def grub(out):
    os.makedirs(out, exist_ok=True)
    _grub_background(os.path.join(out, "background.png"))

    # The mark as its own image, so it keeps its shape on any screen ratio.
    logo_size = 112
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, logo_size, logo_size)
    logo.draw_mark(cairo.Context(surf), logo_size, glow=0.6)
    surf.write_to_png(os.path.join(out, "logo.png"))

    # The menu sits on a dark, slightly lighter card with a thin border.
    def card(c, size):
        _rounded(c, 0.5, 0.5, size - 1, size - 1, 17.5)
        c.set_source_rgba(0.10, 0.08, 0.16, 0.82)
        c.fill_preserve()
        c.set_source_rgba(1, 1, 1, 0.10)
        c.set_line_width(1)
        c.stroke()
    _nine_slice(out, "menu", 60, 20, card)

    # The chosen entry: a soft violet-to-rose pill.
    def pill(c, size):
        _rounded(c, 0, 0, size, size, 12)
        grad = cairo.LinearGradient(0, 0, size, 0)
        grad.add_color_stop_rgba(0, 0.66, 0.44, 1.0, 0.85)
        grad.add_color_stop_rgba(1, 1.0, 0.44, 0.57, 0.75)
        c.set_source(grad)
        c.fill()
    _nine_slice(out, "select", 40, 14, pill)
    # The other entries get an invisible box with the same borders: GRUB offsets an
    # entry's text by its box's top border, so without it the chosen entry would sit
    # lower than the rest and the rows would be unevenly spaced.
    _nine_slice(out, "item", 40, 14, lambda c, size: None)

    _grub_icons(os.path.join(out, "icons"))

    box = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
    c = cairo.Context(box)
    c.set_source_rgba(0.08, 0.06, 0.12, 0.92)
    c.paint()
    box.write_to_png(os.path.join(out, "terminal_box_c.png"))


def installer_marks(out, size=22):
    """The installer's checkbox tick, radio dot and "mixed" dash as PNGs: Qt
    style sheets only load SVG with an extra image plugin the image lacks."""
    os.makedirs(out, exist_ok=True)

    def mark(name, draw):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        c = cairo.Context(surf)
        c.scale(size / 22, size / 22)
        c.set_source_rgba(1, 1, 1, 1)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        draw(c)
        surf.write_to_png(os.path.join(out, f"{name}.png"))

    def tick(c):
        c.set_line_width(2.6)
        c.move_to(6.2, 11.4)
        c.line_to(9.6, 14.6)
        c.line_to(15.9, 7.6)
        c.stroke()

    def dot(c):
        c.arc(11, 11, 4.2, 0, 2 * math.pi)
        c.fill()

    def dash(c):
        c.set_line_width(2.6)
        c.move_to(6.5, 11)
        c.line_to(15.5, 11)
        c.stroke()

    for name, draw in (("check", tick), ("radio", dot), ("dash", dash)):
        mark(name, draw)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "build"
    plymouth(os.path.join(out, "plymouth"))
    grub(os.path.join(out, "grub"))
    installer_marks(os.path.join(out, "calamares"))


if __name__ == "__main__":
    main()
