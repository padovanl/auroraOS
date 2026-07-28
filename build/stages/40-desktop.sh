#!/bin/bash
# Install the Aurora desktop (our own code) into the image.
. "$(dirname "$0")/../lib.sh"

# /src is read-only: build in a scratch copy (keeps rendered wallpapers cached).
BUILD="$WORK/src"
mkdir -p "$BUILD"
rsync -a --delete --exclude /desktop/build "$SRC/desktop" "$SRC/branding" "$BUILD/"

log "installing Aurora desktop"
make -C "$BUILD/desktop" install DESTDIR="$ROOTFS" PREFIX=/usr

in_chroot glib-compile-schemas /usr/share/glib-2.0/schemas
in_chroot gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
in_chroot update-desktop-database -q /usr/share/applications || true

# Ptyxis is the default terminal (foot stays for scripted terminal windows).
in_chroot update-alternatives --set x-terminal-emulator /usr/bin/ptyxis || true
