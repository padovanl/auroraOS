"""Background notifications the system sends by itself, like Ubuntu does:
updates available, low battery, a nearly full disk, and removable drives
(automounted).
"""

import os
import shutil
import subprocess

from gi.repository import Gio, GLib

from aurora import apps, settings
from aurora.i18n import _, ngettext

UPDATE_CHECK_FIRST_S = 5 * 60        # first check a few minutes after login
UPDATE_CHECK_EVERY_S = 6 * 60 * 60   # then every six hours
BATTERY_WARN = (10, 5)               # percent
DISK_CHECK_EVERY_S = 10 * 60


def disk_low(total, free):
    """Below the room Aurora keeps free for the system (the same rule as AI
    downloads): 5% of the disk, at least 2 GB and at most 10 GB."""
    from aurora.ai.download import reserve_for
    return free < reserve_for(total)


MEMORY_FS = {"overlay", "tmpfs", "ramfs", "squashfs", "iso9660"}


def fs_type(path, mounts=None):
    """File system type of the mount holding path (the longest matching mount
    point in /proc/self/mounts)."""
    if mounts is None:
        try:
            with open("/proc/self/mounts") as f:
                mounts = f.read()
        except OSError:
            return ""
    best, kind = "", ""
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        point = fields[1].replace("\\040", " ")
        inside = path == point or path.startswith(point.rstrip("/") + "/")
        if inside and len(point) >= len(best):
            best, kind = point, fields[2]
    return kind


def count_updates():
    """Packages with a newer version in the (already refreshed) apt lists."""
    try:
        out = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True,
                             timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0
    return len([ln for ln in out.splitlines() if "/" in ln and "upgradable" in ln])


class SystemNotifications:
    def __init__(self, shell):
        self.shell = shell
        self._notified_updates = 0
        self._battery_warned = set()
        self._action_ids = {}

        GLib.timeout_add_seconds(UPDATE_CHECK_FIRST_S, self._check_updates)
        self._disk_warned = set()
        GLib.timeout_add_seconds(60, self._check_disks)
        shell.battery.connect("changed", lambda *a: self._check_battery())
        self.volumes = Gio.VolumeMonitor.get()
        self.volumes.connect("volume-added", self._on_volume_added)
        self.volumes.connect("mount-added", self._on_mount_added)

    def notify(self, summary, body, icon, actions=(), on_action=None, urgency=1):
        flat = [x for pair in actions for x in pair]
        nid = self.shell.notifications.notify(_("Aurora"), 0, icon, summary, body, flat,
                                              {"urgency": urgency}, -1)
        if on_action:
            self._action_ids[nid] = on_action
        return nid

    def invoke(self, nid, key):
        """Called by the notification server when one of our actions is clicked."""
        cb = self._action_ids.get(nid)
        if cb:
            cb(key)

    # --- updates ---

    def _check_updates(self):
        n = count_updates()
        if n and n != self._notified_updates:
            self._notified_updates = n
            self.notify(_("Software updates available"),
                         ngettext("{n} update is ready to install.",
                                  "{n} updates are ready to install.", n).format(n=n),
                         "software-update-available",
                         [("update", _("Update")), ("later", _("Later"))],
                         lambda key: key == "update" and apps.spawn(
                             ["gnome-software", "--mode=updates"]))
        GLib.timeout_add_seconds(UPDATE_CHECK_EVERY_S, self._check_updates)
        return GLib.SOURCE_REMOVE

    # --- disk space ---

    def _check_disks(self):
        seen = set()
        for path in ("/", os.path.expanduser("~")):
            try:
                st = os.stat(path)
                disk = shutil.disk_usage(path)
            except OSError:
                continue
            if st.st_dev in seen:  # home on the same file system as / (btrfs)
                continue
            if fs_type(path) in MEMORY_FS:  # the live system: its "disk" is RAM
                continue
            seen.add(st.st_dev)
            low = disk_low(disk.total, disk.free)
            if low and st.st_dev not in self._disk_warned:
                self._disk_warned.add(st.st_dev)
                self.notify(_("Disk almost full"),
                            _("Only {free} is free. Programs and updates can fail when the "
                              "disk is full: remove files you don't need, or AI models in "
                              "Settings → AI.").format(free=GLib.format_size(disk.free)),
                            "drive-harddisk-symbolic",
                            [("usage", _("See What Uses Space")), ("later", _("Later"))],
                            lambda key: key == "usage" and apps.spawn(["baobab"]),
                            urgency=2)
            elif not low:
                self._disk_warned.discard(st.st_dev)  # warn again next time it fills up
        GLib.timeout_add_seconds(DISK_CHECK_EVERY_S, self._check_disks)
        return GLib.SOURCE_REMOVE

    # --- battery ---

    def _check_battery(self):
        bat = self.shell.battery
        if not bat.present or bat.charging:
            self._battery_warned.clear()
            return
        for level in BATTERY_WARN:
            if bat.percentage <= level and level not in self._battery_warned:
                self._battery_warned.add(level)
                self.notify(_("Battery low") if level > 5 else _("Battery critically low"),
                             _("{p}% remaining. Plug in your computer.").format(p=int(bat.percentage)),
                             "battery-caution", urgency=2 if level <= 5 else 1)
                break

    # --- removable drives ---

    def _on_volume_added(self, _monitor, volume):
        if not volume.should_automount() or volume.get_mount() is not None:
            return
        if not volume.can_mount():
            return
        volume.mount(Gio.MountMountFlags.NONE, None, None, self._mounted, None)

    def _mounted(self, volume, res, _data=None):
        try:
            volume.mount_finish(res)
        except GLib.Error as err:
            print(f"aurora: automount of {volume.get_name()} failed: {err.message}")

    def _on_mount_added(self, _monitor, mount):
        if mount.is_shadowed() or not mount.can_unmount():
            return
        root = mount.get_root()
        s = settings.get()
        action = s.get_string("removable-media-action") if s is not None else "notify"
        if action == "nothing":
            return
        if action == "open":
            apps.spawn(["aurora-files", root.get_uri()])
            return
        self.notify(_("{name} connected").format(name=mount.get_name()),
                     _("The drive is ready to use."), "drive-removable-media",
                     [("open", _("Open")), ("eject", _("Eject"))],
                     lambda key: apps.spawn(["aurora-files", root.get_uri()]) if key == "open"
                     else mount.unmount_with_operation(Gio.MountUnmountFlags.NONE, None, None,
                                                       None, None))
