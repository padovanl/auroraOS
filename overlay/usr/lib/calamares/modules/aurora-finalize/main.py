#!/usr/bin/env python3
"""Aurora OS post-install configuration for Calamares.

- Login: greetd starts the Aurora greeter; if the user ticked "Log in
  automatically", greetd's initial_session logs them straight in at boot
  (logging out still shows the greeter, like Ubuntu).
- Removes live-session-only launchers from the installed system.
"""

import os

import libcalamares

GREETER = """[terminal]
vt = 7

[default_session]
command = "/usr/libexec/aurora-greeter-launch"
user = "_greetd"
"""

AUTOLOGIN = """
[initial_session]
command = "/usr/bin/aurora-session"
user = "{user}"
"""

LIVE_ONLY = [
    "usr/share/applications/aurora-installer.desktop",
    "etc/sudoers.d/aurora-live",
    "etc/polkit-1/rules.d/49-aurora-live.rules",
]


def pretty_name():
    return "Configuring Aurora OS"


def run():
    root = libcalamares.globalstorage.value("rootMountPoint")
    if not root:
        return ("No root mount point", "Calamares did not provide a target root.")

    user = libcalamares.globalstorage.value("autoLoginUser")
    config = GREETER + (AUTOLOGIN.format(user=user) if user else "")
    path = os.path.join(root, "etc/greetd/config.toml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(config)
    libcalamares.utils.debug(f"aurora-finalize: greetd autologin={'yes' if user else 'no'}")

    for rel in LIVE_ONLY:
        p = os.path.join(root, rel)
        if os.path.lexists(p):
            os.remove(p)
    return None
