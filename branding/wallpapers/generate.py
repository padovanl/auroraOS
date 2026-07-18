#!/usr/bin/env python3
"""Render the Aurora OS wallpapers procedurally.

Usage: generate.py OUTPUT_DIR [WIDTH HEIGHT]

The aurora is computed per pixel (numpy): each ribbon is a soft luminous
band with a curtain of light rising above it, gently folded along its
length. Highlights are tone-mapped instead of clipped, and the result is
dithered so gradients show no banding. Stars and mountain ridges are drawn
with cairo on top.
"""

import math
import os
import sys

import cairo
import numpy as np

# name: (sky top, sky bottom, ribbon colors (lower edge, upper tail), ridges, light theme)
VARIANTS = {
    "aurora-dawn": ((0.04, 0.025, 0.08), (0.13, 0.06, 0.17),
                    [((1.0, 0.62, 0.36), (1.0, 0.36, 0.55)),
                     ((1.0, 0.42, 0.58), (0.62, 0.40, 1.0)),
                     ((0.70, 0.48, 1.0), (0.40, 0.36, 0.95))],
                    [(0.10, 0.06, 0.16), (0.055, 0.035, 0.09)], False),
    "aurora-borealis": ((0.01, 0.03, 0.06), (0.03, 0.10, 0.14),
                        [((0.30, 1.0, 0.70), (0.25, 0.70, 1.0)),
                         ((0.35, 0.95, 0.80), (0.55, 0.45, 1.0)),
                         ((0.45, 0.80, 1.0), (0.66, 0.44, 1.0))],
                        [(0.03, 0.075, 0.10), (0.01, 0.035, 0.055)], False),
    "aurora-daylight": ((0.62, 0.66, 0.92), (0.96, 0.78, 0.80),
                        [((1.0, 0.96, 0.92), (1.0, 0.72, 0.80)),
                         ((1.0, 0.60, 0.70), (0.80, 0.62, 1.0)),
                         ((0.70, 0.56, 1.0), (0.90, 0.80, 1.0))],
                        [(0.62, 0.50, 0.78), (0.45, 0.34, 0.60)], True),
}


def smooth_noise(n, rng, scales):
    """1-D smooth noise in [-1, 1]: a sum of sines with random phases."""
    x = np.linspace(0, 1, n)
    out = np.zeros(n)
    total = 0.0
    for freq, amp in scales:
        out += amp * np.sin(2 * math.pi * (freq * x + rng.random()))
        total += amp
    return out / total


def ribbon_field(w, h, rng, base, amp, lower, upper):
    """Intensity (h, w) of one aurora curtain, plus its vertical position factor."""
    xs = np.linspace(0, 1, w)
    phase = rng.random() * 2 * math.pi
    center = (base + amp * np.sin(xs * math.pi * 1.5 + phase)
              + amp * 0.35 * np.sin(xs * math.pi * 3.7 + phase * 2)
              + amp * 0.03 * smooth_noise(w, rng, [(5, 1), (8, 0.5)])) * h
    y = np.arange(h)[:, None]
    d = center[None, :] - y            # > 0 above the ribbon's center line
    # A soft luminous band (like the original stroke-drawn ribbons) plus a
    # faint curtain rising above it.
    band = np.exp(-(d / (lower * h)) ** 2)
    # Continuous at the center line: exponential tail above, gaussian below.
    rise = np.where(d > 0, np.exp(-np.maximum(d, 0) / (upper * h)),
                    np.exp(-(np.minimum(d, 0) / (lower * h * 0.8)) ** 2))
    along = 0.6 + 0.4 * (0.5 + 0.5 * smooth_noise(w, rng, [(2, 1), (5, 0.6), (11, 0.3)]))
    # Low-contrast, wide folds in the curtain only: soft texture, no lines.
    # Curtain folds: continuous sine modulation, so they read as soft
    # shimmering rays rather than drawn lines.
    folds = 0.68 + 0.32 * (0.5 + 0.5 * smooth_noise(w, rng, [(19, 1), (29, 0.55), (7, 0.8)]))
    field = (band + 0.85 * rise * folds[None, :]) * along[None, :]
    t = np.clip(d / (upper * h * 1.6), 0, 1)
    return field, t


