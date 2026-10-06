"""Color picker (Super+Shift+C): click anywhere on the screen and the color's
hex code is copied, with a notification showing it."""

import subprocess
import threading

from gi.repository import GLib

from aurora.i18n import _


def ppm_pixel(data):
    """(r, g, b) of the first pixel of a binary PPM (P6), as grim writes it."""
    if not data.startswith(b"P6"):
        raise ValueError("not a P6 image")
    fields, pos = [], 2
    while len(fields) < 3:
        while data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":  # comment line
            pos = data.index(b"\n", pos) + 1
            continue
        end = pos
        while not data[end:end + 1].isspace():
            end += 1
        fields.append(int(data[pos:end]))
        pos = end
    maxval = fields[2]
    pos += 1  # the single whitespace byte after maxval
    if maxval < 256:
        r, g, b = data[pos], data[pos + 1], data[pos + 2]
    else:  # two bytes per sample
        r, g, b = (int.from_bytes(data[pos + i:pos + i + 2], "big") for i in (0, 2, 4))
    scale = 255 / maxval
    return round(r * scale), round(g * scale), round(b * scale)


def hex_color(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def pick(shell):
    if not shell.begin_selection():
        return

    def work():
        try:
            point = subprocess.run(["slurp", "-p", "-b", "#00000000"], capture_output=True,
                                   text=True, timeout=120)
            if point.returncode != 0 or not point.stdout.strip():
                return  # cancelled with Esc
            shot = subprocess.run(["grim", "-g", point.stdout.strip(), "-t", "ppm", "-"],
                                  capture_output=True, timeout=20, check=True)
            color = hex_color(ppm_pixel(shot.stdout))
            subprocess.run(["wl-copy", color], timeout=10, check=True)
            r, g, b = ppm_pixel(shot.stdout)
            GLib.idle_add(lambda: (done(color, f"rgb({r}, {g}, {b})"), False)[1])
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            GLib.idle_add(lambda: (failed(str(e)), False)[1])
        finally:
            GLib.idle_add(lambda: (shell.end_selection(), False)[1])

    def done(color, rgb):
        shell.notifications.notify(
            _("Color Picker"), 0, "color-select-symbolic",
            _("{color} copied").format(color=color),
            GLib.markup_escape_text(rgb), [], {"transient": True}, -1)

    def failed(error):
        shell.notifications.notify(
            _("Color Picker"), 0, "dialog-warning-symbolic", _("Couldn't read the color"),
            GLib.markup_escape_text(error), [], {"transient": True}, -1)

    threading.Thread(target=work, daemon=True).start()
