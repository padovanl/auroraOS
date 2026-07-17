# Shared helpers for build stages. Sourced, not executed.

set -euo pipefail

SRC="${SRC:-/src}"
WORK="${WORK:-/work}"
ROOTFS="$WORK/rootfs"
ISODIR="$WORK/iso"
OUT="${OUT:-/out}"

# shellcheck source=../config/aurora.conf
. "$SRC/config/aurora.conf"

log() { printf '\033[1;35m[aurora]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[aurora] error:\033[0m %s\n' "$*" >&2; exit 1; }

# Read a package list, dropping comments and blank lines.
read_list() { sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$@"; }

mount_chroot() {
    mountpoint -q "$ROOTFS/proc" || mount -t proc proc "$ROOTFS/proc"
    mountpoint -q "$ROOTFS/sys" || mount -t sysfs sys "$ROOTFS/sys"
    mountpoint -q "$ROOTFS/dev" || mount --bind /dev "$ROOTFS/dev"
    mountpoint -q "$ROOTFS/dev/pts" || mount -t devpts devpts "$ROOTFS/dev/pts"
    mountpoint -q "$ROOTFS/run" || mount -t tmpfs tmpfs "$ROOTFS/run"
    mkdir -p "$WORK/cache/apt" "$ROOTFS/var/cache/apt/archives"
    mountpoint -q "$ROOTFS/var/cache/apt/archives" || \
        mount --bind "$WORK/cache/apt" "$ROOTFS/var/cache/apt/archives"
}

umount_chroot() {
    local m
    for m in var/cache/apt/archives run dev/pts dev sys proc; do
        mountpoint -q "$ROOTFS/$m" && umount -l "$ROOTFS/$m"
    done
    return 0
}

in_chroot() {
    LANG=C.UTF-8 DEBIAN_FRONTEND=noninteractive chroot "$ROOTFS" "$@"
}

write_sources() {
    cat > "$ROOTFS/etc/apt/sources.list.d/debian.sources" <<EOF
Types: deb
URIs: $DEBIAN_MIRROR
Suites: $DEBIAN_SUITE $DEBIAN_SUITE-updates
Components: $DEBIAN_COMPONENTS
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: $DEBIAN_SECURITY_MIRROR
Suites: $DEBIAN_SUITE-security
Components: $DEBIAN_COMPONENTS
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
    rm -f "$ROOTFS/etc/apt/sources.list"
}

apt_install() {
    in_chroot apt-get install -y --no-install-recommends "$@"
}
