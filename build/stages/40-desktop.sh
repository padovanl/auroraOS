#!/bin/bash
# Install the Aurora desktop (our own code) into the image.
. "$(dirname "$0")/../lib.sh"

log "installing Aurora desktop"
make -C "$SRC/desktop" install DESTDIR="$ROOTFS" PREFIX=/usr

in_chroot glib-compile-schemas /usr/share/glib-2.0/schemas
in_chroot gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
in_chroot update-desktop-database -q /usr/share/applications || true
