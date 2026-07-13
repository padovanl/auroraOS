#!/bin/bash
# Create the minimal Debian root filesystem.
. "$(dirname "$0")/../lib.sh"

if [ -f "$ROOTFS/.aurora-bootstrapped" ]; then
    log "rootfs already bootstrapped, skipping (make clean to start over)"
    exit 0
fi

log "debootstrap $DEBIAN_SUITE ($ARCH) into $ROOTFS"
rm -rf "$ROOTFS"
mkdir -p "$ROOTFS" "$WORK/cache/apt"

debootstrap --arch="$ARCH" --variant=minbase \
    --components="${DEBIAN_COMPONENTS// /,}" \
    --cache-dir="$WORK/cache/apt" \
    "$DEBIAN_SUITE" "$ROOTFS" "$DEBIAN_MIRROR"

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

touch "$ROOTFS/.aurora-bootstrapped"
