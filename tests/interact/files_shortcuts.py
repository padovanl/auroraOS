#!/usr/bin/env python3
"""Exercise the documented Files shortcuts in a real VM."""

import argparse
import os
import sys
import time

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vm import VM  # noqa: E402


results = []
FOLDER = (765, 330)
FILE_A = (890, 330)
FILE_B = (1015, 330)


def check(description, ok, detail=""):
    results.append((description, bool(ok), detail))
    print(f"{'ok' if ok else 'FAILED'}: {description}" +
          (f"  ({detail})" if detail and not ok else ""), flush=True)


def difference(a, b, box=None):
    first, second = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if box:
        first, second = first.crop(box), second.crop(box)
    return sum(ImageStat.Stat(ImageChops.difference(first, second)).mean) / 3


def type_keys(vm, text, pause=0.06):
    names = {"/": "slash", ".": "dot", "-": "minus", " ": "spc"}
    for char in text:
        key = names.get(char, char.lower())
        vm.keys("shift", key, pause=pause) if char.isupper() else vm.keys(key, pause=pause)


def exists(vm, path):
    return vm.user(f"test -e {path}")[0] == 0


def mark(vm, phase):
    vm.user(f"printf '\\n-- {phase} --\\n' >> /tmp/files-shortcuts.log")


def files_windows(vm):
    return [w for w in vm.windows() if w["app_id"] == "org.aurora.Files"]


