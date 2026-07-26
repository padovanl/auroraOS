#!/usr/bin/env python3
"""Generate the Aurora labwc themes (window decorations).

Usage: generate.py OUTPUT_THEMES_DIR

Writes two themes that share colors and differ only in their buttons:
  Aurora           round colored buttons, glyph shown on hover
  Aurora-Symbolic  monochrome icons (labwc built-ins)
plus a -Light variant of each, used when the desktop is in light style.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Our own palette for the round buttons (close, minimize, maximize).
TRAFFIC = {"close": "#ff6b6b", "iconify": "#ffc24b", "max": "#3ccb5a"}
INACTIVE = "#4a4460"
GLYPH = "#3d2230"

# Dark theme color → light theme color (applied to themerc).
LIGHT = {
    "#1f1a2b": "#f4f1f8", "#17131f": "#ebe7f1", "#f2eefa": "#2a2338",
    "#8d869c": "#8a8398", "#3a3150": "#d5cfe0", "#26212f": "#e0dbe8",
    "#6f6880": "#9a93a8", "#332a45": "#e2dcec", "#ffffff": "#1a1526",
}

GLYPHS = {
    "close": '<path d="M10.2 10.2 15.8 15.8M15.8 10.2 10.2 15.8" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "iconify": '<path d="M9.8 13h6.4" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "max": '<path d="M10 13h6M13 10v6" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>',
    "max_toggled": '<path d="M10 13h6" stroke="{c}" stroke-width="1.6" stroke-linecap="round"/>'
                   '<path d="M13 10v6" stroke="{c}" stroke-width="1.6" stroke-linecap="round" opacity=".4"/>',
}


def svg(fill, glyph=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 26 26">'
            f'<circle cx="13" cy="13" r="6.5" fill="{fill}"/>{glyph}</svg>\n')


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


def main():
    out = sys.argv[1]
    with open(os.path.join(HERE, "themerc")) as f:
        base = f.read()

    for name, traffic, light in (("Aurora", True, False), ("Aurora-Symbolic", False, False),
                                 ("Aurora-Light", True, True),
                                 ("Aurora-Symbolic-Light", False, True)):
        d = os.path.join(out, name, "openbox-3")
        os.makedirs(d, exist_ok=True)
        extra = ("\n# Round buttons: no hover plate, tighter spacing.\n"
                 "window.button.width: 22\nwindow.button.spacing: 2\n"
                 "window.button.hover.bg.color: #00000000\n") if traffic else ""
        text = base
        if light:
            for dark_c, light_c in LIGHT.items():
                text = text.replace(dark_c, light_c)
        write(os.path.join(d, "themerc"), text + extra)
        if not traffic:
            continue
        for button, color in TRAFFIC.items():
            variants = [button] + (["max_toggled"] if button == "max" else [])
            for v in variants:
                glyph = GLYPHS[v].format(c=GLYPH)
                write(os.path.join(d, f"{v}-active.svg"), svg(color))
                write(os.path.join(d, f"{v}_hover-active.svg"), svg(color, glyph))
                write(os.path.join(d, f"{v}-inactive.svg"), svg(INACTIVE))
                write(os.path.join(d, f"{v}_hover-inactive.svg"), svg(color, glyph))


if __name__ == "__main__":
    main()
