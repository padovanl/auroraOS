#!/usr/bin/env python3
"""Make the website's wallpaper images from branding/wallpapers/:
docs/assets/hero.jpg (the page background) and
docs/screenshots/dynamic-wallpaper.jpg (every series at dawn, day, dusk, night).

Usage: tools/site-wallpapers.py
"""

import os

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SOURCE = os.path.join(ROOT, "branding", "wallpapers")
SERIES = ("starfall", "veil", "horizon")
PHASES = ("dawn", "day", "dusk", "night")
CELL, GAP = (480, 270), 4


def main():
    hero = Image.open(os.path.join(SOURCE, "starfall", "dusk.png")).convert("RGB")
    hero.resize((1920, 1080), Image.LANCZOS).save(
        os.path.join(ROOT, "docs", "assets", "hero.jpg"), quality=86, optimize=True,
        progressive=True)
    width = len(PHASES) * CELL[0] + (len(PHASES) - 1) * GAP
    height = len(SERIES) * CELL[1] + (len(SERIES) - 1) * GAP
    grid = Image.new("RGB", (width, height), (12, 9, 21))
    for row, series in enumerate(SERIES):
        for column, phase in enumerate(PHASES):
            picture = Image.open(os.path.join(SOURCE, series, f"{phase}.png")).convert("RGB")
            grid.paste(picture.resize(CELL, Image.LANCZOS),
                       (column * (CELL[0] + GAP), row * (CELL[1] + GAP)))
    grid.save(os.path.join(ROOT, "docs", "screenshots", "dynamic-wallpaper.jpg"), quality=88,
              optimize=True, progressive=True)


if __name__ == "__main__":
    main()
