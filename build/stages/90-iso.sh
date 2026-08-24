#!/bin/bash
# Pack the rootfs into squashfs and master a hybrid BIOS/UEFI ISO.
. "$(dirname "$0")/../lib.sh"

umount_chroot

rm -rf "$ISODIR"
mkdir -p "$ISODIR/live" "$ISODIR/boot/grub" "$OUT"

kernel=$(ls "$ROOTFS"/boot/vmlinuz-* | sort -V | tail -1)
initrd=$(ls "$ROOTFS"/boot/initrd.img-* | sort -V | tail -1)
cp "$kernel" "$ISODIR/live/vmlinuz"
cp "$initrd" "$ISODIR/live/initrd.img"
touch "$ISODIR/.aurora-live"

log "creating squashfs ($SQUASHFS_COMP)"
mksquashfs "$ROOTFS" "$ISODIR/live/filesystem.squashfs" \
    -comp "$SQUASHFS_COMP" -noappend -quiet -progress \
    -e boot/vmlinuz-\* boot/initrd.img-\* .aurora-bootstrapped

du -sx --block-size=1 "$ROOTFS" | cut -f1 > "$ISODIR/live/filesystem.size"

# Offline apt repository used by the installer (see stages/70-pool.sh).
if [ -d "$WORK/pool" ]; then
    log "writing package pool"
    mkdir -p "$ISODIR/pool/main" "$ISODIR/dists/$DEBIAN_SUITE/main/binary-$ARCH"
    cp "$WORK"/pool/*.deb "$ISODIR/pool/main/"
    (cd "$ISODIR" && apt-ftparchive packages pool/main > "dists/$DEBIAN_SUITE/main/binary-$ARCH/Packages")
    gzip -k9 "$ISODIR/dists/$DEBIAN_SUITE/main/binary-$ARCH/Packages"
    apt-ftparchive -o APT::FTPArchive::Release::Suite="$DEBIAN_SUITE" \
        -o APT::FTPArchive::Release::Codename="$DEBIAN_SUITE" \
        -o APT::FTPArchive::Release::Components=main \
        -o APT::FTPArchive::Release::Architectures="$ARCH" \
        release "$ISODIR/dists/$DEBIAN_SUITE" > "$WORK/Release"
    mv "$WORK/Release" "$ISODIR/dists/$DEBIAN_SUITE/Release"
fi

log "writing grub.cfg"
if [ -f "$WORK/branding/grub/theme.txt" ]; then
    mkdir -p "$ISODIR/boot/grub/themes/aurora"
    cp -r "$WORK/branding/grub/." "$ISODIR/boot/grub/themes/aurora/"
fi

BOOT="boot=live quiet splash"
{
    cat <<EOF
set default=0
set timeout=8

insmod all_video
insmod gfxterm
insmod png
loadfont unicode
set gfxmode=1920x1080,1600x900,1280x720,1024x768,auto
terminal_output gfxterm
if [ -f /boot/grub/themes/aurora/theme.txt ]; then
$(for f in "$WORK"/branding/grub/*.pf2; do echo "    loadfont /boot/grub/themes/aurora/$(basename "$f")"; done)
    if [ "\$grub_platform" = "efi" ]; then
        set theme=/boot/grub/themes/aurora/theme.txt
    else
        set theme=/boot/grub/themes/aurora/theme-bios.txt
    fi
fi

search --no-floppy --file --set=root /.aurora-live

menuentry "Try $AURORA_NAME" --class try {
    linux /live/vmlinuz $BOOT
    initrd /live/initrd.img
}
menuentry "Install $AURORA_NAME" --class install {
    linux /live/vmlinuz $BOOT aurora.install
    initrd /live/initrd.img
}
menuentry "Try $AURORA_NAME (safe graphics)" --class safe {
    linux /live/vmlinuz $BOOT nomodeset
    initrd /live/initrd.img
}
submenu "Language  ·  Lingua  ·  Sprache  ·  Idioma" --class language {
EOF
    sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/locales.list" |
    while IFS='|' read -r loc kbd _ name; do
        loc=$(echo $loc); kbd=$(echo $kbd); name=$(echo $name)
        cat <<EOF
    menuentry "$name" --class language {
        linux /live/vmlinuz $BOOT aurora.lang=$loc aurora.kbd=$kbd
        initrd /live/initrd.img
    }
EOF
    done
    cat <<EOF
}
menuentry "Boot from hard disk" --class disk {
    set root=(hd0)
    chainloader +1
}
if [ "\$grub_platform" = "efi" ]; then
    menuentry "UEFI firmware settings" --class firmware {
        fwsetup
    }
fi
EOF
} > "$ISODIR/boot/grub/grub.cfg"

iso="$OUT/aurora-os-$AURORA_VERSION-$ARCH.iso"
log "mastering $iso"
grub-mkrescue -o "$iso" "$ISODIR" -- -volid "$ISO_LABEL" 2>&1 | grep -v '^xorriso : UPDATE' || true
[ -s "$iso" ] || die "ISO was not created"
( cd "$OUT" && sha256sum "$(basename "$iso")" > "$(basename "$iso").sha256" )
log "done: $iso ($(du -h "$iso" | cut -f1))"
