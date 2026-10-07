"""Storage: how much each kind of file takes, and cleaning up, like Windows'
Storage page and Storage Sense.

Sizes are counted the way the disk sees them (allocated blocks), without
following links. Cleaning only touches the Trash, your cache and temporary
files, and (only when you ask) old files in Downloads.
"""

import datetime
import os
import shutil
import time
import urllib.parse

from gi.repository import GLib


def tree_size(path, stop=None):
    """Bytes a folder takes on disk. `stop()` returning True ends the count early."""
    total = 0
    stack = [path]
    while stack:
        if stop is not None and stop():
            break
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    total += st.st_blocks * 512
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
        except OSError:
            continue
    return total


def trash_dir():
    return os.path.join(GLib.get_user_data_dir(), "Trash")


def trash_items(trash=None):
    """[(name, deleted at as a timestamp or None)] in the Trash."""
    trash = trash or trash_dir()
    out = []
    try:
        names = os.listdir(os.path.join(trash, "files"))
    except OSError:
        return out
    for name in names:
        when = None
        try:
            with open(os.path.join(trash, "info", name + ".trashinfo")) as f:
                for line in f:
                    if line.startswith("DeletionDate="):
                        when = datetime.datetime.fromisoformat(
                            line.split("=", 1)[1].strip()).timestamp()
        except (OSError, ValueError):
            pass
        out.append((name, when))
    return out


def _remove(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True
    except OSError:
        return False


def empty_trash(older_than_days=None, trash=None, now=None):
    """Delete what's in the Trash (only what was deleted that many days ago, if
    given). Returns how many items went."""
    trash = trash or trash_dir()
    now = now or time.time()
    gone = 0
    for name, when in trash_items(trash):
        if older_than_days is not None and (when is None or
                                            now - when < older_than_days * 86400):
            continue
        if _remove(os.path.join(trash, "files", name)):
            _remove(os.path.join(trash, "info", name + ".trashinfo"))
            gone += 1
    return gone


def newest_change(path, limit=20000):
    """The latest modification time in a folder's whole tree: a folder's own
    time only changes when entries are added or removed directly in it, not
    when a file deeper inside is edited."""
    newest = os.lstat(path).st_mtime
    seen = 0
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            seen += 1
            if seen > limit:        # huge tree: treat it as recent, keep it
                return float("inf")
            try:
                newest = max(newest, os.lstat(os.path.join(root, name)).st_mtime)
            except OSError:
                continue
    return newest


def old_files(folder, days, now=None):
    """Files and folders directly in `folder` not changed for `days` days
    (a folder counts as changed when anything inside it was)."""
    now = now or time.time()
    out = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                try:
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if entry.name.startswith(".") or now - st.st_mtime <= days * 86400:
                    continue
                if entry.is_dir(follow_symlinks=False) and \
                        now - newest_change(entry.path) <= days * 86400:
                    continue
                out.append(entry.path)
    except OSError:
        pass
    return out


def to_trash(paths):
    """Move to the Trash (so a cleanup can still be undone)."""
    from gi.repository import Gio
    moved = 0
    for path in paths:
        try:
            Gio.File.new_for_path(path).trash(None)
            moved += 1
        except GLib.Error:
            continue
    return moved


def clear_cache(cache=None, keep=("aurora/wallpaper", "fontconfig")):
    """Empty ~/.cache (apps rebuild what they need), keeping a few things that
    are slow to remake or in use. Returns bytes freed."""
    cache = cache or GLib.get_user_cache_dir()
    freed = 0
    try:
        names = os.listdir(cache)
    except OSError:
        return 0
    for name in names:
        path = os.path.join(cache, name)
        if name in keep:
            continue
        if name == "aurora":
            # Only the thumbnails; the wallpaper link and weather stay.
            sub = os.path.join(path, "thumbnails")
            size = tree_size(sub)
            if _remove(sub):
                freed += size
            continue
        size = tree_size(path) if os.path.isdir(path) else os.lstat(path).st_blocks * 512
        if _remove(path):
            freed += size
    return freed


def temp_files(days, tmp="/tmp", uid=None, now=None):
    """Your own files in /tmp not touched for `days` days."""
    uid = os.getuid() if uid is None else uid
    now = now or time.time()
    out = []
    try:
        with os.scandir(tmp) as entries:
            for entry in entries:
                try:
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if st.st_uid == uid and now - max(st.st_mtime, st.st_atime) > days * 86400:
                    out.append(entry.path)
    except OSError:
        pass
    return out


def run_storage_sense(privacy, aurora=None):
    """What the switches ask for, once (the shell runs it at login and every
    few hours): old Trash items, old temporary files, old Downloads."""
    days = privacy.get_uint("old-files-age") if privacy else 30
    done = {}
    if privacy is not None and privacy.get_boolean("remove-old-trash-files"):
        done["trash"] = empty_trash(older_than_days=days)
    if privacy is not None and privacy.get_boolean("remove-old-temp-files"):
        done["temp"] = sum(_remove(p) for p in temp_files(days))
    if aurora is not None and aurora.get_int("downloads-cleanup-days") > 0:
        downloads = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        if downloads and os.path.realpath(downloads) != os.path.realpath(os.path.expanduser("~")):
            done["downloads"] = to_trash(old_files(downloads,
                                                   aurora.get_int("downloads-cleanup-days")))
    return done


def file_uri_to_path(uri):
    return urllib.parse.unquote(urllib.parse.urlparse(uri).path)
