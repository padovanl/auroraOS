#!/usr/bin/env python3
"""Use the live desktop the way a person does, and check what happens.

Usage: scenarios.py ISO [--out DIR] [--push]

Boots the ISO in QEMU, then clicks, double-clicks and types (through a USB
tablet and QMP key presses) and asks the shell which windows exist and in which
state (`aurora-shell windows`). Each scenario is a bug someone hit by hand.
Screenshots of every step are kept in DIR. Exits non-zero if any check fails.
"""

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vm import VM  # noqa: E402

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
INSTALLER_ICON = (70, 100)  # first desktop icon on the live system
EMPTY_DESKTOP = (1300, 500)

results = []


def check(desc, ok, detail=""):
    results.append((desc, bool(ok), detail))
    print(f"{'ok' if ok else 'FAILED'}: {desc}" + (f"  ({detail})" if detail and not ok else ""),
          flush=True)


def region_diff(a, b, box):
    """Mean absolute difference of two screenshots inside box."""
    from PIL import Image, ImageChops, ImageStat
    ia, ib = Image.open(a).convert("RGB").crop(box), Image.open(b).convert("RGB").crop(box)
    return sum(ImageStat.Stat(ImageChops.difference(ia, ib)).mean) / 3


def calamares(vm):
    code, out = vm.root("pgrep -c -x calamares")
    return int(out.strip() or 0) if code == 0 else 0


def desktop_icons(vm):
    box = (0, 40, 200, 200)
    before = vm.shot("desktop")
    vm.click(*INSTALLER_ICON)
    selected = vm.shot("icon-selected")
    vm.click(*EMPTY_DESKTOP)
    cleared = vm.shot("icon-cleared")
    check("a click selects a desktop icon", region_diff(before, selected, box) > 1.0)
    check("a click on the empty desktop clears the selection",
          region_diff(before, cleared, box) < 0.5)


def desktop_file(vm):
    # Any icon, not only the installer: a text file below it opens in Text Editor.
    vm.user("printf 'hello\\n' > ~/Desktop/notes.txt")
    time.sleep(2)
    vm.shot("desktop-file")
    vm.click(INSTALLER_ICON[0], INSTALLER_ICON[1] + 110, double=True)
    check("double-clicking a file on the desktop opens it",
          vm.wait_for(lambda: vm.window("org.gnome.TextEditor"), timeout=20))
    vm.root("pkill -f [g]nome-text-editor")
    vm.user("rm -f ~/Desktop/notes.txt; mkdir -p ~/Desktop/Project")
    vm.wait_for(lambda: not vm.windows(), timeout=10)
    time.sleep(2)
    vm.click(INSTALLER_ICON[0], INSTALLER_ICON[1] + 110, double=True)
    check("double-clicking a folder on the desktop opens it in Files",
          vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("title") == "Project",
                      timeout=20))
    vm.root("pkill -f [a]urora-files")
    vm.user("rmdir ~/Desktop/Project")
    vm.wait_for(lambda: not vm.windows(), timeout=10)


def shell_recovers(vm):
    # A crash must not leave the session without its bar and dock.
    vm.root("pkill -9 -f '^/usr/bin/python3 /usr/bin/[a]urora-shell$'")
    back = vm.wait_for(lambda: vm.root("pgrep -f '^/usr/bin/python3 /usr/bin/[a]urora-shell$' "
                                       "&& test -f /run/user/1000/aurora-shell.ready")[0] == 0,
                       timeout=30)
    time.sleep(3)
    check("the shell starts again by itself after a crash", back)


def installer(vm):
    vm.click(*INSTALLER_ICON, double=True)
    opened = vm.wait_for(lambda: vm.window("io.calamares.calamares"), timeout=30)
    vm.shot("installer")
    check("double-clicking Install Aurora OS opens the installer", opened)
    vm.click(*EMPTY_DESKTOP)
    vm.click(*INSTALLER_ICON, double=True, pause=3)
    w = vm.window("io.calamares.calamares")
    check("opening it again brings the same installer forward",
          calamares(vm) == 1 and w and w["activated"], f"{calamares(vm)} running, {w}")
    vm.root("pkill -x calamares")
    vm.wait_for(lambda: calamares(vm) == 0, timeout=15)
    vm.click(*INSTALLER_ICON, double=True)
    check("the installer opens again after it was closed",
          vm.wait_for(lambda: vm.window("io.calamares.calamares"), timeout=30))
    vm.root("pkill -x calamares")
    vm.wait_for(lambda: not vm.windows(), timeout=15)


