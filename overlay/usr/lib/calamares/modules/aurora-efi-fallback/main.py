#!/usr/bin/env python3
"""On UEFI machines, make the disk bootable through the fallback path too.

Firmware that doesn't keep boot entries (Hyper-V when you pick the disk as the
first device, many laptops after a firmware update, a disk moved to another
PC) starts \\EFI\\BOOT\\BOOTX64.EFI. Calamares' installEFIFallback copies a
single file there, but with Secure Boot support that file is shim, which also
needs GRUB and its small config next to it: the machine then skipped the disk
and tried to boot from the network. `grub-install --removable` writes the
complete set (shim, signed GRUB, MokManager, config) into \\EFI\\BOOT, the way
Debian intends. Runs after the bootloader module.
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
        ["grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi",
         "--removable", "--no-nvram", "--recheck"])
    if rc != 0:
        # The machine still boots through its own boot entry.
        libcalamares.utils.warning(f"aurora-efi-fallback: grub-install --removable failed ({rc})")
    return None