def render(name, width, height, out_dir):
    top, bottom, ribbons, ridges, light = VARIANTS[name]
    rng = np.random.default_rng(sum(map(ord, name)))
    h, w = height, width

    gy = np.linspace(0, 1, h)[:, None, None]
    img = np.array(top)[None, None, :] * (1 - gy) + np.array(bottom)[None, None, :] * gy
    img = np.broadcast_to(img, (h, w, 3)).copy()

    light_acc = np.zeros((h, w, 3))
    for i, (low_c, up_c) in enumerate(ribbons):
        field, t = ribbon_field(w, h, rng, base=0.36 + 0.11 * i, amp=0.085 - 0.02 * i,
                                lower=0.028 - 0.004 * i, upper=0.20 - 0.04 * i)
        color = (np.array(low_c)[None, None, :] * (1 - t[..., None])
                 + np.array(up_c)[None, None, :] * t[..., None])
        strength = 0.75 - 0.12 * i
        light_acc += color * field[..., None] * strength

    if light:
        # Screen blend: light can only brighten a light sky, never gray it.
        glow = 1 - np.exp(-light_acc * 1.3)
        img = 1 - (1 - img) * (1 - glow * 0.85)
    else:
        # Additive light, tone-mapped so bright overlaps stay colorful.
        img = img + 1 - np.exp(-light_acc * 1.1)
    img = np.clip(img, 0, 1)

    # Dither before quantizing to 8 bits to avoid banding.
    img = img * 255 + rng.uniform(-0.5, 0.5, size=img.shape)
    img = np.clip(np.round(img), 0, 255).astype(np.uint8)

    # numpy RGB → cairo BGRA
    bgra = np.empty((h, w, 4), dtype=np.uint8)
    bgra[..., 0], bgra[..., 1], bgra[..., 2], bgra[..., 3] = img[..., 2], img[..., 1], img[..., 0], 255
    surface = cairo.ImageSurface.create_for_data(memoryview(bgra), cairo.FORMAT_RGB24, w, h,
                                                 w * 4)
    ctx = cairo.Context(surface)

    if not light:
        prng = np.random.default_rng(7)
        for _ in range(int(w * h / 5000)):
            x, y = prng.random() * w, prng.random() * h * 0.72
            r = (prng.random() ** 3) * 1.4 * (w / 1920) + 0.35
            a = prng.random() * 0.6 + 0.15
            glow = cairo.RadialGradient(x, y, 0, x, y, r * 2.2)
            glow.add_color_stop_rgba(0, 1, 1, 1, a)
            glow.add_color_stop_rgba(1, 1, 1, 1, 0)
            ctx.set_source(glow)
            ctx.arc(x, y, r * 2.2, 0, 2 * math.pi)
            ctx.fill()

    # Haze glowing behind the mountains.
    haze = cairo.LinearGradient(0, h * 0.62, 0, h * 0.84)
    r, g, b = ribbons[-1][0]
    haze.add_color_stop_rgba(0, r, g, b, 0)
    haze.add_color_stop_rgba(1, r, g, b, 0.10 if not light else 0.25)
    ctx.set_source(haze)
    ctx.rectangle(0, h * 0.62, w, h * 0.3)
    ctx.fill()

    ridge_rng = np.random.default_rng(11)
    for (color, base, rough) in ((ridges[0], 0.80, 0.045), (ridges[1], 0.885, 0.028)):
        ctx.move_to(0, h)
        x = 0.0
        ctx.line_to(0, base * h)
        while x < w:
            x += w * (0.025 + ridge_rng.random() * 0.045)
            ctx.line_to(x, (base + ridge_rng.uniform(-rough, rough)) * h)
        ctx.line_to(w, h)
        ctx.close_path()
        ctx.set_source_rgb(*color)
        ctx.fill()

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
