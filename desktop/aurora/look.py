"""Apply window-decoration settings to labwc and GTK apps.

The compositor reads ~/.config/labwc/rc.xml; GTK 3/4 apps draw their own
title bars, so they are styled through ~/.config/gtk-{3,4}.0/gtk.css, which
imports Aurora's stylesheets. Everything here is idempotent: call apply()
after any change to the org.aurora.desktop window-* keys.
"""

import os

from aurora import data_path, labwcconf, settings

GTK_MARK = "/* Managed by Aurora Settings: edit below the imports, not above. */"


def apply_labwc(s):
    cfg = labwcconf.Config()
    traffic = s.get_string("window-button-style") == "traffic"
    cfg.set("theme", "name", value="Aurora" if traffic else "Aurora-Symbolic")
    cfg.set("theme", "cornerRadius", value=s.get_int("window-corner-radius"))
    left = s.get_string("window-buttons") == "left"
    cfg.set("theme", "titlebar", "layout",
            value="close,iconify,max:" if left else "icon:iconify,max,close")
    cfg.set("core", "gap", value=s.get_int("window-gaps"))
    cfg.save()


def _write_gtk_css(version, imports):
    d = os.path.expanduser(f"~/.config/gtk-{version}.0")
    path = os.path.join(d, "gtk.css")
    user = ""
    if os.path.exists(path):
        with open(path) as f:
            text = f.read()
        # Keep whatever the user wrote after our managed header.
        user = text.split(GTK_MARK, 1)[1] if GTK_MARK in text else text
    os.makedirs(d, exist_ok=True)
    head = "".join(f'@import url("file://{i}");\n' for i in imports)
    with open(path, "w") as f:
        f.write(head + GTK_MARK + (user if user.startswith("\n") else "\n" + user))


def apply_gtk(s):
    traffic = s.get_string("window-button-style") == "traffic"
    left = s.get_string("window-buttons") == "left"
    for version in ("3", "4"):
        imports = [data_path("gtk", f"gtk{version}-base.css")]
        if traffic:
            imports.append(data_path("gtk", f"gtk{version}-traffic.css"))
        _write_gtk_css(version, [i for i in imports if os.path.exists(i)])

    wm = settings.get("org.gnome.desktop.wm.preferences")
    if wm is not None:
        wm.set_string("button-layout", "close,minimize,maximize:" if left
                      else "appmenu:minimize,maximize,close")


def apply():
    s = settings.get()
    if s is None:
        return
    apply_labwc(s)
    apply_gtk(s)


if __name__ == "__main__":
    apply()
