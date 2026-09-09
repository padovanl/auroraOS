#!/bin/bash
# Runs inside the builder container. Usage: build-inner.sh [stage...]
# With no arguments every stage runs in order.
. "$(dirname "$0")/lib.sh"

# All builder containers share /work. Serialise stages so a second build cannot
# replace the ISO staging tree while the first is still copying packages.
mkdir -p "$WORK"
exec 9>"$WORK/.build.lock"
flock 9

trap umount_chroot EXIT

stages=("$@")
if [ ${#stages[@]} -eq 0 ]; then
    stages=($(cd "$SRC/build/stages" && ls *.sh | sed 's/\.sh$//'))
fi

for s in "${stages[@]}"; do
    script=$(ls "$SRC"/build/stages/"$s"*.sh 2>/dev/null | head -1)
    [ -n "$script" ] || die "unknown stage: $s"
    log "=== stage $(basename "$script" .sh) ==="
    [ -d "$ROOTFS/proc" ] && mount_chroot
    bash "$script"
done
