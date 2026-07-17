#!/bin/bash
# Download the offline package pool used by the installer (see config/pool.list).
. "$(dirname "$0")/../lib.sh"

POOL="$WORK/pool"
rm -rf "$POOL"
mkdir -p "$POOL"
dl="$ROOTFS/tmp/aurora-pool"

sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/pool.list" | while read -r group; do
    log "pool: $group"
    rm -rf "$dl" && mkdir -p "$dl/partial"
    # shellcheck disable=SC2086
    in_chroot apt-get install -y --download-only --no-install-recommends \
        -o Dir::Cache::archives=/tmp/aurora-pool $group
    cp "$dl"/*.deb "$POOL/" 2>/dev/null || true
done
rm -rf "$dl"
log "pool: $(ls "$POOL" | wc -l) packages"
