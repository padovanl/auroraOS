#!/bin/bash
# Windows checkouts can expose every source file/directory as mode 0777.
# Install predictable image permissions independently of checkout metadata.
set -euo pipefail
overlay_source=${1:?overlay source required}
overlay_root=${2:?root filesystem required}
rsync -a --no-owner --no-group --chmod=D755,F644 "$overlay_source/" "$overlay_root/"
while IFS= read -r -d '' file; do
    if [ "$(head -c 2 "$file")" = '#!' ]; then
        chmod 755 "$overlay_root/${file#"$overlay_source/"}"
    fi
done < <(find "$overlay_source" -type f -print0)
if [ -d "$overlay_root/etc/sudoers.d" ]; then
    find "$overlay_root/etc/sudoers.d" -type f -exec chmod 440 {} +
fi
