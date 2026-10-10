"""The USB Stick Writer: which disks it offers, what it reads, what the
privileged helper refuses. The refusals are the part that keeps a disk safe,
so they are tested on the helper itself, not on the window's copy of them."""

import bz2
import gzip
import importlib.util
import lzma
import os
from pathlib import Path
import zipfile

import pytest

from aurora import usbwriter

ROOT = Path(__file__).resolve().parents[2]

# One line per mount, in the kernel's own format.
MOUNTS = """\
25 1 8:2 / / rw,relatime shared:1 - ext4 /dev/sda2 rw
26 25 8:1 / /boot/efi rw,relatime shared:2 - vfat /dev/sda1 rw
31 25 8:17 / /media/luca/STICK rw,nosuid shared:5 - vfat /dev/sdb1 rw
40 25 0:40 / /run/live/medium ro,noatime shared:9 - iso9660 /dev/sdc1 ro
"""


def helper():
    path = ROOT / "desktop" / "libexec" / "aurora-usb-write"
    spec = importlib.util.spec_from_loader(
        "aurora_usb_write", importlib.machinery.SourceFileLoader("aurora_usb_write", str(path)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- what the window offers ------------------------------------------------

def test_the_disks_holding_the_system_are_never_offered():
    busy = usbwriter.system_disks(MOUNTS)
    assert "sda" in busy                    # / and /boot/efi live there
    assert "sdc" in busy                    # the live medium we booted from
    assert "sdb" not in busy                # just a stick someone plugged in


def test_a_partition_name_is_traced_back_to_its_disk():
    for source, disk in (("/dev/nvme0n1p2", "nvme0n1"), ("/dev/mmcblk0p1", "mmcblk0"),
                         ("/dev/sda1", "sda")):
        line = f"25 1 8:2 / / rw,relatime shared:1 - ext4 {source} rw\n"
        assert usbwriter.system_disks(line) == {disk}


def test_sizes_read_the_way_a_person_says_them():
    assert usbwriter.human(512) == "512 B"
    assert usbwriter.human(3 * 1024 ** 2) == "3.0 MB"
    assert usbwriter.human(15_900_000_000).endswith("GB")


# --- what it can read ------------------------------------------------------

@pytest.fixture
def image(tmp_path):
    path = tmp_path / "disk.img"
    path.write_bytes(os.urandom(64 * 1024))
    return path


def read_all(path):
    make, total = usbwriter.opener(str(path))
    with make() as stream:
        return stream.read(), total


def test_a_plain_image_is_read_as_it_is(image):
    data, total = read_all(image)
    assert data == image.read_bytes() and total == len(data)


def test_compressed_images_are_unpacked_while_writing(image, tmp_path):
    raw = image.read_bytes()
    gz = tmp_path / "disk.img.gz"
    gz.write_bytes(gzip.compress(raw))
    data, total = read_all(gz)
    assert data == raw and total == len(raw)       # gzip states the real size

    xz = tmp_path / "disk.img.xz"
    xz.write_bytes(lzma.compress(raw))
    data, total = read_all(xz)
    assert data == raw and total is None           # xz doesn't, so the bar pulses

    bz = tmp_path / "disk.img.bz2"
    bz.write_bytes(bz2.compress(raw))
    assert read_all(bz)[0] == raw

    zipped = tmp_path / "disk.zip"
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr("disk.img", raw)
    data, total = read_all(zipped)
    assert data == raw and total == len(raw)


def test_a_zip_with_several_files_is_refused(image, tmp_path):
    zipped = tmp_path / "two.zip"
    with zipfile.ZipFile(zipped, "w") as archive:
        archive.writestr("a.img", b"a")
        archive.writestr("b.img", b"b")
    with pytest.raises(ValueError):
        usbwriter.opener(str(zipped))


# --- what the helper refuses ----------------------------------------------

def test_the_helper_only_takes_a_whole_disk():
    module = helper()
    for target in ("/dev/sda1", "/dev/nvme0n1p1", "/etc/passwd", "/dev/../etc/passwd",
                   "/dev/mapper/crypt", "sda", ""):
        with pytest.raises(SystemExit):
            module.check(target)


def test_the_helper_knows_which_mounts_belong_to_the_target():
    module = helper()
    assert module.belongs_to("/dev/sdb1", "/dev/sdb")
    assert module.belongs_to("/dev/sdb", "/dev/sdb")
    assert not module.belongs_to("/dev/sda1", "/dev/sdb")
    assert not module.belongs_to("tmpfs", "/dev/sdb")
    points = dict((point, source) for source, point in module.mounted_filesystems(MOUNTS))
    assert points["/"] == "/dev/sda2" and points["/media/luca/STICK"] == "/dev/sdb1"


def test_the_helper_refuses_the_disk_the_system_runs_from(monkeypatch, tmp_path):
    module = helper()
    # A disk that looks removable in every way, but holds the running system.
    (tmp_path / "sdb").mkdir()
    (tmp_path / "sdb" / "removable").write_text("1\n")
    (tmp_path / "sdb" / "ro").write_text("0\n")
    monkeypatch.setattr(module.os.path, "exists", lambda path: True)
    monkeypatch.setattr(module.os.path, "realpath", lambda path: path)
    monkeypatch.setattr(module.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(module, "read_sysfs",
                        lambda name, *parts: {"removable": "1", "ro": "0"}.get(parts[0], ""))
    monkeypatch.setattr(module, "mounted_filesystems", lambda text=None: [("/dev/sdb1", "/")])
    with pytest.raises(SystemExit):
        module.check("/dev/sdb")
    # The same disk with nothing of the system's on it is accepted.
    monkeypatch.setattr(module, "mounted_filesystems",
                        lambda text=None: [("/dev/sdb1", "/media/luca/STICK")])
    assert module.check("/dev/sdb") == "/dev/sdb"


def test_the_helper_refuses_a_disk_that_is_neither_removable_nor_usb(monkeypatch):
    module = helper()
    monkeypatch.setattr(module.os.path, "exists", lambda path: True)
    monkeypatch.setattr(module.os.path, "realpath", lambda path: path)
    monkeypatch.setattr(module.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(module, "read_sysfs", lambda name, *parts: "0")
    monkeypatch.setattr(module, "is_usb", lambda name: False)
    monkeypatch.setattr(module, "mounted_filesystems", lambda text=None: [])
    with pytest.raises(SystemExit):
        module.check("/dev/sdb")
    # Not removable, but on the USB bus: an SSD in a USB case is a fair target.
    monkeypatch.setattr(module, "is_usb", lambda name: True)
    assert module.check("/dev/sdb") == "/dev/sdb"


def test_the_helper_refuses_a_write_protected_stick(monkeypatch):
    module = helper()
    monkeypatch.setattr(module.os.path, "exists", lambda path: True)
    monkeypatch.setattr(module.os.path, "realpath", lambda path: path)
    monkeypatch.setattr(module.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(module, "read_sysfs",
                        lambda name, *parts: {"removable": "1", "ro": "1"}.get(parts[0], ""))
    monkeypatch.setattr(module, "mounted_filesystems", lambda text=None: [])
    with pytest.raises(SystemExit):
        module.check("/dev/sdb")
