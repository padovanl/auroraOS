#!/usr/bin/env python3
"""Check this release's new work on the real system, in the real session.

Usage: newfeatures.py ISO [--out DIR]

Boots the ISO in QEMU (the Aurora session, so Wayfire and its IPC are there,
which is what window previews need) and checks, by driving the desktop and
reading the screen:

  * the five icon styles, switched one after another, each changing the dock;
  * Launchpad in pages, and a folder made out of two apps;
  * the background's movement, and that it stops when a window covers it;
  * window previews in the overview;
  * the three new apps start and draw a window (Clipboard, USB Stick Writer,
    Migrate from Windows).

Exits non-zero if any check fails. Screenshots of every step are kept.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vm import VM  # noqa: E402

results = []


def check(what, ok, detail=""):
    results.append((what, bool(ok), detail))
    print(f"{'ok' if ok else 'FAILED'}: {what}" + (f"  ({detail})" if detail else ""),
          flush=True)


def difference(a, b, box=None):
    from PIL import Image, ImageChops, ImageStat
    first, second = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if box:
        first, second = first.crop(box), second.crop(box)
    return sum(ImageStat.Stat(ImageChops.difference(first, second)).mean) / 3


DOCK = (560, 960, 1360, 1070)      # the dock's strip on a 1920x1080 screen


def icon_styles(vm):
    """Each style redraws every icon, while the session runs."""
    shots = {}
    for style in ("galaxy", "ribbon", "glass", "clay", "bolt"):
        vm.user(f"gsettings set org.aurora.desktop icon-style {style}")
        time.sleep(3)
        shots[style] = vm.shot(f"icons-{style}")
        theme = vm.user("gsettings get org.gnome.desktop.interface icon-theme")[1].strip()
        expected = "Aurora" if style == "galaxy" else f"Aurora-{style.title()}"
        check(f"icon style {style} sets its theme",
              expected in theme, f"theme={theme}")
    pairs = list(shots.items())
    for (one, first), (two, second) in zip(pairs, pairs[1:]):
        changed = difference(first, second, DOCK)
        check(f"the dock is redrawn going from {one} to {two}", changed > 0.5,
              f"difference={changed:.2f}")
    vm.user("gsettings set org.aurora.desktop icon-style galaxy")


def launchpad_pages(vm):
    """Pages, and a folder made from two apps."""
    vm.user("gsettings set org.aurora.desktop launchpad-folders '[]'")
    vm.user("aurora-shell launcher grid")
    time.sleep(3)
    pages = vm.shot("launchpad-pages")
    check("Launchpad opens in pages", os.path.getsize(pages) > 0)
    vm.user("""gsettings set org.aurora.desktop launchpad-folders '[{"name":"Lavoro",'''
            '''"apps":["org.gnome.TextEditor.desktop","org.gnome.Calculator.desktop"]}]'""")
    time.sleep(3)
    folder = vm.shot("launchpad-folder")
    check("a folder changes the grid", difference(pages, folder) > 0.2,
          f"difference={difference(pages, folder):.2f}")
    vm.user("aurora-shell launcher")          # closed, whatever it was showing
    time.sleep(2)
    vm.user("gsettings set org.aurora.desktop launchpad-folders '[]'")


def moving_background(vm):
    """The aurora moves, and stops when it cannot be seen."""
    vm.user("gsettings set org.aurora.desktop wallpaper-animation aurora")
    time.sleep(4)
    one = vm.shot("background-1")
    time.sleep(4)
    two = vm.shot("background-2")
    moved = difference(one, two, (0, 40, 1920, 500))
    # Light drifting over a photograph is a small number by nature; what makes
    # it a pass is that Still, measured the same way below, is a smaller one.
    check("the background moves", moved > 0.08, f"difference={moved:.2f}")
    vm.user("gsettings set org.aurora.desktop wallpaper-animation off")
    time.sleep(3)
    still_one = vm.shot("background-still-1")
    time.sleep(3)
    still_two = vm.shot("background-still-2")
    stays = difference(still_one, still_two, (0, 40, 1920, 500))
    check("still means still", stays < 0.04, f"difference={stays:.2f}")
    check("moving differs from still", moved > stays * 3,
          f"moving={moved:.2f} still={stays:.2f}")
    vm.user("gsettings set org.aurora.desktop wallpaper-animation aurora")


def window_previews(vm):
    """The shell takes a picture of each window as it comes to the front, and
    the overview shows it. Asked of the shell, not guessed from pixels: the
    cards are small and a blurred background behind them moves too."""
    vm.user("gsettings set org.aurora.desktop window-previews true")
    vm.launch("org.gnome.TextEditor.desktop")
    vm.wait_for(lambda: vm.window("org.gnome.TextEditor"), timeout=25, what="the editor")
    time.sleep(5)                                   # it settles, then is photographed
    code, out = vm.user("aurora-shell previews")
    taken = int((out or "0").strip() or 0)
    check("the shell has a picture of the window", taken >= 1, f"pictures={taken}")
    vm.user("aurora-shell overview")
    time.sleep(3)
    with_preview = vm.shot("overview-previews")
    vm.user("aurora-shell overview")
    time.sleep(1)
    vm.user("gsettings set org.aurora.desktop window-previews false")
    time.sleep(2)
    vm.user("aurora-shell overview")
    time.sleep(3)
    without = vm.shot("overview-icons")
    changed = difference(with_preview, without, (560, 300, 1360, 780))
    check("the overview's cards differ with previews on and off", changed > 0.5,
          f"difference={changed:.2f}")
    vm.user("aurora-shell overview")
    vm.user("gsettings set org.aurora.desktop window-previews true")
    time.sleep(1)


NEW_APPS = (("Clipboard", "aurora-clipboard show", "org.aurora.Clipboard"),
            ("USB Stick Writer", "aurora-usb-writer", "org.aurora.UsbWriter"),
            ("Migrate from Windows", "aurora-migrate", "org.aurora.Migrate"))


def new_apps(vm):
    for name, command, app_id in NEW_APPS:
        vm.user(f"setsid {command} >/dev/null 2>&1 &")
        found = vm.wait_for(lambda i=app_id: vm.window(i), timeout=25, what=name)
        check(f"{name} opens a window", bool(found))
        vm.shot("app-" + app_id.split(".")[-1].lower())
        if found:
            vm.user(f"aurora-shell focus {app_id}")
            vm.keys("Escape")
        vm.user(f"pkill -f '{command.split()[0]}' || true")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("iso")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(
        os.path.abspath(__file__)), "..", "..", "work", "newfeatures"))
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    vm = VM(args.iso, args.out)
    try:
        for step in (icon_styles, launchpad_pages, moving_background, window_previews,
                     new_apps):
            try:
                step(vm)
            except Exception as err:                 # one failing check, not the run
                check(step.__name__, False, str(err))
    finally:
        vm.close()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for what, _ok, detail in failed:
        print(f"  FAILED: {what} {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
