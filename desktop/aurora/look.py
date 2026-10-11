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


def _write_gtk_css(version, imports, rules=""):
    d = os.path.expanduser(f"~/.config/gtk-{version}.0")
    path = os.path.join(d, "gtk.css")
    user = ""
    if os.path.exists(path):
        with open(path) as f:
            text = f.read()
        # Keep whatever the user wrote after our managed header.
        user = text.split(GTK_MARK, 1)[1] if GTK_MARK in text else text
    os.makedirs(d, exist_ok=True)
    head = "".join(f'@import url("file://{i}");\n' for i in imports) + rules
    with open(path, "w") as f:
        f.write(head + GTK_MARK + (user if user.startswith("\n") else "\n" + user))


ACCENT_HEX = {
    "blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800",
    "orange": "#ed5b00", "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac",
    "slate": "#6f8396",
}


def accent_hex():
    """The accent color as a hex: the one chosen in Settings, or the one taken
    from the background picture when Appearance asks for that."""
    s, iface = settings.get(), settings.interface()
    if s is not None and s.get_boolean("accent-from-wallpaper"):
        from aurora import accent
        found = accent.current()
        if found:
            return found
    name = iface.get_string("accent-color") if iface is not None else "purple"
    return ACCENT_HEX.get(name, ACCENT_HEX["purple"])


def is_dark():
    iface = settings.interface()
    return iface is None or iface.get_string("color-scheme") == "prefer-dark"


# Settings → Appearance → Icon style. Each style is a whole icon theme of its
# own (branding/icons/generate.py); the plain "Aurora" theme is the default
# one, and the rest inherit it, so only their app icons differ.
ICON_STYLES = {"galaxy": "Aurora", "ribbon": "Aurora-Ribbon", "glass": "Aurora-Glass",
               "clay": "Aurora-Clay", "bolt": "Aurora-Bolt"}


def apply_icon_style():
    """Put the chosen style in place, whatever was set before. Choosing a style
    is choosing a theme: it must take even on a system left on Adwaita."""
    iface = settings.interface()
    if iface is None:
        return
    wanted = icon_theme()
    if iface.get_string("icon-theme") != wanted:
        iface.set_string("icon-theme", wanted)


def icon_theme():
    """The icon theme to use: the chosen style, in the right light or dark twin."""
    s = settings.get()
    style = s.get_string("icon-style") if s is not None else "galaxy"
    base = ICON_STYLES.get(style, "Aurora")
    return base + ("-Dark" if is_dark() else "")


def sync_gtk_theme():
    """Make GTK 3 and plain GTK 4 apps follow the style and accent libadwaita apps use."""
    iface = settings.interface()
    if iface is None:
        return
    a11y = settings.get("org.gnome.desktop.a11y.interface")
    high_contrast = a11y is not None and a11y.get_boolean("high-contrast")
    theme = "adw-gtk3-dark" if is_dark() else "adw-gtk3"
    if high_contrast:
        theme = "HighContrast"
    if os.path.isdir(os.path.join("/usr/share/themes", theme)) and \
            iface.get_string("gtk-theme") != theme:
        iface.set_string("gtk-theme", theme)
    # Aurora and Papirus have light and dark variants; keep them in step with
    # the style, and keep Aurora's on the icon style chosen in Settings.
    icons = iface.get_string("icon-theme")
    if icons.startswith("Aurora"):
        wanted = icon_theme()
        if icons != wanted:
            iface.set_string("icon-theme", wanted)
    elif icons.startswith("Papirus"):
        wanted = "Papirus-Dark" if is_dark() else "Papirus"
        if icons != wanted:
            iface.set_string("icon-theme", wanted)
    accent = "#000000" if high_contrast else accent_hex()
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
        if version == "4" and s.get_boolean("window-animations"):
            imports.append(data_path("gtk", "gtk4-animations.css"))
        # Corner radius from Settings, for the windows apps draw themselves
        # (libadwaita's variable; GTK 3's decoration and title bar). The rule
        # comes after the imports on purpose: gtk4-base.css rounds every window
        # by itself, and the setting has to win over it.
        radius = s.get_int("window-corner-radius")
        rules = (f":root {{ --window-radius: {radius}px; }}\n"
                 f"window.csd, window.csd > .titlebar {{ border-radius: {radius}px; }}\n"
                 if version == "4" else
                 f"decoration, window.csd, window.csd > .titlebar {{ "
                 f"border-top-left-radius: {radius}px; border-top-right-radius: {radius}px; }}\n")
        _write_gtk_css(version, [i for i in imports if os.path.exists(i) or "gtk-accent" in i],
                       rules)

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
    if os.environ.get("AURORA_COMPOSITOR") == "wayfire":
        from aurora.wayfireconf import generate
        generate()


if __name__ == "__main__":
    from gi.repository import Gio
    apply()
    Gio.Settings.sync()     # before exiting, or the writes are lost
