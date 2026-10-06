"""Which disk option the installer starts with (aurora-installer, live session).

Calamares picks one fixed option for every computer. "Erase disk" picked on
a disk holding Windows lets Next wipe it; "Install alongside" picked on an
empty disk leaves the page half in that mode. So the choice follows the
disks, looked at as root before Calamares starts:

- every disk empty (the live USB itself aside): Erase disk;
- another system found (os-prober): Install alongside;
- otherwise (partitions, no system: data disks): nothing, the person picks.

    python3 -m aurora.installchoice   → prints erase, alongside or none
"""

import json
import subprocess


def choice(disks, systems_found):
    """disks: [(name, has_partitions)] of the disks one can install on."""
    if not any(has for _name, has in disks):
        return "erase"
    if systems_found:
        return "alongside"
    return "none"


def live_disk():
    """The disk the live system started from (excluded from the look)."""
    try:
        source = subprocess.run(["findmnt", "-no", "SOURCE", "/run/live/medium"],
                                capture_output=True, text=True, timeout=10).stdout.strip()
        parent = subprocess.run(["lsblk", "-no", "PKNAME", source], capture_output=True,
                                text=True, timeout=10).stdout.split()
        return parent[0] if parent else source.rsplit("/", 1)[-1]
    except (OSError, subprocess.TimeoutExpired):
        return ""


def target_disks(lsblk_json, skip=""):
    """[(name, has_partitions)] from `lsblk -J -o NAME,TYPE,FSTYPE`."""
    disks = []
    for dev in json.loads(lsblk_json).get("blockdevices", []):
        if dev.get("type") != "disk" or dev.get("name") == skip:
            continue
        if dev.get("name", "").startswith(("zram", "loop", "sr", "fd")):
            continue
        used = bool(dev.get("children")) or bool(dev.get("fstype"))
        disks.append((dev["name"], used))
    return disks


def systems(prober_output, skip=""):
    """os-prober's findings, without the live USB's own partitions."""
    found = []
    for line in prober_output.splitlines():
        device = line.split("@", 1)[0].split(":", 1)[0]
        if line.strip() and not (skip and device.startswith(f"/dev/{skip}")):
            found.append(line)
    return found


def main():
    out = subprocess.run(["lsblk", "-J", "-o", "NAME,TYPE,FSTYPE"], capture_output=True,
                         text=True, timeout=30).stdout or "{}"
    live = live_disk()
    disks = target_disks(out, live)
    found = []
    if any(has for _n, has in disks):
        try:
            found = systems(subprocess.run(["os-prober"], capture_output=True, text=True,
                                           timeout=120).stdout, live)
        except (OSError, subprocess.TimeoutExpired):
            found = []
    print(choice(disks, bool(found)))


if __name__ == "__main__":
    main()
