"""The installer's first disk option follows the disks."""

import json

from aurora import installchoice as ic


def lsblk(*devices):
    return json.dumps({"blockdevices": list(devices)})


def test_empty_disks_start_on_erase():
    disks = ic.target_disks(lsblk({"name": "nvme0n1", "type": "disk", "fstype": None},
                                  {"name": "sdb", "type": "disk", "fstype": None,
                                   "children": [{"name": "sdb1"}]},
                                  {"name": "zram0", "type": "disk", "fstype": None},
                                  {"name": "sr0", "type": "rom", "fstype": "iso9660"}),
                            skip="sdb")
    assert disks == [("nvme0n1", False)]
    assert ic.choice(disks, systems_found=False) == "erase"


def test_windows_starts_on_alongside_and_data_disks_on_nothing():
    disks = [("nvme0n1", True)]
    assert ic.choice(disks, systems_found=True) == "alongside"
    assert ic.choice(disks, systems_found=False) == "none"
    whole = ic.target_disks(lsblk({"name": "sda", "type": "disk", "fstype": "ntfs"}))
    assert whole == [("sda", True)]


def test_the_live_usb_is_not_another_system():
    out = ("/dev/sdb1:Aurora OS 0.1:Aurora:linux\n"
           "/dev/nvme0n1p1@/efi/Microsoft/Boot/bootmgfw.efi:Windows Boot Manager:Windows:efi\n")
    assert ic.systems(out, skip="sdb") == [out.splitlines()[1]]
    assert ic.systems("/dev/sdb1:Aurora:Aurora:linux\n", skip="sdb") == []
