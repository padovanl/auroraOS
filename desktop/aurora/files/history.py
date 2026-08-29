"""Conservative, in-session undo/redo for local file operations.

Undo never overwrites an occupied name. A copied or newly created item can be
removed only while its metadata tree still matches the result of the action.
Trash is intentionally separate: its existing Restore command is authoritative.
"""

import os
import shutil
import stat
from dataclasses import dataclass, field


def signature(path):
    """Metadata of a whole tree, enough to detect normal edits before deletion."""
    entries = []

    def visit(current, relative):
        item = os.lstat(current)
        data = (relative, item.st_mode, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
        if stat.S_ISLNK(item.st_mode):
            data += (os.readlink(current),)
        entries.append(data)
        if stat.S_ISDIR(item.st_mode):
            for name in sorted(os.listdir(current)):
                visit(os.path.join(current, name), os.path.join(relative, name))

    visit(path, ".")
    return tuple(entries)


def remove_created(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def copy_exact(src, dst):
    if os.path.lexists(dst):
        raise FileExistsError(dst)
    if os.path.isdir(src) and not os.path.islink(src):
        shutil.copytree(src, dst, symlinks=True)
    elif os.path.islink(src):
        os.symlink(os.readlink(src), dst)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)


@dataclass
class Entry:
    kind: str  # copy, move, create-file, create-folder
    pairs: list  # (source path or None, destination path)
    snapshots: list = field(default_factory=list)

    def __post_init__(self):
        if self.kind in ("copy", "create-file", "create-folder"):
            self.snapshots = [signature(dst) for _src, dst in self.pairs]

    def undo(self):
        if self.kind in ("copy", "create-file", "create-folder"):
            for (_src, dst), before in zip(self.pairs, self.snapshots):
                if signature(dst) != before:
                    raise OSError(f"Changed since creation: {dst}")
            for _src, dst in reversed(self.pairs):
                remove_created(dst)
        else:
            for src, dst in self.pairs:
                if not os.path.lexists(dst) or os.path.lexists(src):
                    raise FileExistsError(src)
            for src, dst in reversed(self.pairs):
                shutil.move(dst, src)

    def redo(self):
        for src, dst in self.pairs:
            if os.path.lexists(dst):
                raise FileExistsError(dst)
            if src is not None and not os.path.lexists(src):
                raise FileNotFoundError(src)
        if self.kind == "create-file":
            for _src, dst in self.pairs:
                with open(dst, "x", encoding="utf-8"):
                    pass
        elif self.kind == "create-folder":
            for _src, dst in self.pairs:
                os.mkdir(dst)
        elif self.kind == "copy":
            for src, dst in self.pairs:
                copy_exact(src, dst)
        else:
            for src, dst in self.pairs:
                shutil.move(src, dst)
        if self.kind in ("copy", "create-file", "create-folder"):
            self.snapshots = [signature(dst) for _src, dst in self.pairs]


class History:
    def __init__(self, limit=30):
        self.undo_stack = []
        self.redo_stack = []
        self.limit = limit

    def record(self, kind, pairs):
        if not pairs:
            return
        self.push(Entry(kind, list(pairs)))

    def push(self, entry):
        self.undo_stack.append(entry)
        self.undo_stack = self.undo_stack[-self.limit:]
        self.redo_stack.clear()

    def undo(self):
        entry = self.undo_stack[-1]
        entry.undo()
        self.redo_stack.append(self.undo_stack.pop())

    def redo(self):
        entry = self.redo_stack[-1]
        entry.redo()
        self.undo_stack.append(self.redo_stack.pop())
