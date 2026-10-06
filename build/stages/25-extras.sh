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
    case "$sums" in
        sha256:*) expected=${sums#sha256:} ;;       # pinned in the list itself
        *) expected=$(curl -fsSL "$sums" | awk -v f="$file" '$2 == f || $2 == "*"f {print $1}') ;;
    esac
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
    # Each snapshot reads "Fresh install | 2026-10-07 00:39:43" (what, then
    # when), without the table header row grub-btrfs puts first: it looked like
    # an entry and started nothing, and the path column cut off the rest.
    sed -i 's|^#GRUB_BTRFS_SUBMENUNAME=.*|GRUB_BTRFS_SUBMENUNAME="Aurora OS snapshots"|; s|^#GRUB_BTRFS_LIMIT=.*|GRUB_BTRFS_LIMIT="20"|; s|^#GRUB_BTRFS_TITLE_FORMAT=.*|GRUB_BTRFS_TITLE_FORMAT=("description" "date")|' \
        "$ROOTFS/etc/default/grub-btrfs/config"
    grep -q '^GRUB_BTRFS_TITLE_FORMAT=("description" "date")' "$ROOTFS/etc/default/grub-btrfs/config" ||
        die "grub-btrfs: title format not set"
    grep -q '^header_menu$' "$ROOTFS/etc/grub.d/41_snapshots-btrfs" ||
        die "grub-btrfs: header_menu call not found (upstream changed?)"
    sed -i 's/^header_menu$/: # header_menu: no table header row (Aurora)/' "$ROOTFS/etc/grub.d/41_snapshots-btrfs"
    sed -i -f "$SRC/build/grub-btrfs-titles.sed" "$ROOTFS/etc/grub.d/41_snapshots-btrfs"
    [ "$(grep -c "menuentry 'Aurora OS, Linux" "$ROOTFS/etc/grub.d/41_snapshots-btrfs")" = 2 ] ||
        die "grub-btrfs: kernel titles not patched (upstream changed?)"
    ! grep -q "{ echo }\"$" "$ROOTFS/etc/grub.d/41_snapshots-btrfs" ||
        die "grub-btrfs: snapshot title row not removed (upstream changed?)"
fi

# adw-gtk3 is for GTK 3 apps. Its gtk-4.0 folder targets a newer GTK than
# Debian's 4.18 (hundreds of "Unknown @ rule" errors in every GTK 4 app), and
# libadwaita apps already look right without it.
rm -rf "$ROOTFS"/usr/share/themes/adw-gtk3*/gtk-4.0
