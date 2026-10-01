"""Files' tools for pictures and open files, like PowerToys' Image Resizer and
File Locksmith.

Resize Images…: make smaller copies (or resize in place) at a preset size,
keeping the proportions, optionally as JPEG or PNG.
What's Using This?: the processes that have a file, or anything inside a
folder, open (you can only see your own processes)."""

import os

SIZES = (("small", 854, "Small (854 px)"), ("medium", 1366, "Medium (1366 px)"),
         ("large", 1920, "Large (1920 px)"), ("phone", 1080, "Phone (1080 px)"))
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")


def is_image(path):
    return path.lower().endswith(IMAGE_EXT)


def fit(width, height, longest):
    """The size that fits `longest` on the longer side, never enlarging."""
    if max(width, height) <= longest:
        return width, height
    scale = longest / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def output_path(path, label, fmt=None, in_place=False):
    """photo.jpg → photo (Small).jpg, or photo.png when converting."""
    stem, ext = os.path.splitext(path)
    if fmt:
        ext = ".jpg" if fmt == "jpeg" else f".{fmt}"
    if in_place:
        return stem + ext
    candidate = f"{stem} ({label}){ext}"
    n = 2
    while os.path.exists(candidate):
        candidate = f"{stem} ({label} {n}){ext}"
        n += 1
    return candidate


def resize(path, longest, label, fmt=None, in_place=False):
    """Resize one picture; returns the path written."""
    from gi.repository import GdkPixbuf
    pix = GdkPixbuf.Pixbuf.new_from_file(path)
    pix = pix.apply_embedded_orientation() or pix
    w, h = fit(pix.get_width(), pix.get_height(), longest)
    if (w, h) != (pix.get_width(), pix.get_height()):
        pix = pix.scale_simple(w, h, GdkPixbuf.InterpType.HYPER)
    lower = path.lower()
    if fmt:
        kind = fmt
    elif lower.endswith((".jpg", ".jpeg")):
        kind = "jpeg"
    else:
        kind = "png"        # PNG keeps transparency; other formats become PNG
    keeps_ext = (kind == "jpeg" and lower.endswith((".jpg", ".jpeg"))) or \
        (kind == "png" and lower.endswith(".png"))
    target = output_path(path, label, None if keeps_ext else kind, in_place)
    options = (["quality"], ["90"]) if kind == "jpeg" else ([], [])
    if kind == "jpeg" and pix.get_has_alpha():
        pix = pix.composite_color_simple(w, h, GdkPixbuf.InterpType.BILINEAR, 255, 1,
                                         0xffffff, 0xffffff)
    pix.savev(target, kind, *options)
    if in_place and target != path:
        os.remove(path)
    return target


def holders(paths, proc="/proc"):
    """[(pid, name, [what it has open])] for processes holding any of `paths`
    open (as a file, a working folder, or anything under a folder)."""
    wanted = [os.path.realpath(p) for p in paths]

    def matches(target):
        return any(target == w or target.startswith(w.rstrip("/") + "/") for w in wanted)

    found = []
    try:
        pids = [int(n) for n in os.listdir(proc) if n.isdigit()]
    except OSError:
        return found
    me = os.getpid()
    for pid in pids:
        if pid == me:
            continue
        base = os.path.join(proc, str(pid))
        hits = set()
        try:
            cwd = os.readlink(os.path.join(base, "cwd"))
            if matches(cwd):
                hits.add(cwd)
        except OSError:
            pass
        try:
            for fd in os.listdir(os.path.join(base, "fd")):
                try:
                    target = os.readlink(os.path.join(base, "fd", fd))
                except OSError:
                    continue
                if target.startswith("/") and matches(target):
                    hits.add(target)
        except OSError:
            continue
        if hits:
            try:
                with open(os.path.join(base, "comm")) as f:
                    name = f.read().strip()
            except OSError:
                name = str(pid)
            found.append((pid, name, sorted(hits)))
    return sorted(found, key=lambda h: h[1].lower())
