"""Background file operations (copy, move, delete) with progress reporting."""

import os
import shutil
import threading

from gi.repository import GLib, GObject

from aurora.i18n import _


def unique_destination(folder, name):
    """Return a path in folder that does not exist yet, based on name."""
    dest = os.path.join(folder, name)
    if not os.path.lexists(dest):
        return dest
    stem, ext = os.path.splitext(name)
    if stem.startswith(".") and not ext:
        stem, ext = name, ""
    n = 2
    while True:
        dest = os.path.join(folder, f"{stem} ({n}){ext}")
        if not os.path.lexists(dest):
            return dest
        n += 1


def _count(paths):
    total = 0
    for p in paths:
        if os.path.isdir(p) and not os.path.islink(p):
            for _root, _dirs, files in os.walk(p):
                total += len(files) + 1
        else:
            total += 1
    return max(total, 1)


class Job(GObject.Object):
    """A copy/move job running in a thread. Signals are emitted on the main loop."""

    __gsignals__ = {
        "progress": (GObject.SignalFlags.RUN_FIRST, None, (float, str)),
        "finished": (GObject.SignalFlags.RUN_FIRST, None, (str,)),  # error or ""
    }

    def __init__(self, kind, sources, target_dir):
        super().__init__()
        self.kind = kind            # "copy" or "move"
        self.sources = sources
        self.target_dir = target_dir
        self.cancelled = False
        self._done = 0
        self._total = 1

    @property
    def label(self):
        n = len(self.sources)
        if self.kind == "move":
            return _("Moving {n} item(s)").format(n=n)
        return _("Copying {n} item(s)").format(n=n)

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        self.cancelled = True

    def _tick(self, name):
        self._done += 1
        GLib.idle_add(self.emit, "progress", min(1.0, self._done / self._total), name)
        if self.cancelled:
            raise InterruptedError

    def _copy_file(self, src, dst):
        shutil.copy2(src, dst, follow_symlinks=False)
        self._tick(os.path.basename(src))
        return dst

    def _run(self):
        error = ""
        try:
            self._total = _count(self.sources)
            for src in self.sources:
                name = os.path.basename(src.rstrip("/"))
                same_dir = os.path.dirname(os.path.abspath(src)) == os.path.abspath(self.target_dir)
                if self.kind == "move" and same_dir:
                    continue
                dest = unique_destination(self.target_dir, name)
                if os.path.abspath(dest).startswith(os.path.abspath(src) + os.sep):
                    raise OSError(_("Cannot copy a folder into itself"))
                if self.kind == "move":
                    try:
                        os.rename(src, dest)
                        self._tick(name)
                        continue
                    except OSError:
                        pass  # different filesystem: copy then delete
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.copytree(src, dest, symlinks=True, copy_function=self._copy_file)
                else:
                    self._copy_file(src, dest)
                if self.kind == "move":
                    if os.path.isdir(src) and not os.path.islink(src):
                        shutil.rmtree(src)
                    else:
                        os.remove(src)
        except InterruptedError:
            error = _("Cancelled")
        except (OSError, shutil.Error) as err:
            error = str(err)
        GLib.idle_add(self.emit, "finished", error)
