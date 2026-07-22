#!/bin/bash
# Apply the Aurora overlay, identity files and service configuration.
. "$(dirname "$0")/../lib.sh"

log "applying overlay"
rsync -a --no-owner --no-group "$SRC/overlay/" "$ROOTFS/"

# Take over files owned by base-files so upgrades don't restore Debian branding.
for f in /usr/lib/os-release /etc/issue /etc/issue.net; do
    if ! in_chroot dpkg-divert --list "$f" | grep -q aurora; then
        in_chroot dpkg-divert --package aurora-base --rename --add "$f"
    fi
done

# Hide Calamares' own launchers ("Install Debian", "Install System"); Aurora
# ships aurora-installer.desktop instead.
for f in /usr/share/applications/calamares-install-debian.desktop \
         /usr/share/applications/calamares.desktop \
         /etc/xdg/autostart/calamares-desktop-icon.desktop; do
    if [ -e "$ROOTFS$f" ] && ! in_chroot dpkg-divert --list "$f" | grep -q aurora; then
        in_chroot dpkg-divert --package aurora-base --divert "$f.aurora-hidden" --rename --add "$f"
    fi
done

cat > "$ROOTFS/usr/lib/os-release" <<EOF
PRETTY_NAME="$AURORA_NAME $AURORA_VERSION ($AURORA_CODENAME)"
NAME="$AURORA_NAME"
VERSION_ID="$AURORA_VERSION"
VERSION="$AURORA_VERSION ($AURORA_CODENAME)"
VERSION_CODENAME=$AURORA_CODENAME
DEBIAN_CODENAME=$DEBIAN_SUITE
ID=$AURORA_ID
ID_LIKE=debian
LOGO=aurora-logo
HOME_URL="$AURORA_HOME_URL"
EOF
ln -sf ../usr/lib/os-release "$ROOTFS/etc/os-release"

printf '%s %s \\n \\l\n\n' "$AURORA_NAME" "$AURORA_VERSION" > "$ROOTFS/etc/issue"
printf '%s %s\n' "$AURORA_NAME" "$AURORA_VERSION" > "$ROOTFS/etc/issue.net"

cat > "$ROOTFS/etc/lsb-release" <<EOF
DISTRIB_ID=Aurora
DISTRIB_RELEASE=$AURORA_VERSION
DISTRIB_CODENAME=$AURORA_CODENAME
DISTRIB_DESCRIPTION="$AURORA_NAME $AURORA_VERSION"
EOF

mkdir -p "$ROOTFS/etc/aurora"
printf 'LIVE_USER=%s\n' "$LIVE_USER" > "$ROOTFS/etc/aurora/live.conf"

echo "$LIVE_HOSTNAME" > "$ROOTFS/etc/hostname"
cat > "$ROOTFS/etc/hosts" <<EOF
127.0.0.1	localhost
127.0.1.1	$LIVE_HOSTNAME
::1		localhost ip6-localhost ip6-loopback
EOF

# Writable home for the login screen (runs as greetd's system user).
in_chroot install -d -o _greetd -g _greetd -m 700 /var/lib/aurora-greeter

log "enabling services"
in_chroot systemctl enable NetworkManager greetd aurora-live-setup
in_chroot systemctl set-default graphical.target

# Hide helper/terminal-only launchers (config/hidden-apps.list) with
# NoDisplay overrides in /usr/local/share, which XDG searches first.
mkdir -p "$ROOTFS/usr/local/share/applications"
sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/hidden-apps.list" | while read -r id; do
    src="$ROOTFS/usr/share/applications/$id"
    [ -f "$src" ] || continue
    sed '/^NoDisplay=/d; /^\[Desktop Entry\]/a NoDisplay=true' "$src" \
        > "$ROOTFS/usr/local/share/applications/$id"
done
