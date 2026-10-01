"""Aurora's included wallpapers: three series of the same landscape at dawn,
day, dusk and night. The dynamic background shows one series following the
sun; each picture can also be chosen on its own."""

import os

from aurora.i18n import N_

BACKGROUNDS = "/usr/share/backgrounds/aurora"
PHASES = ("dawn", "day", "dusk", "night")
SERIES = (("starfall", N_("Starfall")), ("veil", N_("Veil")), ("horizon", N_("Horizon")))
DEFAULT_SERIES = "starfall"


def path(series, phase):
    return os.path.join(BACKGROUNDS, f"aurora-{series}-{phase}.png")


def chosen_series(s):
    """The series the dynamic background uses (Settings → Appearance)."""
    name = s.get_string("wallpaper-dynamic-series") if s is not None else DEFAULT_SERIES
    return name if name in dict(SERIES) else DEFAULT_SERIES


def default_picture():
    return path(DEFAULT_SERIES, "dawn")
