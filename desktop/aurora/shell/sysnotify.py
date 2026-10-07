"""Background notifications the system sends by itself, like Ubuntu does:
updates available, low battery, a nearly full disk, and removable drives
(automounted).
"""

import os
import re
import shutil
import subprocess
import threading

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


def reboot_needed(running, kernels, flag=False):
    """An update needs a restart: Debian's flag file, or a newer kernel installed
    than the one running (`kernels` are the versions in /boot)."""
    if flag:
        return True
    def key(version):
        return [int(x) if x.isdigit() else x for x in re.split(r"[.\-+~]", version)]
    try:
        newest = max(kernels, key=key) if kernels else running
        return key(newest) > key(running)
    except TypeError:
        return False


def installed_kernels(boot="/boot"):
    try:
        return [n[len("vmlinuz-"):] for n in os.listdir(boot) if n.startswith("vmlinuz-")]
    except OSError:
        return []


def in_active_hours(hour, start, end):
    """Active hours may cross midnight (22 to 6)."""
    if start == end:
        return True
    return start <= hour < end if start < end else hour >= start or hour < end


def next_quiet_time(now, start, end):
    """The first moment outside active hours from `now` (a datetime)."""
    import datetime
    t = now.replace(minute=0, second=0, microsecond=0)
    for _ in range(48):
        if not in_active_hours(t.hour, start, end) and t >= now - datetime.timedelta(hours=1):
            return max(t, now)
        t += datetime.timedelta(hours=1)
    return now


def battery_saver_action(percentage, charging, threshold, saver_on, we_turned_it_on):
    """"on", "off" or None: Battery Saver turns on below the threshold on
    battery, and off again when charging (only if it was Aurora that turned it on)."""
    if threshold <= 0:
        return None
    if not charging and percentage <= threshold and not saver_on:
        return "on"
    if charging and saver_on and we_turned_it_on:
        return "off"
    return None


BT_LOW = 15        # percent: warn about a Bluetooth device's battery
BT_RESET = 25      # warn again only after it has been charged above this


def bluetooth_warnings(devices, warned):
    """(devices to warn about now, the new warned set) from [{path, name,
    connected, battery}]."""
    now, still = [], set()
    for dev in devices:
        level = dev.get("battery")
        if level is None or not dev.get("connected"):
            if dev["path"] in warned:
                still.add(dev["path"])
            continue
        if level <= BT_LOW:
            still.add(dev["path"])
            if dev["path"] not in warned:
                now.append(dev)
        elif level < BT_RESET and dev["path"] in warned:
            still.add(dev["path"])
    return now, still


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
        self._restart_notified = False
        GLib.timeout_add_seconds(UPDATE_CHECK_FIRST_S + 60, self._check_restart)
        self._disk_warned = set()
        GLib.timeout_add_seconds(60, self._check_disks)
        shell.battery.connect("changed", lambda *a: self._check_battery())
        self._bt_warned = set()
        shell.bluetooth.connect("changed", lambda *a: self._check_bluetooth())
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

    def _check_restart(self):
        """An update needs a restart: say so once, with Restart Now, Tonight
        (outside active hours) and Later; restart at the planned time, with a
        five-minute warning that can postpone it."""
        import time
        s = settings.get()
        planned = s.get_int64("update-restart-at") if s else 0
        if planned and time.time() >= planned:
            s.set_int64("update-restart-at", 0)
            self._warn_restart()
        elif reboot_needed(os.uname().release, installed_kernels(),
                           os.path.exists("/run/reboot-required")):
            auto = s is not None and s.get_boolean("update-auto-restart")
            if auto and not planned:
                self._plan_restart_tonight(quiet=True)
            elif not self._restart_notified:
                self._restart_notified = True
                self.notify(_("Restart to finish updating"),
                            _("An update needs a restart. Your apps will close; save "
                              "your work first."),
                            "system-reboot",
                            [("now", _("Restart Now")), ("tonight", _("Tonight")),
                             ("later", _("Later"))],
                            self._restart_choice)
        GLib.timeout_add_seconds(15 * 60, self._check_restart)
        return False

    def _restart_choice(self, key):
        if key == "now":
            self.shell.power.reboot()
        elif key == "tonight":
            self._plan_restart_tonight()

    def _plan_restart_tonight(self, quiet=False):
        import datetime
        s = settings.get()
        if s is None:
            return
        start = s.get_int("update-active-hours-start")
        end = s.get_int("update-active-hours-end")
        when = next_quiet_time(datetime.datetime.now(), start, end)
        s.set_int64("update-restart-at", int(when.timestamp()))
        if not quiet:
            self.notify(_("Restart planned"),
                        _("Aurora will restart at {time}, outside your active hours.").format(
                            time=when.strftime("%H:%M")), "system-reboot")

    def _warn_restart(self):
        def choice(key):
            if key == "postpone":
                import time
                s = settings.get()
                if s is not None:
                    s.set_int64("update-restart-at", int(time.time()) + 3600)
                GLib.source_remove(self._restart_source)
            elif key == "now":
                GLib.source_remove(self._restart_source)
                self.shell.power.reboot()
        self.notify(_("Restarting in 5 minutes"),
                    _("To finish installing updates. Save your work."), "system-reboot",
                    [("now", _("Restart Now")), ("postpone", _("In an Hour"))], choice,
                    urgency=2)
        self._restart_source = GLib.timeout_add_seconds(
            300, lambda: (subprocess.Popen(["systemctl", "reboot"]), False)[1])

    def _check_updates(self):
        # apt takes a few seconds: in a thread, or the whole desktop froze
        # (input, animations) at every check.
        def work():
            n = count_updates()
            GLib.idle_add(lambda: (self._updates_counted(n), False)[1])
        threading.Thread(target=work, daemon=True).start()
        return GLib.SOURCE_REMOVE

    def _updates_counted(self, n):
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

    def _check_bluetooth(self):
        try:
            devices = self.shell.bluetooth.devices()
        except Exception:  # noqa: BLE001 - BlueZ going away mid-call
            return
        warn, self._bt_warned = bluetooth_warnings(devices, self._bt_warned)
        for dev in warn:
            self.notify(_("{name} is low on battery").format(name=dev["name"]),
                        _("{p}% left. Charge it soon.").format(p=dev["battery"]),
                        "battery-caution")

    def _battery_saver(self, bat):
        s = settings.get()
        profiles = self.shell.power_profiles
        if s is None or not profiles.available:
            return
        threshold = s.get_int("battery-saver-threshold")
        mine = getattr(self, "_saver_by_us", None)
        action = battery_saver_action(bat.percentage, bat.charging, threshold,
                                      profiles.current == "power-saver", mine is not None)
        if action == "on":
            self._saver_by_us = profiles.current
            profiles.set("power-saver")
            self.notify(_("Battery Saver is on"),
                        _("Below {n}%: the screen dims sooner and apps use less power. It "
                          "turns off when you plug in.").format(n=threshold),
                        "battery-caution", [("off", _("Turn Off"))],
                        lambda key: key == "off" and (profiles.set(mine or "balanced"),
                                                      setattr(self, "_saver_by_us", None)))
        elif action == "off":
            profiles.set(mine or "balanced")
            self._saver_by_us = None

    def _check_battery(self):
        bat = self.shell.battery
        if bat.present:
            self._battery_saver(bat)
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
        # Only drives that come and go (USB sticks, SD cards): an internal
        # partition (Windows' C:) or a network share opened from Files is
        # not "connected", and has nothing to eject.
        drive = mount.get_drive()
        if drive is None or not (drive.is_removable() or drive.is_media_removable()):
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
