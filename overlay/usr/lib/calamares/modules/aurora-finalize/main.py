#!/usr/bin/env python3
"""Aurora OS post-install configuration for Calamares.

- Login: greetd starts the Aurora greeter; if the user ticked "Log in
  automatically", greetd's initial_session logs them straight in at boot
  (logging out still shows the greeter, like Ubuntu).
- Removes live-session-only launchers from the installed system.
- On btrfs: sets up Timeshift in btrfs mode, the "Fresh install" snapshot at
  first boot, snapshots before package changes and the "Aurora OS snapshots"
  boot menu (grub-btrfs). ext4 and xfs installs skip all of this.
"""

import json
import os
import subprocess

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


TIMESHIFT = {
    "backup_device_uuid": "", "parent_device_uuid": "", "do_first_run": "false",
    "btrfs_mode": "true", "include_btrfs_home_for_backup": "false",
    "include_btrfs_home_for_restore": "false", "stop_cron_emails": "true",
    "schedule_monthly": "false", "schedule_weekly": "true", "schedule_daily": "true",
    "schedule_hourly": "false", "schedule_boot": "false",
    "count_monthly": "2", "count_weekly": "3", "count_daily": "5",
    "count_hourly": "6", "count_boot": "5",
    "date_format": "%Y-%m-%d %H:%M:%S", "exclude": [], "exclude-apps": [],
}


def _out(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def setup_snapshots(root):
    """Timeshift + grub-btrfs when the new system's root is btrfs."""
    if _out(["findmnt", "-no", "FSTYPE", root]) != "btrfs":
        libcalamares.utils.debug("aurora-finalize: root is not btrfs, no snapshots")
        return
    source = _out(["findmnt", "-no", "SOURCE", root]).split("[")[0]
    config = dict(TIMESHIFT)
    config["backup_device_uuid"] = _out(["blkid", "-s", "UUID", "-o", "value", source])
    if source.startswith("/dev/mapper/"):
        # Encrypted: Timeshift also wants the LUKS container.
        parent = _out(["lsblk", "-no", "PKNAME", source]).splitlines()
        if parent:
            config["parent_device_uuid"] = _out(
                ["blkid", "-s", "UUID", "-o", "value", "/dev/" + parent[0]])
    path = os.path.join(root, "etc/timeshift/timeshift.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    menu = os.path.join(root, "etc/grub.d/41_snapshots-btrfs")
    if os.path.exists(menu):
        os.chmod(menu, 0o755)
    for unit in ("grub-btrfsd.service", "aurora-first-snapshot.service"):
        libcalamares.utils.target_env_call(["systemctl", "enable", unit])
    libcalamares.utils.debug(f"aurora-finalize: snapshots on {source} "
                             f"({config['backup_device_uuid']})")


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

    setup_snapshots(root)

    for rel in LIVE_ONLY:
        p = os.path.join(root, rel)
        if os.path.lexists(p):
            os.remove(p)
    return None
