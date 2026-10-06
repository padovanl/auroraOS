#!/usr/bin/env python3
"""Exercise awkward but plausible keyboard sequences in a real Aurora VM.

Unlike shortcuts.py, this deliberately overlaps surfaces, repeats keys and
interrupts modal tools.  It catches stuck grabs, duplicate shell processes,
or shortcuts that accidentally act on the window below an overlay.
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


def process_count(vm, pattern):
    return int(vm.user(f"pgrep -fc {pattern}")[1].strip() or 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("iso")
    parser.add_argument("--out", default="work/shortcut-edge-test")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    vm = VM(args.iso, args.out)
    try:
        if args.push:
            repo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
            vm.push_desktop(repo)
            source = os.path.join(repo, "desktop", "data", "labwc", "rc.xml")
            vm.push(source, "/usr/share/aurora/labwc/rc.xml")
            vm.root("cp /usr/share/aurora/labwc/rc.xml /home/aurora/.config/labwc/rc.xml; "
                    "chown aurora:aurora /home/aurora/.config/labwc/rc.xml")
            vm.user("labwc --reconfigure")
            vm.restart_shell()
        baseline = vm.shot("baseline")

        # Escape is commonly pressed several times when the user is unsure
        # which surface owns the keyboard.
        for _ in range(8):
            vm.keys("esc", pause=0.05)
        check("repeated Escape leaves the desktop usable",
              process_count(vm, "'^/usr/bin/python3 /usr/bin/aurora-shell$'") == 1)

        # An odd burst should leave one launcher, never duplicate the shell.
        for _ in range(5):
            vm.keys("meta_l", "spc", pause=0.12)
        burst = vm.shot("spotlight-after-five-rapid-presses")
        # Key repeat and the Super-on-release binding can legitimately make a
        # burst end either open or closed.  Escape is the user's usual reset;
        # the next deliberate shortcut must then work normally.
        vm.keys("esc", pause=0.3)
        vm.keys("meta_l", "spc", pause=0.7)
        recovered = vm.shot("spotlight-after-burst-recovery")
        check("rapid Spotlight presses recover with Escape",
              difference(baseline, recovered) > 1.0)
        vm.keys("esc", pause=0.5)

        # Move directly between the shell's keyboard surfaces without closing
        # the previous one first, as users often do while searching.
        previous = vm.shot("before-surface-switching")
        for description, label, keys in (
                ("Control Center replaces the current surface", "edge-control-center",
                 ("meta_l", "s")),
                ("Clipboard replaces Control Center", "edge-clipboard", ("meta_l", "v")),
                ("Emoji replaces Clipboard", "edge-emoji", ("meta_l", "dot")),
                ("shortcut help replaces Emoji", "edge-shortcuts", ("meta_l", "slash"))):
            vm.keys(*keys, pause=0.7)
            current = vm.shot(label)
            check(description, difference(previous, current) > 0.5)
            previous = current
        vm.keys("esc", pause=0.5)

        # A compositor selection owns the input.  Cancelling it must restore
        # global shortcuts instead of leaving a stuck keyboard grab.
        for description, label, keys in (
                ("area screenshot", "screenshot", ("shift", "print")),
                ("OCR", "ocr", ("meta_l", "shift", "t")),
                ("pin", "pin", ("meta_l", "shift", "p")),
                ("color picker", "color-picker", ("meta_l", "shift", "c")),
                ("area recording", "area-recording", ("meta_l", "alt", "shift", "r"))):
            vm.keys(*keys, pause=0.5)
            selecting = vm.user("pgrep -x slurp")[0] == 0
            # This shortcut is intentional noise.  It must be discarded, not
            # replayed after the modal selector exits.
            vm.keys("meta_l", "spc", pause=0.2)
            vm.keys("esc", pause=0.2)
            released = vm.wait_for(lambda: vm.user("pgrep -x slurp")[0] != 0,
                                   timeout=5)
            if not released:
                # Keep one failed selector from invalidating every later case.
                vm.user("pkill -x slurp")
                vm.wait_for(lambda: vm.user("pgrep -x slurp")[0] != 0, timeout=2)
            time.sleep(0.5)  # let the shell's idle callback release its modal state
            vm.keys("meta_l", "spc", pause=0.7)
            after_cancel = vm.shot(f"spotlight-after-cancelled-{label}")
            check(f"cancelling {description} discards queued shortcuts",
                  selecting and released and difference(baseline, after_cancel) > 1.0,
                  f"selecting={selecting}, released={released}")
            vm.keys("esc", pause=0.5)

        # Exercise state changes in an order that normal happy-path tests do
        # not: fullscreen, snap, minimize and recover the same window.
        vm.keys("meta_l", "ret", pause=1)
        terminal = vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("activated"),
                               timeout=20)
        check("terminal opens before mixed window-state shortcuts", terminal)
        if terminal:
            vm.keys("meta_l", "f", pause=0.5)
            vm.keys("meta_l", "left", pause=0.5)
            vm.keys("meta_l", "m", pause=0.7)
            minimized = bool((vm.window("org.gnome.Ptyxis") or {}).get("minimized"))
            vm.user("aurora-shell focus org.gnome.Ptyxis")
            recovered = vm.wait_for(
                lambda: bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")), timeout=10)
            check("fullscreen → snap → minimize can be recovered", minimized and recovered)

            # Toggle always-on-top twice quickly, then close.  No stale rule
            # should affect the next terminal.
            vm.keys("meta_l", "t", pause=0.15)
            vm.keys("meta_l", "t", pause=0.4)
            vm.keys("meta_l", "q", pause=0.7)
            closed = vm.wait_for(lambda: vm.window("org.gnome.Ptyxis") is None, timeout=10)
            vm.keys("meta_l", "ret", pause=1)
            reopened = vm.wait_for(
                lambda: bool((vm.window("org.gnome.Ptyxis") or {}).get("activated")), timeout=20)
            check("rapid always-on-top toggles do not poison the next window",
                  closed and reopened)
            if reopened:
                vm.keys("alt", "f4", pause=0.7)

        # Closing keys with no client must be harmless.
        vm.keys("alt", "f4", pause=0.2)
        vm.keys("meta_l", "q", pause=0.5)
        check("close-window shortcuts are harmless on the bare desktop",
              process_count(vm, "'^/usr/bin/python3 /usr/bin/aurora-shell$'") == 1)

        # Bursty screenshots should not overwrite one another.
        before = int(vm.user("find ~/Pictures/Screenshots -type f 2>/dev/null | wc -l")[1] or 0)
        for _ in range(3):
            vm.keys("print", pause=0.35)
        time.sleep(2)
        after = int(vm.user("find ~/Pictures/Screenshots -type f 2>/dev/null | wc -l")[1] or 0)
        check("three quick screenshots create three distinct files", after >= before + 3,
              f"files {before}->{after}")

        # Recording is especially prone to races.  Start/stop twice and make
        # sure both the real process and any zombie are gone.
        for _ in range(4):
            vm.keys("meta_l", "alt", "r", pause=0.8)
        stopped = vm.wait_for(lambda: vm.user("! pgrep -f '[w]f-recorder'")[0] == 0,
                              timeout=20)
        check("rapid record toggles finish without a recorder process", stopped)

        # A deliberately over-modified unknown chord must not leak modifiers
        # into the next, valid shortcut.
        vm.keys("meta_l", "ctrl", "alt", "shift", "esc", pause=0.2)
        vm.keys("meta_l", "i", pause=1)
        settings = vm.wait_for(lambda: (vm.window("org.aurora.Settings") or {}).get("activated"),
                               timeout=20)
        check("an unknown four-modifier chord does not leave modifiers stuck", settings)
        if settings:
            vm.keys("alt", "f4", pause=0.5)

        # Repeated singleton-app shortcuts should focus one instance, not race
        # and create a stack of Settings or Task Manager windows.
        for _ in range(3):
            vm.keys("meta_l", "i", pause=0.18)
        settings_ready = vm.wait_for(
            lambda: any(w["app_id"] == "org.aurora.Settings" for w in vm.windows()), timeout=20)
        settings_count = sum(w["app_id"] == "org.aurora.Settings" for w in vm.windows())
        check("three quick Settings shortcuts keep a single window",
              settings_ready and settings_count == 1, f"windows={settings_count}")
        if settings_ready:
            vm.keys("alt", "f4", pause=0.7)

        for _ in range(3):
            vm.keys("ctrl", "shift", "esc", pause=0.18)
        task_ready = vm.wait_for(
            lambda: any(w["app_id"] == "org.aurora.TaskManager" for w in vm.windows()),
            timeout=20)
        task_count = sum(w["app_id"] == "org.aurora.TaskManager" for w in vm.windows())
        check("three quick Task Manager shortcuts keep a single window",
              task_ready and task_count == 1, f"windows={task_count}")
        if task_ready:
            vm.keys("alt", "f4", pause=0.7)

        # Check wrap-around and the highest documented workspace rather than
        # only the adjacent workspace exercised by the normal suite.
        vm.keys("meta_l", "ret", pause=1)
        terminal = vm.wait_for(lambda: (vm.window("org.gnome.Ptyxis") or {}).get("activated"),
                               timeout=20)
        if terminal:
            vm.keys("ctrl", "alt", "left", pause=0.7)
            wrapped = not bool((vm.window("org.gnome.Ptyxis") or {}).get("activated"))
            vm.keys("ctrl", "alt", "right", pause=0.7)
            returned = bool((vm.window("org.gnome.Ptyxis") or {}).get("activated"))
            check("workspace navigation wraps from 1 to 9 and back", wrapped and returned)
            vm.keys("meta_l", "shift", "9", pause=0.7)
            vm.keys("meta_l", "9", pause=0.7)
            on_nine = bool((vm.window("org.gnome.Ptyxis") or {}).get("activated"))
            vm.keys("meta_l", "shift", "1", pause=0.7)
            vm.keys("meta_l", "1", pause=0.7)
            on_one = bool((vm.window("org.gnome.Ptyxis") or {}).get("activated"))
            check("a window can be moved to workspace 9 and back", on_nine and on_one)
            vm.keys("alt", "f4", pause=0.7)
        else:
            check("workspace navigation wraps from 1 to 9 and back", False, "terminal absent")
            check("a window can be moved to workspace 9 and back", False, "terminal absent")

        # Lock while a keyboard-grabbing overlay is open, then make sure input
        # works immediately after unlocking (simulated by ending gtklock).
        vm.keys("meta_l", "slash", pause=0.7)
        vm.keys("meta_l", "l", pause=1)
        locked = vm.wait_for(lambda: vm.user("pgrep -x gtklock")[0] == 0, timeout=10)
        if locked:
            vm.root("pkill -x gtklock")
            time.sleep(1)
        vm.keys("meta_l", "i", pause=1)
        post_lock = vm.wait_for(
            lambda: bool((vm.window("org.aurora.Settings") or {}).get("activated")), timeout=20)
        check("locking over an overlay returns a working keyboard", locked and post_lock)
        if post_lock:
            vm.keys("alt", "f4", pause=0.7)

        # The session watchdog must recover even if the shell dies while it
        # owns an exclusive keyboard surface.
        vm.keys("meta_l", "v", pause=0.7)
        vm.restart_shell()
        vm.keys("meta_l", "spc", pause=0.8)
        after_restart = vm.shot("spotlight-after-overlay-crash-recovery")
        check("shell restart during an overlay releases and restores shortcuts",
              difference(baseline, after_restart) > 1.0)
        vm.keys("esc", pause=0.5)

        _code, log = vm.user("cat $XDG_RUNTIME_DIR/aurora-shell.log")
        check("edge-case shortcut use leaves no shell exceptions", "Traceback" not in log,
              log[-500:])
        check("edge-case shortcut use leaves one shell process",
              process_count(vm, "'^/usr/bin/python3 /usr/bin/aurora-shell$'") == 1)
        check("edge-case shortcut use leaves no selection helper",
              vm.user("! pgrep -x slurp")[0] == 0)
    finally:
        vm.close()

    failed = sum(not ok for _description, ok, _detail in results)
    print(f"\n{len(results) - failed}/{len(results)} shortcut edge checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
