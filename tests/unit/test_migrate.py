"""Migrating from Windows: finding it, reading it, and copying out of it
without ever writing back or overwriting what is already here."""

import json
import os

import pytest

from aurora import migrate

LSBLK = json.dumps({"blockdevices": [
    {"name": "sda", "path": "/dev/sda", "fstype": None, "children": [
        {"name": "sda1", "path": "/dev/sda1", "fstype": "vfat", "label": "EFI",
         "size": "512M", "mountpoint": "/boot/efi", "rm": False},
        {"name": "sda2", "path": "/dev/sda2", "fstype": "ntfs", "label": "Windows",
         "size": "220G", "mountpoint": None, "rm": False},
        {"name": "sda3", "path": "/dev/sda3", "fstype": "ext4", "label": "aurora",
         "size": "200G", "mountpoint": "/", "rm": False}]},
    {"name": "sdb", "path": "/dev/sdb", "fstype": None, "children": [
        {"name": "sdb1", "path": "/dev/sdb1", "fstype": "ntfs", "label": "Old laptop",
         "size": "500G", "mountpoint": "/media/luca/Old", "rm": True}]}]})


@pytest.fixture
def windows(tmp_path):
    """A Windows installation, as far as this program is concerned."""
    root = tmp_path / "windows"
    (root / "Windows" / "System32").mkdir(parents=True)
    for user in ("Luca", "Public", "Default"):
        (root / "Users" / user).mkdir(parents=True)
    luca = root / "Users" / "Luca"
    for folder, names in (("Documents", ["lettera.odt", "conti.xlsx", "desktop.ini"]),
                          ("Pictures", ["mare.jpg", "Thumbs.db"]),
                          ("Downloads", []),
                          ("Desktop", ["appunti.txt"])):
        (luca / folder).mkdir()
        for name in names:
            (luca / folder / name).write_text(name)
    (luca / "Documents" / "Lavoro").mkdir()
    (luca / "Documents" / "Lavoro" / "piano.md").write_text("piano")
    (root / "Users" / "Public" / "Documents").mkdir(parents=True)
    return root


# --- finding it ------------------------------------------------------------

def test_every_ntfs_filesystem_is_offered(tmp_path):
    found = migrate.ntfs_partitions(LSBLK)
    assert [p["path"] for p in found] == ["/dev/sda2", "/dev/sdb1"]
    assert found[0]["label"] == "Windows" and not found[0]["removable"]
    assert found[1]["mountpoint"] == "/media/luca/Old" and found[1]["removable"]
    assert migrate.ntfs_partitions("not json") == []
    assert migrate.ntfs_partitions("{}") == []


def test_an_ntfs_disk_is_not_a_windows_installation(windows, tmp_path):
    assert migrate.is_windows(str(windows))
    assert not migrate.is_windows(str(tmp_path))
    assert not migrate.is_windows("")
    assert not migrate.is_windows(None)


# --- reading it ------------------------------------------------------------

def test_only_real_accounts_with_files_are_listed(windows):
    found = migrate.profiles(str(windows))
    assert [p["name"] for p in found] == ["Luca"]       # Public and Default are Windows'
    names = [f["name"] for f in found[0]["folders"]]
    assert names == ["Desktop", "Documents", "Downloads", "Pictures"]


def test_a_folder_is_measured_for_the_person_choosing(windows):
    folder = str(windows / "Users" / "Luca" / "Documents")
    size, count, whole = migrate.measure(folder)
    assert whole and count == 4 and size > 0
    # A measurement that runs out of time says so instead of lying.
    _size, _count, finished = migrate.measure(folder, deadline=-1)
    assert finished is False


# --- copying ---------------------------------------------------------------

def test_the_plan_puts_each_folder_where_it_belongs(windows, home, monkeypatch):
    profile = migrate.profiles(str(windows))[0]
    plan = dict(migrate.copy_plan(profile, {"Documents", "Pictures"}, home=str(home)))
    assert len(plan) == 2
    for source, destination in plan.items():
        assert os.path.basename(source) in ("Documents", "Pictures")
        assert destination  # a real path on this side
    assert not migrate.copy_plan(profile, set(), home=str(home))


def test_copying_keeps_what_is_already_here(windows, tmp_path):
    source = windows / "Users" / "Luca" / "Documents"
    destination = tmp_path / "home" / "Documents"
    destination.mkdir(parents=True)
    (destination / "lettera.odt").write_text("the one I already wrote here")
    skipped = []
    copied = migrate.copy_tree(str(source), str(destination), skipped=skipped)
    # conti.xlsx and Lavoro/piano.md; desktop.ini is Windows' own clutter and
    # lettera.odt was already here.
    assert copied == 2
    assert (destination / "conti.xlsx").exists()
    assert (destination / "Lavoro" / "piano.md").read_text() == "piano"
    assert not (destination / "desktop.ini").exists()
    # The file that was here is untouched, and reported as kept.
    assert (destination / "lettera.odt").read_text() == "the one I already wrote here"
    assert skipped == [str(destination / "lettera.odt")]


def test_nothing_is_written_to_the_windows_side(windows, tmp_path):
    source = windows / "Users" / "Luca" / "Pictures"
    before = sorted(os.listdir(source))
    migrate.copy_tree(str(source), str(tmp_path / "out"))
    assert sorted(os.listdir(source)) == before


# --- bookmarks and background ---------------------------------------------

def test_bookmarks_are_read_from_a_chromium_profile(tmp_path):
    bookmarks = {"roots": {"bookmark_bar": {"children": [
        {"type": "url", "name": "Aurora", "url": "https://aurora.example"},
        {"type": "folder", "name": "Work", "children": [
            {"type": "url", "name": "Mail", "url": "https://mail.example"}]}]}}}
    profile = tmp_path / "Users" / "Luca"
    edge = profile / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data" / "Default"
    edge.mkdir(parents=True)
    (edge / "Bookmarks").write_text(json.dumps(bookmarks))
    files = migrate.browser_bookmark_files(str(profile))
    assert list(files) == ["Microsoft Edge"]
    items = migrate.chromium_bookmarks(files["Microsoft Edge"])
    assert items == [("Aurora", "https://aurora.example"), ("Mail", "https://mail.example")]
    assert migrate.chromium_bookmarks(str(tmp_path / "nope")) == []


def test_the_bookmarks_file_is_one_any_browser_imports():
    html = migrate.bookmarks_html({"Microsoft Edge": [("A & B", "https://a.example?x=1&y=2")],
                                   "Empty": []})
    assert html.startswith("<!DOCTYPE NETSCAPE-Bookmark-file-1>")
    assert "<H3>Microsoft Edge</H3>" in html and "<H3>Empty</H3>" not in html
    assert 'HREF="https://a.example?x=1&amp;y=2"' in html and ">A &amp; B<" in html


def test_the_windows_background_is_found_only_when_it_is_there(tmp_path):
    profile = tmp_path / "Luca"
    themes = profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Themes"
    themes.mkdir(parents=True)
    assert migrate.windows_wallpaper(str(profile)) is None
    (themes / "TranscodedWallpaper").write_bytes(b"\xff\xd8jpeg")
    assert migrate.windows_wallpaper(str(profile)) == str(themes / "TranscodedWallpaper")
