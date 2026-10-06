#!/usr/bin/env python3
"""On UEFI machines, make the disk start on every firmware.

/usr/local/lib/aurora/efi-install installs Debian's signed chain in \\EFI\\debian
and a complete copy in the removable path \\EFI\\BOOT (grub-install
--force-extra-removable), and verifies both. Next to Windows or another
system that already starts from \\EFI\\BOOT, that path is left to it. On Hyper-V it writes no firmware
boot entry and removes the ones the bootloader module just made: guest-written
entries there sent the VM to PXE after installing. Runs after the bootloader
module; the same helper refreshes the files after package updates.
"""

import os

import libcalamares


def pretty_name():
    return "Making the disk bootable on every UEFI firmware"


def run():
    if not os.path.isdir("/sys/firmware/efi"):
        libcalamares.utils.debug("aurora-efi-fallback: BIOS system, nothing to do")
        return None
    rc = libcalamares.utils.target_env_call(
        ["/bin/bash", "/usr/local/lib/aurora/efi-install", "--install"])
    if rc != 0:
        return ("EFI bootloader installation failed",
                f"Could not install and verify the EFI boot files (exit {rc}).")
    return None
