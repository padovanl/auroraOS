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

# The same look for the installed system's boot menu, in the root file system
# (GRUB reads it there, like the kernel). Its menu has up to five entries:
# Aurora, Advanced options, Windows (or another system), UEFI firmware
# settings, snapshots: logo and card sit higher, rows closer, a card for five
# that scrolls when there are more, above the key hints on a 768-pixel screen;
# wider, for "Aurora GNU/Linux, with Linux 6.12.… (recovery mode)" whole.
installed="$ROOTFS/usr/share/grub/themes/aurora"
rm -rf "$installed"
mkdir -p "$installed"
cp -r "$OUTB/grub/." "$installed/"
rm -f "$installed/theme.txt" "$installed/theme-bios.txt"
sed -e 's/^    top = 9%$/    top = 6%/' \
    -e 's/^    top = 9%+124$/    top = 6%+124/' \
    -e 's/^    top = 9%+170$/    top = 6%+170/' \
    -e 's/^    top = 9%+212$/    top = 6%+208/' \
    -e 's/^    item_spacing = 22$/    item_spacing = 12/' \
    -e 's/^    left = 50%-290$/    left = 50%-390/' \
    -e 's/^    width = 580$/    width = 780/' \
    -e 's/^    height = 392$/    height = 300/' \
    -e 's/^    scrollbar = false$/    scrollbar = true/' \
    -e 's/Choose how to start/Choose a system/' \
    "$OUTB/grub/theme.txt" > "$installed/theme.txt"
# BIOS: no firmware settings entry, one row (42 px) less.
sed 's/^    height = 300$/    height = 258/' "$installed/theme.txt" > "$installed/theme-bios.txt"
for want in 'top = 6%+208' 'item_spacing = 12' 'height = 300' 'width = 780'; do
    grep -q "$want" "$installed/theme.txt" || die "installed GRUB theme: '$want' not applied"
done
grep -q 'height = 258' "$installed/theme-bios.txt" || die "installed GRUB theme: BIOS height not applied"

# Installer branding.
cal="$ROOTFS/etc/calamares/branding/aurora"
mkdir -p "$cal"
sed "s/@VERSION@/$AURORA_VERSION/g" "$SRC/branding/calamares/branding.desc" > "$cal/branding.desc"
cp "$SRC/branding/calamares/show.qml" "$SRC/branding/calamares/keyboardq.qml" \
   "$SRC/branding/calamares/calamares-sidebar.qml" \
   "$SRC/branding/calamares/stylesheet.qss" "$cal/"
cp "$SRC"/branding/calamares/*.svg "$cal/"
cp "$OUTB"/calamares/*.png "$cal/"
cp -r "$SRC/branding/calamares/slides" "$cal/"
python3 "$SRC/branding/logo.py" mark "$cal/logo.png" 128
python3 "$SRC/branding/logo.py" static "$cal/welcome.png" 360

style_build="$OUTB/installer-style"
mkdir -p "$style_build"
qmake6 "$SRC/branding/calamares/progress-style/progress-style.pro" -o "$style_build/Makefile"
make -C "$style_build" -j"$(nproc)"
style_plugins="$ROOTFS/usr/lib/aurora/qt6/styles"
mkdir -p "$style_plugins"
cp "$style_build/libaurora-installer-style.so" "$style_plugins/"
