#!/usr/bin/env python3
"""Generate the Aurora labwc themes (window decorations).

Usage: generate.py OUTPUT_THEMES_DIR

Writes two themes that share colors and differ only in their buttons:
  Aurora           round colored buttons with their symbol always visible
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
# Symbols stay visible, softer until hovered, so each button says what it does.
GLYPH_REST = 0.7
INACTIVE_GLYPH = "#a39cb5"

# Dark theme color → light theme color (applied to themerc).
LIGHT = {
    "#1f1a2b": "#f4f1f8", "#17131f": "#ebe7f1", "#f2eefa": "#2a2338",
    "#8d869c": "#8a8398", "#3a3150": "#d5cfe0", "#26212f": "#e0dbe8",
    "#6f6880": "#9a93a8", "#332a45": "#e2dcec", "#ffffff": "#1a1526",
}

GLYPHS = {
    "close": '<path d="M10.3 10.3 15.7 15.7M15.7 10.3 10.3 15.7" stroke="{c}" stroke-width="1.7" '
             'stroke-linecap="round" opacity="{o}"/>',
    "iconify": '<path d="M9.8 13h6.4" stroke="{c}" stroke-width="1.7" stroke-linecap="round" opacity="{o}"/>',
    # Expand: two arrows pointing out; restore: pointing in.
    "max": '<path d="M13.6 9.6h2.8v2.8M12.4 16.4H9.6v-2.8M16.2 9.8l-2.6 2.6M9.8 16.2l2.6-2.6" '
           'stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
           'fill="none" opacity="{o}"/>',
    "max_toggled": '<path d="M14.2 9.6v2.2h2.2M11.8 16.4v-2.2H9.6M14.2 11.8l2.2-2.2M11.8 14.2l-2.2 2.2" '
                   'stroke="{c}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
                   'fill="none" opacity="{o}"/>',
}


def svg(fill, glyph=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 26 26">'
            f'<circle cx="13" cy="13" r="7" fill="{fill}"/>{glyph}</svg>\n')


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
                rest = GLYPHS[v].format(c=GLYPH, o=GLYPH_REST)
                hover = GLYPHS[v].format(c=GLYPH, o=1)
                write(os.path.join(d, f"{v}-active.svg"), svg(color, rest))
                write(os.path.join(d, f"{v}_hover-active.svg"), svg(color, hover))
                write(os.path.join(d, f"{v}-inactive.svg"),
                      svg(INACTIVE, GLYPHS[v].format(c=INACTIVE_GLYPH, o=0.8)))
                write(os.path.join(d, f"{v}_hover-inactive.svg"), svg(color, hover))


if __name__ == "__main__":
    main()
