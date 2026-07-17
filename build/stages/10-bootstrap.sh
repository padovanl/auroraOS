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

write_sources

touch "$ROOTFS/.aurora-bootstrapped"
