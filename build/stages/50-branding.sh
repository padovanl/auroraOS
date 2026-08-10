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

# GRUB theme and fonts. Only Latin glyphs: bigger fonts overflow GRUB's heap on BIOS.
sed "s/@AURORA_TITLE@/$AURORA_NAME $AURORA_VERSION/" "$SRC/branding/grub/theme.txt" > "$OUTB/grub/theme.txt"
inter="$ROOTFS/usr/share/fonts/opentype/inter"
for spec in "Inter-Regular:16" "Inter-Regular:18" "Inter-Regular:20" \
            "Inter-SemiBold:28"; do
    name=${spec%%:*} size=${spec##*:}
    grub-mkfont -s "$size" -r 0x20-0x7E,0xA0-0x17F,0x2010-0x2027 \
        -o "$OUTB/grub/$name-$size.pf2" "$inter/$name.otf"
done

# Installer branding.
cal="$ROOTFS/etc/calamares/branding/aurora"
mkdir -p "$cal"
sed "s/@VERSION@/$AURORA_VERSION/g" "$SRC/branding/calamares/branding.desc" > "$cal/branding.desc"
cp "$SRC/branding/calamares/show.qml" "$SRC/branding/calamares/stylesheet.qss" "$cal/"
cp -r "$SRC/branding/calamares/slides" "$cal/"
python3 "$SRC/branding/logo.py" mark "$cal/logo.png" 128
python3 "$SRC/branding/logo.py" static "$cal/welcome.png" 360
