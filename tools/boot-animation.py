#!/usr/bin/env python3
"""Make the transparent copy of the boot animation used in the README.

docs/aurora-boot.gif is a recording of Plymouth, so every frame carries the
boot screen's flat background. GitHub shows the README on white or on dark
depending on the reader, and a square of near-black around the logo looks like
a hole in the page. This keys that background out: the animation is rebuilt as
an APNG (GIF has no soft transparency, and the logo's glow needs it), where
each pixel's alpha is how much light there is and its colour is that light's
own colour, so the glow fades to nothing on a page of any colour.

Usage: tools/boot-animation.py [--check]
"""

import os
import sys

from PIL import Image, ImageFilter, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "docs", "aurora-boot.gif")
TARGET = os.path.join(ROOT, "docs", "aurora-boot.png")
HEIGHT = 160        # the README shows it about this big
KEEP = 5            # one frame in five: 150 ms each, which with the rounding
                    # below keeps the file about as light as the GIF it replaces
MARGIN = 4          # breathing room around the drawing
GLOW_BLUR = 1.6     # dissolves the GIF palette's steps in the glow
GLOW_FALLOFF = 1.45  # the faint outer half of the halo fades out sooner
COLOUR_STEP = 16     # the glow's colour, rounded: invisible, and much lighter


def keyed(frame, bg):
    """One frame over nothing.

    The boot screen is a glow *added* to a flat near-black, so the honest way
    out of it is to subtract that background and read what is left as light:
    how bright the light is becomes the alpha, and the light's own colour —
    not the light mixed back into the background — becomes the pixel. Adding
    the background back in, as this used to, left every half-transparent pixel
    carrying a bit of the boot screen's black, which is the grey veil on a
    white page and the dirty ring on a dark one.
    """
    frame = frame.convert("RGB")
    out = Image.new("RGBA", frame.size)
    pixels = []
    for r, g, b in frame.getdata():
        light = (r - bg[0], g - bg[1], b - bg[2])
        brightest = max(light)
        if brightest <= 1:
            pixels.append((0, 0, 0, 0))
            continue
        # The light at full strength: its colour, with the brightest channel
        # taken to 255, and how much of it there is kept in the alpha.
        scale = 255 / brightest
        pixels.append((
            max(0, min(255, round(light[0] * scale))),
            max(0, min(255, round(light[1] * scale))),
            max(0, min(255, round(light[2] * scale))),
            min(255, brightest),
        ))
    out.putdata(pixels)
    return _smooth(out)


def _smooth(frame):
    """The recording is a 256-colour GIF, so its glow comes in steps and the
    halo ends on a visible edge. Blurring the transparency alone dissolves
    those steps without touching the drawing, and bending it down makes the
    faint outer half fade out sooner, which is what stops the halo reading as
    a ring on a dark page."""
    r, g, b, a = frame.split()
    a = a.filter(ImageFilter.GaussianBlur(GLOW_BLUR))
    a = a.point(lambda v: round(255 * (v / 255) ** GLOW_FALLOFF))
    # The colour, unlike the transparency, can be rounded without being seen:
    # it is a smooth warm gradient, and this is what keeps the file as light
    # as the GIF it replaces.
    quantise = (lambda v: min(255, round(v / COLOUR_STEP) * COLOUR_STEP))
    return Image.merge("RGBA", (r.point(quantise), g.point(quantise),
                                b.point(quantise), a))


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
    frames = [f.crop(box).resize((width, HEIGHT), Image.LANCZOS) for f in frames]
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
