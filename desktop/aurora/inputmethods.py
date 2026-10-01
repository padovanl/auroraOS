"""Input methods for Chinese, Korean and Japanese, through Fcitx 5.

The choice lives in ~/.config/aurora/input-methods (names, one per line:
pinyin, hangul, mozc). From it this writes Fcitx's profile, with the keyboard
layout first, so Ctrl+Space switches between typing letters and the input
method. aurora-session starts Fcitx (and tells apps to use it) only when one
is chosen: people who type only Latin scripts don't run it at all.
"""

import os

METHODS = (("pinyin", "zh", "Chinese (Pinyin)"), ("hangul", "ko", "Korean (Hangul)"),
           ("mozc", "ja", "Japanese (Mozc)"))


def config_home():
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def choice_path():
    return os.path.join(config_home(), "aurora", "input-methods")


def profile_path():
    return os.path.join(config_home(), "fcitx5", "profile")


def chosen():
    """The chosen methods, or None when nothing was ever chosen."""
    try:
        with open(choice_path()) as f:
            return [line.strip() for line in f if line.strip() in dict(
                (m, m) for m, _l, _n in METHODS)]
    except OSError:
        return None


def defaults_for(lang):
    """The method a language needs: zh_CN → ["pinyin"], en_US → []."""
    code = (lang or "").split("_")[0].split(".")[0]
    return [m for m, l, _n in METHODS if l == code]


def chosen_layouts():
    """The keyboard layouts from Settings → Language & Region (the compositor's
    environment file), else the session's."""
    path = os.path.join(config_home(), "labwc", "environment")
    try:
        with open(path) as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and key == "XKB_DEFAULT_LAYOUT" and value.strip().strip('"'):
                    return value.strip().strip('"')
    except OSError:
        pass
    return os.environ.get("XKB_DEFAULT_LAYOUT", "us")


def profile_text(layout, methods):
    """Fcitx's profile: every keyboard layout, then the input methods, so
    Ctrl+Space goes through them all and typing letters keeps your layout."""
    layouts = [x for x in (layout or "us").split(",") if x] or ["us"]
    items = [f"keyboard-{x}" for x in layouts] + list(methods)
    layout = layouts[0]
    lines = ["[Groups/0]", "Name=Default", f"Default Layout={layout}",
             f"DefaultIM={methods[0] if methods else items[0]}", ""]
    for i, name in enumerate(items):
        lines += [f"[Groups/0/Items/{i}]", f"Name={name}", "Layout=", ""]
    lines += ["[GroupOrder]", "0=Default", ""]
    return "\n".join(lines)


# Cloud Pinyin sends what you type to online services for suggestions: off.
DISABLED_ADDONS = ("cloudpinyin",)


def fcitx_config_path():
    return os.path.join(config_home(), "fcitx5", "config")


def ensure_private(path=None):
    """Turn the cloud suggestions off in Fcitx's config, keeping the rest.
    Fcitx keeps lists as a section of numbered keys:
    [Behavior/DisabledAddons] 0=cloudpinyin."""
    path = path or fcitx_config_path()
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    section = "[Behavior/DisabledAddons]"
    have, out, inside = [], [], False
    for line in lines:
        if line.startswith("["):
            inside = line.strip() == section
            if inside:
                continue
        if inside:
            if "=" in line:
                have.append(line.split("=", 1)[1].strip())
            continue
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    names = list(dict.fromkeys([a for a in have if a] + list(DISABLED_ADDONS)))
    out += ["", section] + [f"{i}={name}" for i, name in enumerate(names)]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(out).lstrip("\n") + "\n")


def save(methods, layout=None):
    os.makedirs(os.path.dirname(choice_path()), exist_ok=True)
    with open(choice_path(), "w") as f:
        f.write("".join(m + "\n" for m in methods))
    os.makedirs(os.path.dirname(profile_path()), exist_ok=True)
    layout = layout or chosen_layouts()
    with open(profile_path(), "w") as f:
        f.write(profile_text(layout, methods))
    ensure_private()


def setup(lang=None, layout=None):
    """At login: the first time, pick the method the language needs. True when
    Fcitx should run."""
    methods = chosen()
    if methods is None:
        methods = defaults_for(lang or os.environ.get("LANG", ""))
        if methods:
            save(methods, layout)
    return bool(methods)
