#!/bin/bash
# Boot splash (plymouth) inside the image and GRUB theme assets for the ISO.
. "$(dirname "$0")/../lib.sh"

OUTB="$WORK/branding"
rm -rf "$OUTB"
log "rendering branding assets"
python3 "$SRC/branding/render.py" "$OUTB"

theme="$ROOTFS/usr/share/plymouth/themes/aurora"
mkdir -p "$theme"
cp "$SRC"/branding/plymouth/aurora.plymouth "$SRC"/branding/plymouth/aurora.script "$theme/"
cp "$OUTB"/plymouth/*.png "$theme/"

# GRUB fonts from the image's DejaVu (used by the theme and 90-iso).
cp "$SRC/branding/grub/theme.txt" "$OUTB/grub/"
dejavu="$ROOTFS/usr/share/fonts/truetype/dejavu"
for spec in "DejaVuSans.ttf:12" "DejaVuSans.ttf:16" "DejaVuSans-Bold.ttf:16"; do
    ttf=${spec%%:*} size=${spec##*:}
    grub-mkfont -s "$size" -o "$OUTB/grub/${ttf%.ttf}-$size.pf2" "$dejavu/$ttf"
done
