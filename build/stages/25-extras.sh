#!/bin/bash
# Install third-party .deb packages listed in config/extra-debs.list,
# verifying each against its publisher's checksum file.
. "$(dirname "$0")/../lib.sh"

dir="$WORK/cache/extras"
mkdir -p "$dir" "$ROOTFS/tmp/extras"

sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/extra-debs.list" |
while IFS='|' read -r name version url sums; do
    name=$(echo $name); url=$(echo $url); sums=$(echo $sums)
    file=$(basename "$url")
    log "extra: $name $version"
    [ -f "$dir/$file" ] || curl -fsSL -o "$dir/$file" "$url"
    expected=$(curl -fsSL "$sums" | awk -v f="$file" '$2 == f || $2 == "*"f {print $1}')
    [ -n "$expected" ] || die "no checksum for $file in $sums"
    actual=$(sha256sum "$dir/$file" | cut -d' ' -f1)
    [ "$expected" = "$actual" ] || die "checksum mismatch for $file"
    cp "$dir/$file" "$ROOTFS/tmp/extras/"
done

# Paths as seen from inside the chroot.
debs=$(cd "$ROOTFS" && ls tmp/extras/*.deb | sed 's|^|/|')
# shellcheck disable=SC2086
apt_install $debs
rm -rf "$ROOTFS/tmp/extras"

# Pinned archives (config/extra-archives.list).
sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/extra-archives.list" |
while IFS='|' read -r name version url sha dest; do
    name=$(echo $name); url=$(echo $url); sha=$(echo $sha); dest=$(echo $dest)
    file="$dir/$(basename "$url")"
    log "extra archive: $name $version"
    [ -f "$file" ] || curl -fsSL -o "$file" "$url"
    echo "$sha  $file" | sha256sum -c --quiet - || die "checksum mismatch for $name"
    mkdir -p "$ROOTFS$dest"
    tar -xf "$file" -C "$ROOTFS$dest"
done

# grub-btrfs: "Aurora OS snapshots" in the boot menu (Timeshift snapshots).
# Not packaged by Debian; installed from the pinned upstream release. The menu
# script and the daemon are switched on per install, only on btrfs
# (Calamares aurora-finalize), so ext4/xfs installs and the live ISO ignore it.
gbsrc=$(ls -d "$ROOTFS"/usr/src/grub-btrfs-* 2>/dev/null | head -1)
if [ -n "$gbsrc" ]; then
    log "installing grub-btrfs"
    make -C "$gbsrc" install DESTDIR="$ROOTFS" PREFIX=/usr INSTALL_DOCS=false >/dev/null
    rm -rf "$gbsrc"
    chmod -x "$ROOTFS/etc/grub.d/41_snapshots-btrfs"
    sed -i 's|^#GRUB_BTRFS_SUBMENUNAME=.*|GRUB_BTRFS_SUBMENUNAME="Aurora OS snapshots"|; s|^#GRUB_BTRFS_LIMIT=.*|GRUB_BTRFS_LIMIT="20"|' \
        "$ROOTFS/etc/default/grub-btrfs/config"
fi

# adw-gtk3 is for GTK 3 apps. Its gtk-4.0 folder targets a newer GTK than
# Debian's 4.18 (hundreds of "Unknown @ rule" errors in every GTK 4 app), and
# libadwaita apps already look right without it.
rm -rf "$ROOTFS"/usr/share/themes/adw-gtk3*/gtk-4.0
