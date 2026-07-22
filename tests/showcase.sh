#!/bin/bash
# Screenshot scenario for the website and README (make screenshots).
# Runs inside the headless session like tests/smoke.sh.
set -u
out=/out/showcase
mkdir -p "$out"
shot() { sleep "${2:-1.5}"; grim "$out/$1.png"; }
key() { wlrctl keyboard type "$1"; }

aurora-look >/dev/null 2>&1
mkdir -p ~/Documents/Projects ~/Downloads ~/Music ~/Pictures/Screenshots ~/Videos ~/Desktop
xdg-user-dirs-update >/dev/null 2>&1 || true
touch ~/Documents/notes.md ~/Documents/budget.ods ~/Documents/Projects/README.md

# Desktop with Files open and a notification.
aurora-files >/dev/null 2>&1 &
sleep 3
notify-send -a "Aurora" -i software-update-available "Updates installed" \
    "Security updates were installed in the background. No restart needed."
shot desktop 2

# Spotlight: apps and settings, then math.
aurora-shell search "disp"; shot spotlight-search
aurora-shell search "12*(3+4)/2"; shot spotlight-math
aurora-shell launcher spotlight

# Launchpad.
aurora-shell launcher grid; shot launchpad
aurora-shell launcher grid

# Control Center.
aurora-shell quick-settings; shot control-center
wlrctl keyboard type " " >/dev/null 2>&1; sleep 0.3
pkill -f aurora-files

# Settings and Dev Hub.
aurora-settings --page desktop >/dev/null 2>&1 & shot settings-desktop 4
aurora-settings --page appearance >/dev/null 2>&1; shot settings-appearance
aurora-settings --page keyboard >/dev/null 2>&1; shot settings-keyboard
pkill -f aurora-settings
aurora-devhub >/dev/null 2>&1 & shot devhub 4
pkill -f aurora-devhub

# Other layouts.
aurora-files >/dev/null 2>&1 &
sleep 2
for layout in studio classic minimal; do
    python3 - "$layout" <<'EOF'
import sys
sys.path.insert(0, "/opt/aurora/lib/aurora")
from aurora import settings
from aurora.settingsapp.desktop import PRESETS
s = settings.get()
for k, v in PRESETS[sys.argv[1]]["values"].items():
    if isinstance(v, bool): s.set_boolean(k, v)
    elif isinstance(v, int): s.set_int(k, v)
    elif isinstance(v, float): s.set_double(k, v)
    else: s.set_string(k, v)
EOF
    aurora-look >/dev/null 2>&1
    shot "layout-$layout" 3
done
