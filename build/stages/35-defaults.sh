#!/bin/bash
# System-wide defaults for the features Aurora turns on out of the box.
. "$(dirname "$0")/../lib.sh"

log "firewall on (deny incoming, allow outgoing)"
sed -i 's/^ENABLED=.*/ENABLED=yes/' "$ROOTFS/etc/ufw/ufw.conf"
in_chroot systemctl enable ufw

log "automatic security updates"
cat > "$ROOTFS/etc/apt/apt.conf.d/20auto-upgrades" <<EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

log "flathub"
in_chroot flatpak remote-add --system --if-not-exists flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo || log "warning: could not add flathub"

# Docker starts on first use instead of at every boot.
in_chroot systemctl disable docker.service containerd.service 2>/dev/null || true
in_chroot systemctl enable docker.socket 2>/dev/null || true

# Interactive shell niceties for every user (see overlay/etc/aurora/bashrc).
if ! grep -q aurora/bashrc "$ROOTFS/etc/bash.bashrc"; then
    printf '\n# Aurora OS shell setup\n[ -r /etc/aurora/bashrc ] && . /etc/aurora/bashrc\n' \
        >> "$ROOTFS/etc/bash.bashrc"
fi

# SSH server is installed but off; Settings → Sharing turns it on.
in_chroot systemctl disable ssh.service ssh.socket 2>/dev/null || true
