#!/usr/bin/env python3
"""On UEFI machines, make the disk bootable through the fallback path too.

Firmware that doesn't keep boot entries (Hyper-V when you pick the disk as the
first device, many laptops after a firmware update, a disk moved to another
PC) starts \\EFI\\BOOT\\BOOTX64.EFI. Calamares' installEFIFallback copies a
single file there, but with Secure Boot support that file is shim, which also
needs GRUB and its small config next to it: the machine then skipped the disk
and tried to boot from the network. The shared EFI installer writes both
paths, selects direct GRUB on Hyper-V with Secure Boot off, and verifies the
result. The same helper refreshes these files after package updates.
Runs after the bootloader module.
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
