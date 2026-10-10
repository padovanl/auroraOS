#!/usr/bin/env python3
"""Make the transparent copy of the boot animation used in the README.

docs/aurora-boot.gif is a recording of Plymouth, so every frame carries the
boot screen's flat background. GitHub shows the README on white or on dark
depending on the reader, and a square of near-black around the logo looks like
a hole in the page. This keys that background out: the animation is rebuilt as
an APNG (GIF has no soft transparency, and the logo's glow needs it), where
each pixel's alpha is how far it stands from the background and its color is
what it would be over nothing.

Usage: tools/boot-animation.py [--check]
"""

import os
import sys

from PIL import Image, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "docs", "aurora-boot.gif")
TARGET = os.path.join(ROOT, "docs", "aurora-boot.png")
HEIGHT = 160        # the README shows it about this big
ALPHA_STEP = 8      # steps of the glow's transparency: fewer compress better
KEEP = 4            # one frame in four: 120 ms each, and a file no heavier
                    # than the GIF it replaces
MARGIN = 4          # breathing room around the drawing


def keyed(frame, bg):
    """One frame over nothing: alpha from the distance to the background,
    color un-mixed from it, so the glow fades out instead of ending in a
    dark fringe."""
    frame = frame.convert("RGB")
    out = Image.new("RGBA", frame.size)
    pixels = []
    for r, g, b in frame.getdata():
        # How much of this pixel is not the background (the background is
        # nearly black, so every channel only ever rises above it).
        alpha = max((r - bg[0]) / max(1, 255 - bg[0]),
                    (g - bg[1]) / max(1, 255 - bg[1]),
                    (b - bg[2]) / max(1, 255 - bg[2]), 0.0)
        if alpha <= 0.004:
            pixels.append((0, 0, 0, 0))
            continue
        pixels.append((
            min(255, round(bg[0] + (r - bg[0]) / alpha)),
            min(255, round(bg[1] + (g - bg[1]) / alpha)),
            min(255, round(bg[2] + (b - bg[2]) / alpha)),
            min(255, round(alpha * 255)),
        ))
    out.putdata(pixels)
    return out


def _posterize(frame):
    """Round the glow's transparency to a few steps: invisible to the eye, and
    it keeps the file as light as the GIF it replaces."""
    r, g, b, a = frame.split()
    a = a.point(lambda v: min(255, round(v / ALPHA_STEP) * ALPHA_STEP))
    return Image.merge("RGBA", (r, g, b, a))


def mark_only(box, frames):
    """Cut the word under the logo away: it is drawn in white, which vanishes
    on a white page, and the README says the name right next to the picture.
    The two are separated by rows no frame ever paints."""
    rows = [any(frame.crop((box[0], y, box[2], y + 1)).getbbox() for frame in frames)
            for y in range(box[1], box[3])]
    gap_start = gap_len = best_start = best_len = 0
    for i, painted in enumerate(rows + [True]):
        if not painted:
            if gap_len == 0:
                gap_start = i
            gap_len += 1
            continue
        if gap_len > best_len and gap_start > 0:
            best_start, best_len = gap_start, gap_len
        gap_len = 0
    if best_len < 6:            # no clear gap: keep the whole thing
        return box
    return (box[0], box[1], box[2], box[1] + best_start)


def union_box(frames, size):
    """The smallest box holding the drawing in every frame: the recording is a
    square screen, and most of it is empty."""
    box = None
    for frame in frames:
        here = frame.getbbox()
        if here is None:
            continue
        box = here if box is None else (min(box[0], here[0]), min(box[1], here[1]),
                                        max(box[2], here[2]), max(box[3], here[3]))
    if box is None:
        return (0, 0, *size)
    return (max(0, box[0] - MARGIN), max(0, box[1] - MARGIN),
            min(size[0], box[2] + MARGIN), min(size[1], box[3] + MARGIN))


def build():
    source = Image.open(SOURCE)
    background = source.convert("RGB").getpixel((0, 0))
    frames = [keyed(f, background)
              for i, f in enumerate(ImageSequence.Iterator(source)) if i % KEEP == 0]
    box = mark_only(union_box(frames, frames[0].size), frames)
    width = round((box[2] - box[0]) * HEIGHT / (box[3] - box[1]))
    frames = [_posterize(f.crop(box).resize((width, HEIGHT), Image.LANCZOS))
              for f in frames]
    duration = source.info.get("duration", 30) * KEEP
    frames[0].save(TARGET, save_all=True, append_images=frames[1:], loop=0,
                   duration=duration, disposal=2, optimize=True, default_image=False)
    return len(frames), duration, frames[0].size


if __name__ == "__main__":
    if "--check" in sys.argv:
        if not os.path.exists(TARGET):
            sys.exit(f"missing {TARGET}: run tools/boot-animation.py")
        sys.exit(0)
    count, duration, size = build()
    print(f"{TARGET}: {count} frames of {duration} ms at {size[0]}×{size[1]}, "
          f"{os.path.getsize(TARGET) / 1024:.0f} kB")
