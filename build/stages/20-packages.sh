#!/bin/bash
# Install the package sets and generate locales.
. "$(dirname "$0")/../lib.sh"

# Never start services while building the image.
printf '#!/bin/sh\nexit 101\n' > "$ROOTFS/usr/sbin/policy-rc.d"
chmod +x "$ROOTFS/usr/sbin/policy-rc.d"

# Preseed answers that would otherwise prompt.
in_chroot debconf-set-selections <<EOF
keyboard-configuration keyboard-configuration/layoutcode string $DEFAULT_KEYMAP
locales locales/default_environment_locale select $DEFAULT_LOCALE
EOF

log "apt update + upgrade"
in_chroot apt-get update
in_chroot apt-get -y full-upgrade

LOCALES=$(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/locales.list")

firefox_l10n=$(awk -F'|' '{gsub(/ /,"",$3); if ($3 != "-") print "firefox-esr-l10n-" $3}' <<<"$LOCALES")

log "installing package lists"
# shellcheck disable=SC2046
apt_install $(read_list "$SRC"/config/packages/*.list) $firefox_l10n

log "generating locales"
: > "$ROOTFS/etc/locale.gen"
awk -F'|' '{gsub(/ /,"",$1); print $1}' <<<"$LOCALES" | while read -r loc; do
    grep -E "^${loc//./\\.} " "$ROOTFS/usr/share/i18n/SUPPORTED" >> "$ROOTFS/etc/locale.gen" \
        || die "locale $loc not found in SUPPORTED"
done
in_chroot locale-gen
printf 'LANG=%s\n' "$DEFAULT_LOCALE" > "$ROOTFS/etc/default/locale"
