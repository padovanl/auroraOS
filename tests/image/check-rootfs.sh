#!/bin/bash
# Checks on the built root filesystem and ISO. Runs in the builder container
# after a build (make test-image).
set -uo pipefail
. /src/build/lib.sh
set +e

fail=0
ok() { echo "ok: $*"; }
bad() { echo "FAILED: $*"; fail=1; }
expect() { local what=$1; shift; if "$@" >/dev/null 2>&1; then ok "$what"; else bad "$what"; fi; }

iso="$OUT/aurora-os-$AURORA_VERSION-$ARCH.iso"

echo "== identity"
expect "os-release ID=aurora" grep -qx 'ID=aurora' "$ROOTFS/usr/lib/os-release"
expect "os-release based on debian" grep -qx 'ID_LIKE=debian' "$ROOTFS/usr/lib/os-release"
expect "plymouth theme aurora" grep -q 'Theme=aurora' "$ROOTFS/etc/plymouth/plymouthd.conf"

echo "== required programs"
for bin in labwc greetd aurora-shell aurora-session aurora-settings aurora-files aurora-devhub \
           aurora-installer calamares portop git docker podman python3 node firefox-esr foot \
           nmcli ufw flatpak gnome-software timeshift; do
    expect "$bin" chroot "$ROOTFS" sh -c "command -v $bin"
done

echo "== services"
for unit in greetd NetworkManager ufw aurora-live-setup; do
    expect "$unit enabled" chroot "$ROOTFS" systemctl is-enabled "$unit"
done
expect "ssh disabled by default" sh -c "! chroot '$ROOTFS' systemctl is-enabled ssh.service"
expect "graphical target" sh -c "chroot '$ROOTFS' systemctl get-default | grep -q graphical"

echo "== desktop"
expect "gsettings schema compiled" test -f "$ROOTFS/usr/share/glib-2.0/schemas/gschemas.compiled"
expect "aurora schema installed" test -f "$ROOTFS/usr/share/glib-2.0/schemas/org.aurora.desktop.gschema.xml"
expect "wayland bindings generated" test -d "$ROOTFS/usr/lib/aurora/aurora/protocols/wlr_foreign_toplevel_management_unstable_v1"
expect "window themes" test -f "$ROOTFS/usr/share/themes/Aurora/openbox-3/close-active.svg"
expect "light window theme" test -f "$ROOTFS/usr/share/themes/Aurora-Light/openbox-3/themerc"
expect "GTK3 theme (adw-gtk3)" test -f "$ROOTFS/usr/share/themes/adw-gtk3-dark/gtk-3.0/gtk.css"
expect "Qt follows GNOME settings" chroot "$ROOTFS" dpkg -s qgnomeplatform-qt6
expect "plymouth hand-over for greetd" test -f "$ROOTFS/etc/systemd/system/greetd.service.d/aurora-plymouth.conf"
expect "wallpaper" test -f "$ROOTFS/usr/share/backgrounds/aurora/aurora-dawn.png"
expect "shell imports" chroot "$ROOTFS" env PYTHONDONTWRITEBYTECODE=1 python3 -c "import sys; sys.path.insert(0,'/usr/lib/aurora'); import aurora.shell.dock, aurora.settingsapp.app, aurora.files.app, aurora.devhub.app"

echo "== default apps (config/apps.manifest)"
while IFS='|' read -r cat name id launch; do
    id=$(echo $id); name=$(echo $name)
    local_f="$ROOTFS/usr/local/share/applications/$id"
    f="$ROOTFS/usr/share/applications/$id"
    [ -f "$local_f" ] && f="$local_f"
    if [ ! -f "$f" ]; then bad "$name: $id not installed"; continue; fi
    if grep -q '^NoDisplay=true' "$f"; then bad "$name: $id is hidden"; continue; fi
    exe=$(sed -n 's/^Exec=//p' "$f" | head -1 | sed 's/^env [^ ]* //' | awk '{print $1}')
    if chroot "$ROOTFS" env PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/usr/games sh -c "command -v '$exe'" >/dev/null 2>&1; then
        ok "$name"
    else
        bad "$name: '$exe' not found"
    fi
done < <(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/apps.manifest")
expect "Terminal launcher renamed" grep -qx 'Name=Terminal' "$ROOTFS/usr/local/share/applications/foot.desktop"

echo "== installer"
expect "calamares branding" test -f "$ROOTFS/etc/calamares/branding/aurora/branding.desc"
expect "branding logo rendered" test -s "$ROOTFS/etc/calamares/branding/aurora/logo.png"
expect "aurora-finalize module" test -f "$ROOTFS/usr/lib/calamares/modules/aurora-finalize/main.py"
expect "Install Debian launcher hidden" test ! -e "$ROOTFS/usr/share/applications/calamares-install-debian.desktop"

echo "== cleanliness"
expect "no policy-rc.d left" test ! -e "$ROOTFS/usr/sbin/policy-rc.d"
expect "empty machine-id" test ! -s "$ROOTFS/etc/machine-id"
expect "no live user baked in" sh -c "! grep -q '^$LIVE_USER:' '$ROOTFS/etc/passwd'"

echo "== iso"
expect "iso exists" test -s "$iso"
expect "iso smaller than 4 GiB" test "$(stat -c %s "$iso")" -lt 4294967296
report=$(xorriso -indev "$iso" -report_el_torito plain 2>/dev/null)
expect "BIOS boot entry" grep -q "BIOS" <<<"$report"
expect "UEFI boot entry" grep -q "UEFI" <<<"$report"
listing=$(xorriso -indev "$iso" -find / -type f 2>/dev/null)
for f in /live/vmlinuz /live/initrd.img /live/filesystem.squashfs /boot/grub/grub.cfg \
         "/dists/$DEBIAN_SUITE/main/binary-$ARCH/Packages"; do
    expect "iso contains $f" grep -q "'$f'" <<<"$listing"
done
extract() {  # extract ISO_PATH → prints the file
    local tmp; tmp=$(mktemp)
    rm -f "$tmp"
    xorriso -indev "$iso" -osirrox on -extract "$1" "$tmp" >/dev/null 2>&1
    cat "$tmp" 2>/dev/null
    rm -f "$tmp"
}
cfg=$(extract /boot/grub/grub.cfg)
expect "grub Try entry" grep -q 'menuentry "Try ' <<<"$cfg"
expect "grub Install entry" grep -q 'aurora.install' <<<"$cfg"
pkgs=$(extract "/dists/$DEBIAN_SUITE/main/binary-$ARCH/Packages")
for p in grub-pc grub-efi-amd64 shim-signed cryptsetup-initramfs; do
    expect "pool has $p" grep -qx "Package: $p" <<<"$pkgs"
done

echo
[ $fail -eq 0 ] && echo "IMAGE CHECKS PASSED" || echo "IMAGE CHECKS FAILED"
exit $fail
