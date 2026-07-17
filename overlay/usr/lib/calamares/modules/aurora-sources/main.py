#!/usr/bin/env python3
"""Write the installed system's apt sources (deb822), including backports.

Replaces Debian's sources-final helper, which writes a one-line
sources.list that would duplicate the image's debian.sources.
"""

import os

import libcalamares

SOURCES = """Types: deb
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates trixie-backports
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: http://security.debian.org/debian-security
Suites: trixie-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
"""


def pretty_name():
    return "Configuring software sources"


def run():
    root = libcalamares.globalstorage.value("rootMountPoint")
    apt = os.path.join(root, "etc/apt")
    legacy = os.path.join(apt, "sources.list")
    if os.path.exists(legacy):
        os.remove(legacy)
    os.makedirs(os.path.join(apt, "sources.list.d"), exist_ok=True)
    with open(os.path.join(apt, "sources.list.d/debian.sources"), "w") as f:
        f.write(SOURCES)
    return None
