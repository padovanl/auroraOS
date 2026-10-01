"""Compressed archives in Files: Compress… and Extract Here, through File
Roller (zip, 7z, tar.xz and friends; rar with unar)."""

import os

ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz",
                    ".tar.bz2", ".tbz2", ".tar.zst", ".gz", ".xz", ".bz2", ".zst", ".cab",
                    ".iso", ".jar", ".apk", ".deb", ".cpio", ".lz", ".lzma")
FORMATS = ((".zip", "ZIP: opens everywhere, Windows included"),
           (".7z", "7-Zip: smaller files"),
           (".tar.xz", "tar.xz: smallest, keeps Linux permissions"))


def is_archive(name):
    lower = name.lower()
    return lower.endswith(ARCHIVE_SUFFIXES)


def archive_name(paths):
    """A name for an archive of these files: the file's own name for one, the
    folder's for several."""
    if len(paths) == 1:
        base = os.path.basename(paths[0].rstrip("/"))
        stem = base if os.path.isdir(paths[0]) else os.path.splitext(base)[0]
        return stem or "Archive"
    parent = os.path.basename(os.path.dirname(paths[0].rstrip("/")))
    return parent or "Archive"


def free_name(folder, stem, suffix):
    """stem.zip, or stem (2).zip if that exists, and so on."""
    candidate = os.path.join(folder, stem + suffix)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem} ({n}){suffix}")
        n += 1
    return candidate


def compress_command(paths, destination):
    return ["file-roller", f"--add-to={destination}"] + list(paths)


def extract_command(paths):
    return ["file-roller", "--extract-here"] + list(paths)
