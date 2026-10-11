#!/usr/bin/env python3
"""Draw the grain of Aurora's glass: desktop/data/style/noise.png.

Frosted glass is never a flat wash of colour — it scatters light, and the eye
reads that scattering as a very fine grain. The shell lays this tile over the
top bar, the dock, Spotlight and the Control Center at a few percent of
opacity: too faint to see as texture, enough to stop a large pane from looking
like a rectangle of paint. Random noise tiles without a seam, so 128×128 is
enough for any screen.

Usage: tools/glass-noise.py
"""

import os
import random

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "desktop", "data", "style", "noise.png")
SIZE = 128
ALPHA = 6           # of 255: the strength of one grain of light or shadow
SEED = 20261010     # the same picture at every build


def build():
    random.seed(SEED)
    image = Image.new("RGBA", (SIZE, SIZE))
    pixels = []
    for _ in range(SIZE * SIZE):
        # Half the grains lighten, half darken; most pixels stay untouched, or
        # the grain reads as dirt instead of as light.
        roll = random.random()
        if roll < 0.18:
            pixels.append((255, 255, 255, random.randint(1, ALPHA)))
        elif roll < 0.36:
            pixels.append((0, 0, 0, random.randint(1, ALPHA)))
        else:
            pixels.append((0, 0, 0, 0))
    image.putdata(pixels)
    image.save(TARGET, optimize=True)
    return os.path.getsize(TARGET)


if __name__ == "__main__":
    print(f"{TARGET}: {SIZE}×{SIZE}, {build()} bytes")
