#!/bin/bash
# Build Aurora's own packages (aurora-desktop, aurora-artwork) and install them.
. "$(dirname "$0")/../lib.sh"

# /src is read-only: build in a scratch copy (keeps rendered wallpapers cached).
BUILD="$WORK/src"
mkdir -p "$BUILD"
rsync -a --delete --exclude /desktop/build "$SRC/desktop" "$SRC/branding" "$BUILD/"
cp "$SRC/LICENSE" "$BUILD/"

version="${AURORA_PKG_VERSION:-$AURORA_VERSION.0}"
log "building Aurora packages $version"
bash "$SRC/build/package-desktop.sh" "$BUILD" "$OUT/debs" "$version"

log "installing Aurora packages"
mkdir -p "$ROOTFS/tmp/aurora-debs"
cp "$OUT"/debs/aurora-*_"$version"_all.deb "$ROOTFS/tmp/aurora-debs/"
in_chroot sh -c 'apt-get install -y --allow-downgrades /tmp/aurora-debs/*.deb'
rm -rf "$ROOTFS/tmp/aurora-debs"

# The Aurora archive key; the source is switched on once the repository is
# published (aurora-repo-check.timer), so apt never fails on a missing repo.
install -Dm644 "$SRC/config/keys/aurora-archive-keyring.gpg" \
    "$ROOTFS/usr/share/keyrings/aurora-archive-keyring.gpg"

in_chroot glib-compile-schemas /usr/share/glib-2.0/schemas
in_chroot gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
in_chroot update-desktop-database -q /usr/share/applications || true

# Ptyxis is the default terminal (foot stays for scripted terminal windows).
in_chroot update-alternatives --set x-terminal-emulator /usr/bin/ptyxis || true
