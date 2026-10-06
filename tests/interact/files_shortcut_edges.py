#!/usr/bin/env python3
"""Stress Files shortcuts around focus, dialogs and asynchronous operations."""

import argparse
import os
import sys
import time

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vm import VM  # noqa: E402


ROOT = "/home/aurora/FilesEdge"
FOLDER = (765, 330)
FILE_A = (890, 330)
FILE_B_AFTER_COPY = (1140, 330)
results = []


def check(description, ok, detail=""):
    results.append((description, bool(ok), detail))
    print(f"{'ok' if ok else 'FAILED'}: {description}" +
          (f"  ({detail})" if detail and not ok else ""), flush=True)


def exists(vm, name):
    return vm.user(f"test -e '{ROOT}/{name}'")[0] == 0


def names(vm):
    return vm.user(f"find '{ROOT}' -mindepth 1 -maxdepth 1 -printf '%f\\n' | sort")[1].strip()


def type_keys(vm, text, pause=0.05):
    keys = {"/": "slash", ".": "dot", "-": "minus", " ": "spc"}
    for char in text:
        key = keys.get(char, char.lower())
        vm.keys("shift", key, pause=pause) if char.isupper() else vm.keys(key, pause=pause)


def difference(first, second, box=None):
    a, b = Image.open(first).convert("RGB"), Image.open(second).convert("RGB")
    if box:
        a, b = a.crop(box), b.crop(box)
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def quicklook(vm):
    return any(w["app_id"] == "aurora-files" for w in vm.windows())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("iso")
    parser.add_argument("--out", default="work/files-shortcut-edges")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    vm = VM(args.iso, args.out)
    try:
        if args.push:
            repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            print(f"pushed {len(vm.push_desktop(repo))} changed desktop files", flush=True)
        vm.user(f"rm -rf '{ROOT}'; mkdir -p '{ROOT}/Sub'; "
                f"printf alpha > '{ROOT}/a.txt'; printf beta > '{ROOT}/b.txt'; "
                f"printf gamma > '{ROOT}/c.txt'; printf secret > '{ROOT}/.hidden'; "
                f"setsid -f aurora-files '{ROOT}' >/tmp/files-edges.log 2>&1")
        opened = vm.wait_for(lambda: (vm.window("org.aurora.Files") or {}).get("title") ==
                             "FilesEdge", timeout=20)
        time.sleep(2)
        check("Files opens the edge-case fixture", opened)
        baseline = vm.shot("baseline")

        # Escape should cancel location editing, not leave an invisible input
        # context which consumes what the user types next.
        vm.keys("ctrl", "l", pause=0.4)
        editing = vm.shot("location-editing")
        vm.keys("esc", pause=0.5)
        cancelled = vm.shot("location-after-escape")
        check("Escape leaves Ctrl+L location editing",
              difference(baseline, cancelled, (700, 190, 1410, 245)) < 0.5,
              f"difference={difference(baseline, cancelled, (700, 190, 1410, 245)):.2f}")

        # Ctrl+A must belong to the rename entry while the dialog has focus.
        vm.click(*FILE_A)
        vm.keys("f2", pause=0.5)
        vm.keys("ctrl", "a", pause=0.2)
        type_keys(vm, "whole.md")
        vm.keys("ret", pause=0.8)
        selected_all = vm.wait_for(lambda: exists(vm, "whole.md"), timeout=5)
        check("Ctrl+A in Rename selects the entry text", selected_all, names(vm))
        if selected_all:
            vm.keys("ctrl", "z", pause=0.7)
        else:
            vm.user(f"mv '{ROOT}/whole.md.txt' '{ROOT}/a.txt' 2>/dev/null || true")
            vm.keys("f5", pause=0.8)

        # Text undo in a dialog must not undo the last file operation behind it.
        vm.click(*FILE_A)
        vm.keys("ctrl", "d", pause=0.5)
        copied = vm.wait_for(lambda: exists(vm, "a (2).txt"), timeout=5)
        vm.click(*FILE_A)
        vm.keys("f2", pause=0.5)
        type_keys(vm, "temp")
        vm.keys("ctrl", "z", pause=0.3)
        vm.keys("esc", pause=0.5)
        check("Ctrl+Z in Rename does not undo a file operation",
              copied and exists(vm, "a (2).txt"), names(vm))
        vm.user(f"rm -f '{ROOT}/a (2).txt'")
        vm.keys("f5", pause=0.8)

        # Delete edits the name field; it must not move the selected file to Trash.
        vm.click(*FILE_A)
        vm.keys("f2", pause=0.5)
        vm.keys("delete", pause=0.2)
        type_keys(vm, "x")
        vm.keys("esc", pause=0.5)
        check("Delete in Rename never trashes the selected file", exists(vm, "a.txt"), names(vm))

        # Search owns normal editing shortcuts too.
        vm.keys("ctrl", "f", pause=0.4)
        type_keys(vm, "zz")
        no_results = vm.shot("search-no-results")
        vm.keys("ctrl", "a", pause=0.2)
        type_keys(vm, "a")
        time.sleep(0.5)
        replaced_search = vm.shot("search-replaced")
        check("Ctrl+A replaces text in Search",
              difference(no_results, replaced_search, (700, 280, 1400, 800)) > 1.0)
        vm.keys("esc", pause=0.5)

        # Quick Look should toggle cleanly and arrows should move the Files selection.
        vm.click(*FILE_A)
        vm.keys("spc", pause=0.7)
        first_open = vm.wait_for(lambda: quicklook(vm), timeout=5)
        vm.keys("spc", pause=0.7)
        toggled_closed = vm.wait_for(lambda: not quicklook(vm), timeout=5)
        vm.keys("spc", pause=0.7)
        vm.keys("right", pause=0.3)
        vm.keys("esc", pause=0.5)
        vm.keys("f2", pause=0.5)
        type_keys(vm, "after-preview")
        vm.keys("ret", pause=0.8)
        moved_selection = exists(vm, "after-preview.txt")
        check("repeated Space and Quick Look arrows preserve a usable selection",
              first_open and toggled_closed and moved_selection, names(vm))
        if moved_selection:
            vm.keys("ctrl", "z", pause=0.6)

        # Delete is asynchronous. An immediate Undo must not consume an older
        # history item before the trash entry has been recorded.
        vm.click(*FILE_A)
        vm.keys("ctrl", "d", pause=0.5)
        prior_copy = vm.wait_for(lambda: exists(vm, "a (2).txt"), timeout=5)
        vm.click(*FILE_B_AFTER_COPY)
        vm.keys("delete", pause=0.01)
        vm.keys("ctrl", "z", pause=0.3)
        # On a fast disk the trash callback may finish before Ctrl+Z arrives;
        # then that key legitimately restores b.txt.  On a slower disk it is
        # ignored while trash is pending, so send Undo once the item is gone.
        # Either way, the older duplicate entry must remain untouched.
        previous_preserved = prior_copy and exists(vm, "a (2).txt")
        if not exists(vm, "b.txt"):
            vm.keys("ctrl", "z", pause=0.8)
        restored_after_pending = vm.wait_for(lambda: exists(vm, "b.txt"), timeout=5)
        check("immediate Ctrl+Z after Delete cannot undo the previous operation",
              previous_preserved and restored_after_pending and exists(vm, "a (2).txt"), names(vm))
        vm.keys("ctrl", "z", pause=0.6)

        # Trash/undo/redo must treat a multi-selection as one history entry.
        vm.keys("ctrl", "a", pause=0.2)
        vm.keys("delete", pause=0.8)
        all_trashed = vm.wait_for(lambda: not any(exists(vm, n) for n in
                                                  ("a.txt", "b.txt", "c.txt", "Sub")), timeout=8)
        vm.keys("ctrl", "z", pause=0.8)
        all_restored = vm.wait_for(lambda: all(exists(vm, n) for n in
                                               ("a.txt", "b.txt", "c.txt", "Sub")), timeout=8)
        vm.keys("ctrl", "y", pause=0.8)
        all_retrashed = vm.wait_for(lambda: not any(exists(vm, n) for n in
                                                    ("a.txt", "b.txt", "c.txt", "Sub")), timeout=8)
        vm.keys("ctrl", "z", pause=0.8)
        restored_again = vm.wait_for(lambda: all(exists(vm, n) for n in
                                                 ("a.txt", "b.txt", "c.txt", "Sub")), timeout=8)
        check("multi-file Trash is one undoable and redoable operation",
              all_trashed and all_restored and all_retrashed and restored_again, names(vm))

        # Two nearly simultaneous duplicate requests must not collide or lose data.
        vm.click(*FILE_A)
        vm.keys("ctrl", "d", pause=0.05)
        vm.keys("ctrl", "d", pause=0.05)
        two_copies = vm.wait_for(lambda: exists(vm, "a (2).txt") and exists(vm, "a (3).txt"),
                                 timeout=8)
        check("two rapid Ctrl+D operations create two distinct copies", two_copies, names(vm))

        # Toggling a state twice should return both UI and model to their start.
        before_hidden = vm.shot("before-hidden-toggle")
        vm.keys("ctrl", "h", pause=0.5)
        shown_hidden = vm.shot("hidden-shown")
        vm.keys("ctrl", "h", pause=0.5)
        hidden_again = vm.shot("hidden-again")
        check("two rapid hidden-file toggles return to the original view",
              difference(before_hidden, shown_hidden, (700, 280, 1450, 650)) > 0.5 and
              difference(before_hidden, hidden_again, (700, 280, 1450, 650)) < 0.5)

        _code, log = vm.user("cat /tmp/files-edges.log")
        check("edge combinations leave no exceptions", "Traceback" not in log, log[-1000:])
        check("edge combinations leave no GTK criticals", "Gtk-CRITICAL" not in log, log[-1000:])
    finally:
        vm.user(f"rm -rf '{ROOT}'")
        vm.close()

    failed = sum(not ok for _name, ok, _detail in results)
    print(f"\n{len(results) - failed}/{len(results)} Files edge checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
