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
    name = "Aurora" if traffic else "Aurora-Symbolic"
    if not is_dark():
        name += "-Light"
    cfg.set("theme", "name", value=name)
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


ACCENT_HEX = {
    "blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800",
    "orange": "#ed5b00", "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac",
    "slate": "#6f8396",
}


def is_dark():
    iface = settings.interface()
    return iface is None or iface.get_string("color-scheme") == "prefer-dark"


def sync_gtk_theme():
    """Make GTK 3 and plain GTK 4 apps follow the style and accent libadwaita apps use."""
    iface = settings.interface()
    if iface is None:
        return
    theme = "adw-gtk3-dark" if is_dark() else "adw-gtk3"
    if os.path.isdir(os.path.join("/usr/share/themes", theme)) and \
            iface.get_string("gtk-theme") != theme:
        iface.set_string("gtk-theme", theme)
    # Papirus has light and dark variants; keep them in step with the style.
    icons = iface.get_string("icon-theme")
    if icons in ("Papirus", "Papirus-Dark", "Papirus-Light"):
        wanted = "Papirus-Dark" if is_dark() else "Papirus"
        if icons != wanted:
            iface.set_string("icon-theme", wanted)
    accent = ACCENT_HEX.get(iface.get_string("accent-color"), ACCENT_HEX["purple"])
    path = os.path.expanduser("~/.config/aurora/gtk-accent.css")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f"@define-color accent_bg_color {accent};\n"
                f"@define-color accent_color {accent};\n"
                "@define-color accent_fg_color #ffffff;\n")


def apply_gtk(s):
    traffic = s.get_string("window-button-style") == "traffic"
    left = s.get_string("window-buttons") == "left"
    for version in ("3", "4"):
        imports = [os.path.expanduser("~/.config/aurora/gtk-accent.css"),
                   data_path("gtk", f"gtk{version}-base.css")]
        if traffic:
            imports.append(data_path("gtk", f"gtk{version}-traffic.css"))
        _write_gtk_css(version, [i for i in imports if os.path.exists(i) or "gtk-accent" in i])

    wm = settings.get("org.gnome.desktop.wm.preferences")
    if wm is not None:
        wm.set_string("button-layout", "close,minimize,maximize:" if left
                      else "appmenu:minimize,maximize,close")


def apply():
    s = settings.get()
    if s is None:
        return
    sync_gtk_theme()
    apply_labwc(s)
    apply_gtk(s)


if __name__ == "__main__":
    apply()
