"""Background file operations (copy, move, delete) with progress reporting."""

import os
import shutil
import threading

from gi.repository import GLib, GObject

from aurora.files.history import Entry
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
        self.changes = []  # (original path, final path), for undo/redo
        self.history_entry = None

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

    def _copy_file(self, src, dst):
        if self.cancelled:
            raise InterruptedError
        created = False
        try:
            if os.path.islink(src):
                os.symlink(os.readlink(src), dst)
                created = True
            else:
                with open(src, "rb") as source, open(dst, "xb") as target:
                    created = True
                    shutil.copyfileobj(source, target)
            shutil.copystat(src, dst, follow_symlinks=False)
        except (OSError, shutil.Error):
            if created:
                os.remove(dst)
            raise
        self._tick(os.path.basename(src))
        return dst

    def _run(self):
        error = ""
        try:
            self._total = _count(self.sources)
            for src in self.sources:
                if self.cancelled:
                    raise InterruptedError
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
                        self.changes.append((src, dest))
                        continue
                    except OSError:
                        pass  # different filesystem: copy then delete
                created_dir = False
                try:
                    if os.path.isdir(src) and not os.path.islink(src):
                        os.mkdir(dest)
                        created_dir = True
                        shutil.copytree(src, dest, symlinks=True, dirs_exist_ok=True,
                                        copy_function=self._copy_file)
                    else:
                        self._copy_file(src, dest)
                except (InterruptedError, OSError, shutil.Error):
                    # The destination was created by this job and is incomplete.
                    if created_dir:
                        shutil.rmtree(dest)
                    raise
                if self.kind == "move":
                    if os.path.isdir(src) and not os.path.islink(src):
                        shutil.rmtree(src)
                    else:
                        os.remove(src)
                self.changes.append((src, dest))
        except InterruptedError:
            error = _("Cancelled")
        except (OSError, shutil.Error) as err:
            error = str(err)
        if self.changes:
            try:
                self.history_entry = Entry(self.kind, list(self.changes))
            except OSError as err:
                error = error or str(err)
        GLib.idle_add(self.emit, "finished", error)