def quicklook_windows(vm):
    # Quick Look is a second application surface, not a second Files window.
    return [w for w in vm.windows() if w["app_id"] == "aurora-files"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("iso")
    parser.add_argument("--out", default="work/files-shortcut-test")
    parser.add_argument("--push", action="store_true",
                        help="copy the checkout's desktop code into the live system")
    args = parser.parse_args()
    vm = VM(args.iso, args.out)
    try:
        if args.push:
            pushed = vm.push_desktop(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))))
            print(f"pushed {len(pushed)} changed desktop files", flush=True)
        vm.user("rm -rf ~/FilesTest; mkdir -p ~/FilesTest/Sub; "
                "printf alpha > ~/FilesTest/a.txt; printf beta > ~/FilesTest/b.txt; "
                "printf secret > ~/FilesTest/.secret; "
                "setsid -f aurora-files ~/FilesTest >/tmp/files-shortcuts.log 2>&1")
        opened = vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("title") ==
                             "FilesTest", timeout=20)
        time.sleep(2)
        check("Files opens the requested folder", opened)
        baseline = vm.shot("files-baseline")

        mark(vm, "quick-look")
        vm.click(*FILE_A)
        vm.keys("spc", pause=1)
        preview = vm.wait_for(lambda: bool(quicklook_windows(vm)), timeout=10)
        check("Space opens Quick Look for the selected file", preview)
        vm.keys("esc", pause=0.8)
        check("Escape closes Quick Look",
              vm.wait_for(lambda: not quicklook_windows(vm), timeout=10))

        mark(vm, "duplicate")
        vm.click(*FILE_A)
        vm.keys("ctrl", "d", pause=0.5)
        copy_path = "'/home/aurora/FilesTest/a (2).txt'"
        duplicated = vm.wait_for(lambda: exists(vm, copy_path), timeout=10)
        check("Ctrl+D duplicates the selected file", duplicated)
        vm.keys("ctrl", "z", pause=0.5)
        undone = vm.wait_for(lambda: not exists(vm, copy_path), timeout=10)
        vm.keys("ctrl", "shift", "z", pause=0.5)
        redone = vm.wait_for(lambda: exists(vm, copy_path), timeout=10)
        check("Ctrl+Z and Ctrl+Shift+Z undo and redo duplication", undone and redone)
        vm.user("rm -f '/home/aurora/FilesTest/a (2).txt'")
        vm.keys("f5", pause=0.8)

        mark(vm, "rename")
        vm.click(*FILE_A)
        vm.keys("f2", pause=0.5)
        type_keys(vm, "renamed")
        vm.keys("ret", pause=0.8)
        renamed = vm.wait_for(lambda: exists(vm, "~/FilesTest/renamed.txt"), timeout=10)
        _code, names = vm.user("find ~/FilesTest -mindepth 1 -maxdepth 1 -printf '%f\\n' | sort")
        check("F2 renames the selected file", renamed, names.strip())
        vm.keys("ctrl", "z", pause=0.6)
        check("Ctrl+Z undoes a rename",
              vm.wait_for(lambda: exists(vm, "~/FilesTest/a.txt"), timeout=10))

        mark(vm, "trash-and-undo")
        vm.click(*FILE_A)
        vm.keys("delete", pause=0.7)
        trashed = vm.wait_for(lambda: not exists(vm, "~/FilesTest/a.txt"), timeout=10)
        vm.keys("ctrl", "z", pause=0.7)
        restored = vm.wait_for(lambda: exists(vm, "~/FilesTest/a.txt"), timeout=10)
        check("Delete moves to Trash and Ctrl+Z restores", trashed and restored)

        mark(vm, "permanent-delete-cancel")
        vm.click(*FILE_A)
        vm.keys("shift", "delete", pause=0.6)
        vm.keys("esc", pause=0.6)
        check("Escape cancels permanent deletion", exists(vm, "~/FilesTest/a.txt"))

        mark(vm, "new-folder")
        vm.keys("ctrl", "shift", "n", pause=0.5)
        type_keys(vm, "NewDir")
        vm.keys("ret", pause=0.8)
        created = vm.wait_for(lambda: exists(vm, "~/FilesTest/NewDir"), timeout=10)
        vm.keys("ctrl", "z", pause=0.6)
        removed = vm.wait_for(lambda: not exists(vm, "~/FilesTest/NewDir"), timeout=10)
        check("new-folder shortcut and Undo work together", created and removed)

        mark(vm, "copy-path")
        vm.click(*FILE_B)
        vm.keys("ctrl", "shift", "c", pause=0.5)
        _code, clipboard = vm.user("wl-paste --no-newline")
        check("Ctrl+Shift+C copies the full path", clipboard.strip() == "/home/aurora/FilesTest/b.txt",
              clipboard.strip())

        mark(vm, "navigation")
        vm.keys("ctrl", "l", pause=0.3)
        type_keys(vm, "/tmp")
        vm.keys("ret", pause=0.8)
        at_tmp = vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("title") == "tmp",
                             timeout=10)
        vm.keys("alt", "home", pause=0.8)
        at_home = vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("title") == "Home",
                              timeout=10)
        vm.keys("alt", "left", pause=0.8)
        back = vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("title") == "tmp",
                           timeout=10)
        vm.keys("alt", "right", pause=0.8)
        forward = vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("title") == "Home",
                              timeout=10)
        check("location entry, Home, Back and Forward preserve navigation history",
              at_tmp and at_home and back and forward)

        mark(vm, "tabs")
        vm.keys("ctrl", "t", pause=0.8)
        two_tabs = vm.shot("files-two-tabs")
        check("Ctrl+T creates a visibly separate tab",
              difference(baseline, two_tabs, (680, 235, 1450, 290)) > 0.5)
        vm.keys("ctrl", "tab", pause=0.4)
        vm.keys("ctrl", "shift", "tab", pause=0.4)
        vm.keys("ctrl", "w", pause=0.8)
        check("tab cycling and Ctrl+W leave Files usable",
              bool((vm.window("org.aurora.Files") or {}).get("activated")))

        mark(vm, "view-and-search")
        vm.keys("ctrl", "1", pause=0.8)
        list_view = vm.shot("files-list-view")
        check("Ctrl+1 changes list/grid view", difference(baseline, list_view) > 1.0)
        vm.keys("ctrl", "f", pause=0.6)
        search = vm.shot("files-search")
        check("Ctrl+F opens search", difference(list_view, search) > 0.5)
        vm.keys("esc", pause=0.5)

        _code, log = vm.user("cat /tmp/files-shortcuts.log")
        check("Files shortcut use leaves no exceptions", "Traceback" not in log, log[-500:])
        critical_context = "\n".join(line for line in log.splitlines()
                                     if line.startswith("-- ") or "CRITICAL" in line)
        check("Files shortcut use leaves no GTK criticals", "Gtk-CRITICAL" not in log,
              critical_context[-1500:])
    finally:
        vm.user("rm -rf ~/FilesTest")
        vm.close()

    failed = sum(not ok for _description, ok, _detail in results)
    print(f"\n{len(results) - failed}/{len(results)} Files shortcut checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
