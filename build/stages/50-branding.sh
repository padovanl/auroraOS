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
sed -e "s/@AURORA_NAME@/$AURORA_NAME/g" -e "s/@AURORA_VERSION@/$AURORA_VERSION/g" \
    "$SRC/branding/grub/theme.txt" > "$OUTB/grub/theme.txt"
# BIOS has no "UEFI firmware settings" entry: a card one row (52 px) shorter.
sed 's/^    height = 392$/    height = 340/' "$OUTB/grub/theme.txt" > "$OUTB/grub/theme-bios.txt"
grep -q 'height = 340' "$OUTB/grub/theme-bios.txt" || die "theme-bios.txt: menu height not found"
inter="$ROOTFS/usr/share/fonts/opentype/inter"
for spec in "Inter-Regular:16" "Inter-Regular:18" "Inter-SemiBold:18" "Inter-SemiBold:30"; do
    name=${spec%%:*} size=${spec##*:}
    # Latin, punctuation (· – …) and the arrows of the key hints.
    # grub-mkfont names every weight "Inter Regular N": give SemiBold its own
    # family, so the theme can ask for "Inter SemiBold Regular N".
    family="Inter"; [ "$name" = Inter-SemiBold ] && family="Inter SemiBold"
    grub-mkfont -n "$family" -s "$size" -r 0x20-0x7E,0xA0-0x17F,0x2010-0x2027,0x2190-0x2193 \
        -o "$OUTB/grub/$name-$size.pf2" "$inter/$name.otf"
done

# Installer branding.
cal="$ROOTFS/etc/calamares/branding/aurora"
mkdir -p "$cal"
sed "s/@VERSION@/$AURORA_VERSION/g" "$SRC/branding/calamares/branding.desc" > "$cal/branding.desc"
cp "$SRC/branding/calamares/show.qml" "$SRC/branding/calamares/keyboardq.qml" \
   "$SRC/branding/calamares/stylesheet.qss" "$cal/"
cp "$SRC"/branding/calamares/*.svg "$cal/"
cp "$OUTB"/calamares/*.png "$cal/"
cp -r "$SRC/branding/calamares/slides" "$cal/"
python3 "$SRC/branding/logo.py" mark "$cal/logo.png" 128
python3 "$SRC/branding/logo.py" static "$cal/welcome.png" 360
