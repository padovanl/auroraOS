#!/usr/bin/env python3
"""Exercise the documented global keyboard shortcuts in a real QEMU desktop.

The checks use QMP keyboard events, inspect toplevel state through aurora-shell,
and keep screenshots of every shell surface.  Hardware-only keys and actions
that need a physical device or configured AI model are outside this scenario.
"""

import argparse
import os
import sys
import time

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vm import VM  # noqa: E402


results = []


def check(description, ok, detail=""):
    results.append((description, bool(ok), detail))
    print(f"{'ok' if ok else 'FAILED'}: {description}" +
          (f"  ({detail})" if detail and not ok else ""), flush=True)


def difference(a, b):
    first, second = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    return sum(ImageStat.Stat(ImageChops.difference(first, second)).mean) / 3


def visual(vm, description, label, keys, close=("esc",), threshold=1.0):
    before = vm.shot(f"{label}-before")
    vm.keys(*keys, pause=1.2)
    after = vm.shot(label)
    amount = difference(before, after)
    check(description, amount > threshold, f"screen difference {amount:.2f}")
    if close:
        vm.keys(*close, pause=0.8)


def app_shortcut(vm, description, keys, app_id):
    vm.keys(*keys, pause=1)
    opened = vm.wait_for(lambda: (vm.window(app_id) or {}).get("activated"), timeout=20)
    check(description, opened)
    if opened:
        vm.keys("meta_l", "q", pause=1)
        vm.wait_for(lambda: vm.window(app_id) is None, timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("iso")
    parser.add_argument("--out", default="work/shortcut-test")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    repo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
    vm = VM(args.iso, args.out)
    try:
        if args.push:
            vm.push_desktop(repo)
            # The session copied this file to the user's config at login; push
            # the corrected shared binding there too and ask labwc to reload.
            source = os.path.join(repo, "desktop", "data", "labwc", "rc.xml")
            vm.push(source, "/usr/share/aurora/labwc/rc.xml")
            vm.root("cp /usr/share/aurora/labwc/rc.xml /home/aurora/.config/labwc/rc.xml; "
                    "chown aurora:aurora /home/aurora/.config/labwc/rc.xml")
            vm.user("labwc --reconfigure")
            vm.restart_shell()

        vm.user("printf 'shortcut clipboard test' | wl-copy")
        visual(vm, "tap Super opens Spotlight", "spotlight-super", ("meta_l",))
        visual(vm, "Super+Space opens Spotlight", "spotlight-space", ("meta_l", "spc"))
        visual(vm, "Super+A opens Spotlight", "spotlight-a", ("meta_l", "a"))
        visual(vm, "Super+S opens Control Center", "control-center", ("meta_l", "s"))
        visual(vm, "Super+V opens clipboard history", "clipboard", ("meta_l", "v"))
        visual(vm, "Super+. opens the emoji picker", "emoji", ("meta_l", "dot"))
        visual(vm, "Super+/ opens keyboard shortcuts", "shortcuts", ("meta_l", "slash"))

        app_shortcut(vm, "Super+E opens Files", ("meta_l", "e"), "org.aurora.Files")
        app_shortcut(vm, "Super+I opens Settings", ("meta_l", "i"), "org.aurora.Settings")
        app_shortcut(vm, "Ctrl+Shift+Esc opens Task Manager",
                     ("ctrl", "shift", "esc"), "org.aurora.TaskManager")
        app_shortcut(vm, "Ctrl+Alt+T opens Terminal", ("ctrl", "alt", "t"),
                     "org.gnome.Ptyxis")

        vm.keys("meta_l", "ret", pause=1)
        terminal = vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("activated"),
                               timeout=20)
        check("Super+Enter opens Terminal", terminal)
        if terminal:
            vm.keys("meta_l", "e", pause=1)
            files = vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("activated"),
                                timeout=20)
            check("a second window opens for window-switching checks", files)
            if files:
                vm.keys("alt", "tab", pause=1)
                check("Alt+Tab switches to the next window",
                      bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))
                vm.keys("alt", "shift", "tab", pause=1)
                check("Alt+Shift+Tab switches to the previous window",
                      bool((vm.window("org.aurora.Files") or {}).get("activated")))
                vm.keys("meta_l", "tab", pause=1)
                check("Super+Tab switches to the next window",
                      bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))

                # Focusing Files must not cover a terminal marked always-on-top.
                # Turn the state off and repeat: the two frames then differ in
                # their overlapping center, which checks the visible effect.
                vm.keys("meta_l", "t", pause=1)
                vm.user("aurora-shell focus org.aurora.Files")
                time.sleep(1)
                top_on = vm.shot("always-on-top-enabled")
                vm.user("aurora-shell focus org.gnome.Ptyxis")
                time.sleep(0.5)
                vm.keys("meta_l", "t", pause=1)
                vm.user("aurora-shell focus org.aurora.Files")
                time.sleep(1)
                top_off = vm.shot("always-on-top-disabled")
                check("Super+T toggles keep-window-on-top",
                      difference(top_on, top_off) > 1.0)
                vm.keys("alt", "f4", pause=1)
                vm.user("aurora-shell focus org.gnome.Ptyxis")
                time.sleep(0.5)

            vm.keys("meta_l", "up", pause=1)
            check("Super+Up maximizes the window",
                  bool((vm.window("org.gnome.Ptyxis") or {}).get("maximized")))
            vm.keys("meta_l", "down", pause=1)
            check("Super+Down restores the window",
                  not bool((vm.window("org.gnome.Ptyxis") or {}).get("maximized")))
            previous = vm.shot("window-before-snapping")
            for description, label, keys in (
                    ("Super+Left snaps left", "snap-left", ("meta_l", "left")),
                    ("Super+Right snaps right", "snap-right", ("meta_l", "right")),
                    ("Super+Ctrl+U snaps top-left", "snap-top-left",
                     ("meta_l", "ctrl", "u")),
                    ("Super+Ctrl+I snaps top-right", "snap-top-right",
                     ("meta_l", "ctrl", "i")),
                    ("Super+Ctrl+J snaps bottom-left", "snap-bottom-left",
                     ("meta_l", "ctrl", "j")),
                    ("Super+Ctrl+K snaps bottom-right", "snap-bottom-right",
                     ("meta_l", "ctrl", "k")),
                    ("Super+Ctrl+D snaps left third", "snap-left-third",
                     ("meta_l", "ctrl", "d")),
                    ("Super+Ctrl+F snaps center third", "snap-center-third",
                     ("meta_l", "ctrl", "f")),
                    ("Super+Ctrl+G snaps right third", "snap-right-third",
                     ("meta_l", "ctrl", "g"))):
                vm.keys(*keys, pause=1)
                current = vm.shot(label)
                amount = difference(previous, current)
                check(description, amount > 0.5, f"screen difference {amount:.2f}")
                previous = current
            vm.keys("meta_l", "f", pause=1)
            check("Super+F enters full screen",
                  bool((vm.window("org.gnome.Ptyxis") or {}).get("fullscreen")))
            vm.keys("meta_l", "f", pause=1)
            check("Super+F leaves full screen",
                  not bool((vm.window("org.gnome.Ptyxis") or {}).get("fullscreen")))
            visual(vm, "Super+W opens Overview", "overview", ("meta_l", "w"))
            visual(vm, "Super+Z opens Snap Layouts", "snap-layouts", ("meta_l", "z"),
                   threshold=0.2)

            vm.keys("meta_l", "2", pause=1)
            check("Super+2 changes to workspace 2",
                  not bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))
            vm.keys("meta_l", "1", pause=1)
            check("Super+1 returns to workspace 1",
                  bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))
            vm.keys("meta_l", "shift", "2", pause=1)
            # labwc may follow a window when moving it. Return explicitly to
            # workspace 1 and verify that the window stayed on workspace 2.
            vm.keys("meta_l", "1", pause=1)
            check("Super+Shift+2 moves the window to workspace 2",
                  not bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))
            vm.keys("meta_l", "2", pause=1)
            check("the moved window is visible on workspace 2",
                  bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))
            vm.keys("ctrl", "alt", "left", pause=1)
            check("Ctrl+Alt+Left goes to the previous workspace",
                  not bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))
            vm.keys("ctrl", "alt", "right", pause=1)
            check("Ctrl+Alt+Right goes to the next workspace",
                  bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")))

            vm.keys("meta_l", "m", pause=1)
            check("Super+M minimizes the window",
                  bool((vm.window("org.gnome.Ptyxis") or {}).get("minimized")))
            vm.user("aurora-shell focus org.gnome.Ptyxis")
            vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("activated"), timeout=10)
            vm.keys("meta_l", "q", pause=1)
            check("Super+Q closes the window",
                  vm.wait_for(lambda: vm.window("org.gnome.Ptyxis") is None, timeout=10))

        vm.keys("meta_l", "ret", pause=1)
        terminal = vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("activated"),
                               timeout=20)
        if terminal:
            vm.keys("alt", "f4", pause=1)
        check("Alt+F4 closes the window",
              terminal and vm.wait_for(lambda: vm.window("org.gnome.Ptyxis") is None,
                                       timeout=10))

        before = vm.user("find ~/Pictures/Screenshots -type f 2>/dev/null | wc -l")[1].strip()
        vm.keys("print", pause=2)
        after = vm.user("find ~/Pictures/Screenshots -type f 2>/dev/null | wc -l")[1].strip()
        check("Print Screen saves a screenshot", int(after or 0) > int(before or 0),
              f"before {before}, after {after}")

        # Selection tools must at least enter their graphical selection mode;
        # Escape then cancels without modifying the desktop.
        for description, label, keys in (
                ("Shift+Print starts area selection", "area-screenshot", ("shift", "print")),
                ("Super+Shift+S starts area selection", "area-screenshot-super",
                 ("meta_l", "shift", "s")),
                ("Super+Shift+T starts OCR selection", "ocr", ("meta_l", "shift", "t")),
                ("Super+Shift+P starts pin selection", "pin", ("meta_l", "shift", "p")),
                ("Super+Alt+Shift+R starts area recording selection", "area-recording",
                 ("meta_l", "alt", "shift", "r"))):
            visual(vm, description, label, keys, threshold=0.2)

        vm.keys("meta_l", "shift", "c", pause=0.8)
        check("Super+Shift+C starts the color picker",
              vm.user("pgrep -x slurp")[0] == 0)
        vm.keys("esc", pause=0.8)

        before = int(vm.user("find ~/Videos -type f -name '*.mp4' 2>/dev/null | wc -l")[1] or 0)
        vm.keys("meta_l", "alt", "r", pause=2)
        started = vm.user("pgrep -f '[w]f-recorder'")[0] == 0
        vm.keys("meta_l", "alt", "r", pause=2)
        stopped = vm.wait_for(lambda: vm.user("! pgrep -f '[w]f-recorder'")[0] == 0,
                              timeout=15)
        after = int(vm.user("find ~/Videos -type f -name '*.mp4' 2>/dev/null | wc -l")[1] or 0)
        check("Super+Alt+R starts and stops screen recording",
              started and stopped and after > before,
              f"started={started}, stopped={stopped}, files {before}->{after}")

        vm.keys("meta_l", "l", pause=2)
        locked = vm.user("pgrep -x gtklock")[0] == 0
        check("Super+L locks the screen", locked)
        if locked:
            vm.root("pkill -x gtklock")
            time.sleep(1)

        _code, log = vm.user("cat $XDG_RUNTIME_DIR/aurora-shell.log")
        check("shortcut use leaves no shell exceptions", "Traceback" not in log, log[-500:])
    finally:
        vm.close()
    failed = sum(not ok for _description, ok, _detail in results)
    print(f"\n{len(results) - failed}/{len(results)} shortcut checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
