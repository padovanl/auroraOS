#!/bin/bash
# Runs inside the dev container: installs the desktop into /opt/aurora, starts a
# headless labwc session with the shell, runs the given scenario, screenshots.
# Usage: session.sh SCENARIO_SCRIPT OUTPUT_DIR
set -euo pipefail

scenario="${1:-}"
out="${2:-/out}"
mkdir -p "$out"

# Install into a private prefix from a writable copy of the sources.
rsync -a --exclude /desktop/build /src/desktop /src/branding /tmp/src/
mkdir -p /tmp/src/desktop/build
# -p keeps timestamps, so make re-renders when the generator is newer.
[ -d /cache/wallpapers ] && cp -rp /cache/wallpapers /tmp/src/desktop/build/
make -s -C /tmp/src/desktop install DESTDIR=/ PREFIX=/opt/aurora WALLPAPER_SIZE="1920 1080" >/dev/null
mkdir -p /cache && rm -rf /cache/wallpapers && cp -rp /tmp/src/desktop/build/wallpapers /cache/ 2>/dev/null || true
ln -sfn /opt/aurora/share/backgrounds/aurora /usr/share/backgrounds/aurora 2>/dev/null || {
    mkdir -p /usr/share/backgrounds && ln -sfn /opt/aurora/share/backgrounds/aurora /usr/share/backgrounds/aurora; }
glib-compile-schemas /opt/aurora/share/glib-2.0/schemas

export PATH="/opt/aurora/bin:$PATH"
export AURORA_PREFIX=/opt/aurora AURORA_LIBDIR=/opt/aurora/lib/aurora
export XDG_DATA_DIRS="/opt/aurora/share:/usr/local/share:/usr/share"
export GSETTINGS_SCHEMA_DIR=/opt/aurora/share/glib-2.0/schemas
export XDG_RUNTIME_DIR=/tmp/xdg && mkdir -p -m 700 $XDG_RUNTIME_DIR
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 WLR_HEADLESS_OUTPUTS=1
export GSK_RENDERER=cairo
export XDG_CURRENT_DESKTOP=Aurora:wlroots
# No portal service in the container: tell libadwaita the scheme directly.
export ADW_DEBUG_COLOR_SCHEME=prefer-dark ADW_DEBUG_ACCENT_COLOR=purple
# Hide the same helper launchers as the image does.
mkdir -p ~/.local/share/applications
sed -e 's/#.*//' -e '/^[[:space:]]*$/d' /src/config/hidden-apps.list | while read -r id; do
    for d in /usr/share/applications /opt/aurora/share/applications; do
        if [ -f "$d/$id" ]; then
            sed '/^\[Desktop Entry\]/a NoDisplay=true' "$d/$id" > ~/.local/share/applications/$id
        fi
    done
done
printf '[Desktop Entry]\nType=Application\nName=x\nNoDisplay=true\n' > ~/.local/share/applications/mousepad-settings.desktop
# ...and rename the same launchers.
sed -e 's/#.*//' -e '/^[[:space:]]*$/d' /src/config/renamed-apps.list | while IFS='|' read -r id name icon; do
    id=$(echo $id); name=$(echo $name); icon=$(echo $icon)
    [ -f "/usr/share/applications/$id" ] || continue
    sed -e "/^\[Desktop Entry\]/,/^\[/ s|^Name=.*|Name=$name|" "/usr/share/applications/$id" > ~/.local/share/applications/$id
    if [ "$icon" != "-" ]; then sed -i "/^\[Desktop Entry\]/,/^\[/ s|^Icon=.*|Icon=$icon|" ~/.local/share/applications/$id; fi
done
cp -r /opt/aurora/share/themes/* /usr/share/themes/ 2>/dev/null || true

cat > /tmp/inner.sh <<EOF
set -x
wlr-randr --output HEADLESS-1 --custom-mode 1600x900 || true
aurora-shell > $out/shell.log 2>&1 &
sleep 4
if [ "${AURORA_RELOGIN_TEST:-}" = 1 ]; then
    for i in \$(seq 600); do
        test -e "\$XDG_RUNTIME_DIR/aurora-shell.ready" && break
        sleep .1
    done
    if ! test -e "\$XDG_RUNTIME_DIR/aurora-shell.ready"; then
        echo FIRST_LOGIN_FAILED > $out/logout-result
        labwc --exit
        exit 1
    fi
fi
scenario_status=0
${scenario:+bash $scenario || scenario_status=\$?}
sleep 1
grim $out/screen.png
echo \$scenario_status > $out/scenario-result
labwc --exit
EOF

# Same compositor config as the real session, minus its autostart.
rm -rf /tmp/labwc && cp -r /opt/aurora/share/aurora/labwc /tmp/labwc && rm -f /tmp/labwc/autostart
if [ "${AURORA_RELOGIN_TEST:-}" = 1 ]; then
    cat > /tmp/second.sh <<'EOF'
aurora-shell > /out/second-shell.log 2>&1 &
for i in $(seq 100); do
    test -e "$XDG_RUNTIME_DIR/aurora-shell.ready" && break
    sleep .1
done
test -e "$XDG_RUNTIME_DIR/aurora-shell.ready" && echo RELOGIN_OK > /out/logout-result
labwc --exit
EOF
    # Both compositors must use the same session bus: a stale Shell owner is
    # exactly what would make the second login return a black desktop.
    timeout 600 dbus-run-session -- bash -c '
        labwc -C /tmp/labwc -s "bash /tmp/inner.sh"
        if [ -e /out/logout-result ]; then exit 1; fi
        rm -f "$XDG_RUNTIME_DIR/aurora-logging-out" "$XDG_RUNTIME_DIR/aurora-shell.ready"
        labwc -C /tmp/labwc -s "bash /tmp/second.sh"
    ' > "$out/labwc.log" 2>&1 || true
else
    timeout 600 dbus-run-session -- labwc -C /tmp/labwc -s "bash /tmp/inner.sh" > "$out/labwc.log" 2>&1 || true
fi
echo "screenshot: $out/screen.png"
if [ -n "$scenario" ]; then
    test -f "$out/scenario-result"
    test "$(cat "$out/scenario-result")" = 0
fi
