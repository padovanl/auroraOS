#!/usr/bin/env python3
"""On UEFI machines, install Debian's signed shim and GRUB into the target.

Runs after bootloader-config (which installs plain grub-efi) and before the
bootloader module. Debian's grub-install uses the signed images when they
are installed, so the installed system boots with Secure Boot enabled.
The packages come from the offline pool on the USB stick.
"""

import os

import libcalamares


def pretty_name():
    return "Preparing Secure Boot"


def run():
    if not os.path.isdir("/sys/firmware/efi"):
        libcalamares.utils.debug("aurora-secureboot: BIOS system, nothing to do")
        return None
    rc = libcalamares.utils.target_env_call(
        ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y",
         "shim-signed", "grub-efi-amd64-signed"])
    if rc != 0:
        # Not fatal: the system still boots with Secure Boot disabled.
        libcalamares.utils.warning(f"aurora-secureboot: apt-get failed ({rc})")
    return None
