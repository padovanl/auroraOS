#!/usr/bin/env python3
"""Render the Aurora OS wallpapers procedurally.

Usage: generate.py OUTPUT_DIR [WIDTH HEIGHT]
"""

import math
import os
import random
import sys

import cairo

VARIANTS = {
    # name: (sky top, sky bottom, ribbon colors, ridge colors)
    "aurora-dawn": ((0.05, 0.03, 0.10), (0.16, 0.07, 0.20),
                    [(0.66, 0.44, 1.0), (1.0, 0.44, 0.57), (1.0, 0.64, 0.36)],
                    [(0.10, 0.06, 0.16), (0.06, 0.04, 0.10)]),
    "aurora-borealis": ((0.01, 0.04, 0.08), (0.03, 0.12, 0.16),
                        [(0.25, 1.0, 0.72), (0.30, 0.75, 1.0), (0.66, 0.44, 1.0)],
                        [(0.03, 0.08, 0.11), (0.01, 0.04, 0.06)]),
    "aurora-daylight": ((0.98, 0.84, 0.76), (0.80, 0.72, 0.96),
                        [(1.0, 1.0, 1.0), (1.0, 0.60, 0.70), (0.70, 0.55, 1.0)],
                        [(0.62, 0.50, 0.78), (0.45, 0.34, 0.60)]),
}


def ribbon(ctx, w, h, rng, color, base_y, amplitude, phase):
    """A soft glowing band: many translucent strokes with growing width."""
    points = []
    steps = 80
    for i in range(steps + 1):
        x = -0.1 * w + i * 1.2 * w / steps
        t = i / steps
        y = base_y + amplitude * math.sin(t * math.pi * 1.6 + phase) \
            + amplitude * 0.35 * math.sin(t * math.pi * 4.3 + phase * 2)
        points.append((x, y))
    for layer in range(28, 0, -1):
        width = layer * h * 0.012
        alpha = 0.010 + (28 - layer) * 0.0009
        ctx.set_source_rgba(*color, alpha)
        ctx.set_line_width(width)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(*points[0])
        for p in points[1:]:
            ctx.line_to(*p)
        ctx.stroke()
    # Vertical curtain rays rising from the band.
    for x, y in points[::2]:
        if rng.random() < 0.6:
            length = h * (0.05 + rng.random() * 0.18)
            grad = cairo.LinearGradient(x, y, x, y - length)
            grad.add_color_stop_rgba(0, *color, 0.07)
            grad.add_color_stop_rgba(1, *color, 0.0)
            ctx.set_source(grad)
            ctx.set_line_width(w * 0.004 + rng.random() * w * 0.006)
            ctx.move_to(x, y)
            ctx.line_to(x + rng.uniform(-8, 8), y - length)
            ctx.stroke()


def ridge(ctx, w, h, rng, color, base, roughness):
    ctx.move_to(0, h)
    y = base
    x = 0
    ctx.line_to(0, y)
    while x < w:
        x += w * (0.02 + rng.random() * 0.04)
        y = base + rng.uniform(-roughness, roughness)
        ctx.line_to(x, y)
    ctx.line_to(w, h)
    ctx.close_path()
    ctx.set_source_rgb(*color)
    ctx.fill()


def render(name, width, height, out_dir):
    top, bottom, ribbons, ridges = VARIANTS[name]
    rng = random.Random(name)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    ctx = cairo.Context(surface)

    sky = cairo.LinearGradient(0, 0, 0, height)
    sky.add_color_stop_rgb(0, *top)
    sky.add_color_stop_rgb(1, *bottom)
    ctx.set_source(sky)
    ctx.paint()

    light = sum(top) > 1.5
    if not light:
        for _ in range(int(width * height / 6000)):
            x, y = rng.random() * width, rng.random() * height * 0.75
            r = rng.random() * 1.3 + 0.2
            ctx.set_source_rgba(1, 1, 1, rng.random() * 0.7 + 0.1)
            ctx.arc(x, y, r, 0, 2 * math.pi)
            ctx.fill()

    ctx.set_operator(cairo.OPERATOR_ADD if not light else cairo.OPERATOR_OVER)
    for i, color in enumerate(ribbons):
        ribbon(ctx, width, height, rng, color,
               base_y=height * (0.30 + 0.12 * i),
               amplitude=height * (0.10 - 0.02 * i),
               phase=rng.random() * math.pi * 2)
    ctx.set_operator(cairo.OPERATOR_OVER)

    ridge(ctx, width, height, rng, ridges[0], height * 0.80, height * 0.04)
    ridge(ctx, width, height, rng, ridges[1], height * 0.88, height * 0.025)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.png")
    surface.write_to_png(path)
    return path


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 3840
    h = int(sys.argv[3]) if len(sys.argv) > 3 else 2160
    for name in VARIANTS:
        print(render(name, w, h, out))


if __name__ == "__main__":
    main()
