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
[ -d /cache/wallpapers ] && cp -r /cache/wallpapers /tmp/src/desktop/build/
make -s -C /tmp/src/desktop install DESTDIR=/ PREFIX=/opt/aurora WALLPAPER_SIZE="1920 1080" >/dev/null
mkdir -p /cache && cp -r /tmp/src/desktop/build/wallpapers /cache/ 2>/dev/null || true
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
    sed -e "s|^Name=.*|Name=$name|" "/usr/share/applications/$id" > ~/.local/share/applications/$id
    if [ "$icon" != "-" ]; then sed -i "s|^Icon=.*|Icon=$icon|" ~/.local/share/applications/$id; fi
done
cp -r /opt/aurora/share/themes/* /usr/share/themes/ 2>/dev/null || true

cat > /tmp/inner.sh <<EOF
set -x
wlr-randr --output HEADLESS-1 --custom-mode 1600x900 || true
aurora-shell > $out/shell.log 2>&1 &
sleep 4
${scenario:+bash $scenario}
sleep 1
grim $out/screen.png
labwc --exit
EOF

# Same compositor config as the real session, minus its autostart.
rm -rf /tmp/labwc && cp -r /opt/aurora/share/aurora/labwc /tmp/labwc && rm -f /tmp/labwc/autostart
timeout 600 dbus-run-session -- labwc -C /tmp/labwc -s "bash /tmp/inner.sh" > "$out/labwc.log" 2>&1 || true
echo "screenshot: $out/screen.png"