def terminal(vm):
    vm.keys("meta_l", "ret", pause=1)
    ok = vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("activated"), timeout=20)
    check("Super+Return opens a focused terminal", ok)
    vm.keys("meta_l", "m", pause=1.5)
    check("Super+M minimizes it", (vm.window("org.gnome.Ptyxis") or {}).get("minimized"))
    vm.shot("minimized")
    vm.user("aurora-shell focus org.gnome.Ptyxis")
    w = vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("activated"), timeout=5)
    check("a minimized window comes back from the shell (dock, overview)",
          w and not vm.window("org.gnome.Ptyxis")["minimized"])


def control_center(vm):
    # Esc must close it, and the keyboard must go back to the terminal: typing
    # "exit" there closes the window.
    vm.keys("meta_l", "s", pause=1.2)
    vm.shot("control-center")
    vm.keys("esc", pause=0.8)
    for key in ("e", "x", "i", "t", "ret"):
        vm.keys(key, pause=0.15)
    check("Esc closes the Control Center and the keyboard returns to the window",
          vm.wait_for(lambda: vm.window("org.gnome.Ptyxis") is None, timeout=10))


def hot_corner(vm):
    vm.keys("meta_l", "ret", pause=1)
    vm.wait_for(lambda: vm.window("org.gnome.Ptyxis"), timeout=20)
    vm.move(1000, 500)
    vm._events([{"type": "abs", "data": {"axis": "x", "value": 32767}},
                {"type": "abs", "data": {"axis": "y", "value": 32767}}])
    ok = vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("minimized"), timeout=5)
    vm.move(1000, 500)
    check("the bottom-right hot corner shows the desktop", ok)
    vm.root("pkill -x ptyxis; pkill -f [p]tyxis-agent")


def files(vm):
    vm.user("setsid -f aurora-files > /tmp/files.log 2>&1 < /dev/null")
    vm.wait_for(lambda: vm.window("org.aurora.Files"), timeout=20)
    time.sleep(2)
    vm.right_click(1300, 750)
    vm.shot("files-menu")
    vm.keys("esc")
    _c, log = vm.user("cat /tmp/files.log")
    check("Files shows its context menu without errors", "Traceback" not in log, log[-300:])
    vm.root("pkill -f [a]urora-files")


def settings(vm):
    pages = sorted(set(re.findall(r'page_id = "([a-z]+)"', "".join(
        open(os.path.join(REPO, "desktop/aurora/settingsapp", f)).read()
        for f in os.listdir(os.path.join(REPO, "desktop/aurora/settingsapp")) if f.endswith(".py")))))
    vm.user("setsid -f aurora-settings > /tmp/settings.log 2>&1 < /dev/null")
    vm.wait_for(lambda: vm.window("org.aurora.Settings"), timeout=20)
    for page in pages:
        vm.user(f"aurora-settings --page {page}")
        time.sleep(1)
    vm.shot("settings")
    _c, log = vm.user("cat /tmp/settings.log")
    check(f"every Settings page opens ({len(pages)})", "Traceback" not in log, log[-300:])
    check("no Settings text lost to markup errors", "Failed to set text" not in log, log[-300:])
    vm.root("pkill -f [a]urora-settings")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--out", default="work/interact-test")
    ap.add_argument("--push", action="store_true",
                    help="first copy this checkout's desktop code into the VM (no rebuild)")
    args = ap.parse_args()
    vm = VM(args.iso, args.out)
    if args.push:
        vm.push_desktop(REPO)
        vm.restart_shell()
    try:
        for scenario in (desktop_icons, desktop_file, installer, terminal, control_center, hot_corner,
                         files, settings, shell_recovers):
            try:
                scenario(vm)
            except Exception as err:  # noqa: BLE001 - report and go on with the others
                check(f"{scenario.__name__} ran", False, repr(err))
        _c, log = vm.user("cat $XDG_RUNTIME_DIR/aurora-shell.log")
        check("no shell exceptions", "Traceback" not in log, log[-300:])
    finally:
        vm.close()
    failed = sum(1 for _d, ok, _x in results if not ok)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
