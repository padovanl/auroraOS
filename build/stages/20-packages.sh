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

# Rewritten every build so component changes in aurora.conf take effect.
write_sources

log "apt update + upgrade"
in_chroot apt-get update
in_chroot apt-get -y full-upgrade

LOCALES=$(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SRC/config/locales.list")

firefox_l10n=$(awk -F'|' '{gsub(/ /,"",$3); if ($3 != "-") print "firefox-esr-l10n-" $3}' <<<"$LOCALES")
# LibreOffice uses the same codes except for a few regional variants.
lo_l10n=$(awk -F'|' '{gsub(/ /,"",$3); if ($3 != "-") print $3}' <<<"$LOCALES" |
    sed -e 's/^es-es$/es/' -e 's/^sv-se$/sv/' -e 's/^hi-in$/hi/' -e 's/^pt-pt$/pt/' | sed 's/^/libreoffice-l10n-/')

tb_l10n=$(awk -F'|' '{gsub(/ /,"",$3); if ($3 != "-") print "thunderbird-l10n-" $3}' <<<"$LOCALES")

# Translation packages don't exist for every language: keep the ones that do.
available() {
    for p in "$@"; do
        if in_chroot apt-cache show "$p" >/dev/null 2>&1; then echo "$p"; fi
    done
}
# shellcheck disable=SC2086
l10n=$(available $firefox_l10n $lo_l10n $tb_l10n)

log "installing package lists"
# shellcheck disable=SC2046,SC2086
apt_install $(read_list "$SRC"/config/packages/*.list) $l10n

log "generating locales"
: > "$ROOTFS/etc/locale.gen"
awk -F'|' '{gsub(/ /,"",$1); print $1}' <<<"$LOCALES" | while read -r loc; do
    grep -E "^${loc//./\\.} " "$ROOTFS/usr/share/i18n/SUPPORTED" >> "$ROOTFS/etc/locale.gen" \
        || die "locale $loc not found in SUPPORTED"
done
in_chroot locale-gen
printf 'LANG=%s\n' "$DEFAULT_LOCALE" > "$ROOTFS/etc/default/locale"
