"""Aurora desktop environment."""

import os

VERSION = "0.1"

PREFIX = os.environ.get("AURORA_PREFIX", "/usr")
DATADIR = os.environ.get("AURORA_DATADIR", os.path.join(PREFIX, "share", "aurora"))
LOCALEDIR = os.environ.get("AURORA_LOCALEDIR", os.path.join(PREFIX, "share", "locale"))


def data_path(*parts):
    return os.path.join(DATADIR, *parts)


def config_path(*parts):
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "aurora", *parts)
