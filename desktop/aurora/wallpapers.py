"""Bundled still images, downloaded video wallpapers and daylight series.

The dynamic background follows the sun; every still can also be selected.
"""

import os

from aurora.i18n import N_

BACKGROUNDS = "/usr/share/backgrounds/aurora"
PHASES = ("dawn", "day", "dusk", "night")
SERIES = (("starfall", N_("Starfall")), ("veil", N_("Veil")), ("horizon", N_("Horizon")))
DEFAULT_SERIES = "starfall"
SCENES = (("northern-lights", N_("Northern Lights")), ("wave", N_("Wave")),
          ("nebula", N_("Nebula")), ("milky-way", N_("Milky Way")),
          ("sunrise", N_("Sunrise")), ("ringed-planet", N_("Ringed Planet")))
STATIC = (
    ("violet-sculpture", N_("Violet Sculpture")),
    ("folded-ribbons", N_("Folded Ribbons")),
    ("floating-geometry", N_("Floating Geometry")),
    ("metallic-orbit", N_("Metallic Orbit")),
    ("indigo-silk", N_("Indigo Silk")),
    ("blue-world", N_("Blue World")),
    ("amber-planet", N_("Amber Planet")),
    ("red-horizon", N_("Red Horizon")),
    ("earth-at-dusk", N_("Earth at Dusk")),
    ("eclipse-world", N_("Eclipse World")),
    ("alpine-reflection", N_("Alpine Reflection")),
    ("alpine-valley", N_("Alpine Valley")),
    ("golden-forest", N_("Golden Forest")),
    ("turquoise-depths", N_("Turquoise Depths")),
    ("fern-canopy", N_("Fern Canopy")),
)
VIDEO_EXT = (".mp4", ".webm", ".m4v", ".mov")
ANIMATED = (
    ("fjord-lights", N_("Fjord Lights")),
    ("crystal-bloom", N_("Crystal Bloom")),
    ("atmosphere", N_("Atmosphere")),
    ("smooth-waves", N_("Smooth Waves")),
    ("crystal-flow", N_("Crystal Flow")),
    ("infinite-flight", N_("Infinite Flight")),
    ("nordic-aurora", N_("Nordic Aurora")),
    ("trappist-dawn", N_("Trappist Dawn")),
    ("triton-horizon", N_("Triton Horizon")),
    ("alpine-mist", N_("Alpine Mist")),
    ("amber-water", N_("Amber Water")),
    ("emerald-leaves", N_("Emerald Leaves")),
    ("meadow-sky", N_("Meadow Sky")),
    ("winter-river", N_("Winter River")),
    ("blue-hour", N_("Blue Hour")),
    ("mirror-lake", N_("Mirror Lake")),
    ("golden-birch", N_("Golden Birch")),
    ("summer-bloom", N_("Summer Bloom")),
    ("forest-stream", N_("Forest Stream")),
    ("itachi-sharingan", N_("Unyielding Itachi's Sharingan")),
    ("madara-village", N_("Madara in Japanese Village")),
    ("rain-window", N_("Rain Drops on Window")),
    ("elden-full-moon", N_("Full Moon (Elden Ring)")),
    ("mist-pines", N_("Mist Over the Pines")),
    ("azure-clouds", N_("Azure Clouds")),
    ("singularity-cosmic-vortex", N_("Singularity Cosmic Vortex")),
    ("cat-and-bee", N_("Cat and Bee")),
)


def animated_path(name):
    return os.path.join(BACKGROUNDS, "animated", name + ".mp4")


def is_video(path):
    return bool(path) and path.lower().endswith(VIDEO_EXT)


def poster_path(path):
    """Static companion for thumbnails, lock screen and video fallback."""
    return os.path.splitext(path)[0] + ".png" if is_video(path) else path


def scene_path(name):
    return os.path.join(BACKGROUNDS, f"aurora-{name}.png")


def path(series, phase):
    return os.path.join(BACKGROUNDS, f"aurora-{series}-{phase}.png")


def chosen_series(s):
    """The series the dynamic background uses (Settings → Appearance)."""
    name = s.get_string("wallpaper-dynamic-series") if s is not None else DEFAULT_SERIES
    return name if name in dict(SERIES) else DEFAULT_SERIES


def default_picture():
    return path(DEFAULT_SERIES, "dawn")
