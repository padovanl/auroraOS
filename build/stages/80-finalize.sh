#!/bin/bash
# Clean the image and regenerate the initramfs.
. "$(dirname "$0")/../lib.sh"

log "setting plymouth theme"
if [ -d "$ROOTFS/usr/share/plymouth/themes/aurora" ]; then
    in_chroot plymouth-set-default-theme aurora
fi

log "regenerating initramfs"
in_chroot update-initramfs -u -k all

log "cleaning up"
# Detach the shared apt cache first, or apt-get clean would empty it.
umount "$ROOTFS/var/cache/apt/archives"
in_chroot apt-get -y autoremove --purge
in_chroot apt-get clean
rm -f "$ROOTFS/usr/sbin/policy-rc.d"
rm -rf "$ROOTFS"/var/lib/apt/lists/* "$ROOTFS"/tmp/* "$ROOTFS"/var/tmp/*
find "$ROOTFS/var/log" -type f -delete
# A fresh machine-id is generated on first boot.
: > "$ROOTFS/etc/machine-id"
rm -f "$ROOTFS/var/lib/dbus/machine-id"
