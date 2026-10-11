#!/bin/bash
# Runs only as a disposable account inside the development container.
set -euo pipefail
if [ "${AURORA_MULTIUSER_TEST_CONTAINER:-}" != 1 ] || [ ! -e /.dockerenv ]; then
    echo 'Run only through the opted-in disposable development container.' >&2
    exit 2
fi
aurora-shell > "$XDG_RUNTIME_DIR/shell.log" 2>&1 &
for _ in $(seq 150); do
    test -e "$XDG_RUNTIME_DIR/aurora-shell.ready" && break
    sleep .1
done
test -e "$XDG_RUNTIME_DIR/aurora-shell.ready"
cp /usr/share/backgrounds/aurora/aurora-dynamic-dawn.png "$HOME/private-background.png"
gsettings set org.aurora.desktop wallpaper "$HOME/private-background.png"
gsettings get org.aurora.desktop wallpaper > "$XDG_RUNTIME_DIR/preference"
aurora-files > "$XDG_RUNTIME_DIR/files.log" 2>&1 &
python3 - <<'PY' &
import os, time
from pathlib import Path
from aurora import activities
ident = activities.create(os.environ['USER'] + ' private transfer', 'copy')
root = Path(os.environ['XDG_RUNTIME_DIR'])
(root / 'job.id').write_text(ident)
while not (root / 'end-job').exists():
    time.sleep(.1)
activities.update(ident, status='finished')
PY
for _ in $(seq 150); do
    test -e "$XDG_RUNTIME_DIR/job.id" && break
    sleep .1
done
gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.NameHasOwner org.aurora.Shell | grep -q true
touch "$XDG_RUNTIME_DIR/session-ready"
for _ in $(seq 300); do
    if test -e "$XDG_RUNTIME_DIR/logout-now"; then
        touch "$XDG_RUNTIME_DIR/end-job"
        aurora-shell logout
        exit 0
    fi
    sleep .1
done
exit 1
