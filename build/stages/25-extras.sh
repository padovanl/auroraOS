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
