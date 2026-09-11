"""Verified, resumable downloads for Aurora AI.

`fetch()` downloads to NAME.part, resumes an interrupted download with an HTTP
Range request, checks the SHA-256 from catalog.json and only then renames the
file into place. A file that fails the check is deleted, never used. A download
only starts if the disk keeps enough room for the system afterwards.
"""

import errno
import hashlib
import os
import shutil
import urllib.request

from aurora.i18n import _

CHUNK = 1 << 20


class DownloadError(Exception):
    pass


class Cancelled(Exception):
    pass


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def is_complete(item, dest):
    return os.path.exists(dest) and os.path.getsize(dest) == item["size"]


# Room left for the system after a download: models are gigabytes, and a full
# disk breaks updates, logins and btrfs itself.
RESERVE_MIN = 2 * 1024 ** 3
RESERVE_MAX = 10 * 1024 ** 3
RESERVE_FRACTION = 0.05


def reserve_for(total):
    """5% of the disk, at least 2 GB and at most 10 GB."""
    return max(RESERVE_MIN, min(RESERVE_MAX, int(total * RESERVE_FRACTION)))


def check_space(item, dest, have=0, usage=None):
    """Raise DownloadError unless the download leaves enough free space."""
    disk = (usage or shutil.disk_usage)(os.path.dirname(dest))
    need = max(0, item["size"] - have)
    reserve = reserve_for(disk.total)
    if disk.free - need < reserve:
        raise DownloadError(_(
            "Not enough disk space for {name}: it needs {need} and {reserve} must stay "
            "free for the system, but only {free} is free. Remove models you don't use in "
            "Settings → AI, or free up space.").format(
                name=os.path.basename(dest), need=_size(need), reserve=_size(reserve),
                free=_size(disk.free)))


def _size(n):
    return f"{n / 1e9:.1f} GB"


def fetch(item, dest, progress=None, cancelled=None, opener=urllib.request.urlopen):
    """Download item {url, size, sha256} to dest. progress(done, total) is called
    as bytes arrive; cancelled() returning True stops (the .part is kept)."""
    if is_complete(item, dest):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if have > item["size"]:
        os.remove(part)
        have = 0
    check_space(item, dest, have)
    req = urllib.request.Request(item["url"], headers={"User-Agent": "Aurora-OS"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    try:
        resp = opener(req, timeout=60)
    except OSError as e:
        raise DownloadError(str(e)) from e
    with resp:
        if have and getattr(resp, "status", 206) != 206:
            have = 0                      # the server ignored Range: start over
        with open(part, "ab" if have else "wb") as f:
            done = have
            while True:
                if cancelled and cancelled():
                    raise Cancelled()
                block = resp.read(CHUNK)
                if not block:
                    break
                try:
                    f.write(block)
                except OSError as e:
                    if e.errno != errno.ENOSPC:
                        raise
                    f.close()
                    os.remove(part)  # don't leave gigabytes behind on a full disk
                    raise DownloadError(_("The disk filled up while downloading {name}; "
                                          "free up space and try again").format(
                                              name=os.path.basename(dest))) from e
                done += len(block)
                if progress:
                    progress(done, item["size"])
    if os.path.getsize(part) != item["size"] or sha256_of(part) != item["sha256"]:
        os.remove(part)
        raise DownloadError(_("{name} is damaged (checksum mismatch); try again").format(name=os.path.basename(dest)))
    os.replace(part, dest)
    return dest
