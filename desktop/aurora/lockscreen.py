"""The lock screen's picture, from Settings → Appearance → Lock Screen:
the desktop's own, the desktop's blurred, or a picture of its own.

    python3 lockscreen.py DESKTOP_PICTURE   → prints the picture to show

Blurred copies are made once per picture and kept in ~/.cache/aurora.
"""

import hashlib
import os
import sys

MODES = ("desktop", "blurred", "picture")


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aurora", "lock")


def blurred(path):
    """A softly blurred, slightly darker copy of a picture (made once)."""
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return path
    key = hashlib.sha1(f"{path}\0{stamp}".encode()).hexdigest()[:16]
    out = os.path.join(cache_dir(), f"blurred-{key}.jpg")
    if os.path.exists(out):
        return out
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        image = Image.open(path).convert("RGB")
        image.thumbnail((1920, 1920))
        image = image.filter(ImageFilter.GaussianBlur(radius=max(image.size) / 60))
        image = ImageEnhance.Brightness(image).enhance(0.82)
        os.makedirs(cache_dir(), exist_ok=True)
        for old in os.listdir(cache_dir()):
            if old.startswith("blurred-"):
                os.remove(os.path.join(cache_dir(), old))
        image.save(out, quality=90)
        return out
    except (ImportError, OSError, ValueError):
        return path


def picture(desktop, mode, own):
    """The picture the lock screen shows."""
    if mode == "picture" and own and os.path.isfile(own):
        return own
    if mode == "blurred" and desktop and os.path.isfile(desktop):
        return blurred(desktop)
    return desktop


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from aurora import settings
    s = settings.get()
    mode = s.get_string("lock-background") if s is not None else "desktop"
    own = s.get_string("lock-picture") if s is not None else ""
    print(picture(sys.argv[1] if len(sys.argv) > 1 else "", mode, own))


if __name__ == "__main__":
    main()
