#!/bin/bash
# Desktop smoke test, run as a scenario inside the headless session
# (desktop/dev/run-headless.sh tests/smoke.sh). Starts every Aurora app,
# takes a screenshot of each and fails on any Python traceback.
set -u
out=/out
mkdir -p "$out/smoke"
fail=0

aurora-look >/dev/null 2>&1

launch() {  # launch NAME COMMAND...
    local name=$1; shift
    "$@" >"$out/smoke/$name.log" 2>&1 &
    sleep 4
    grim "$out/smoke/$name.png"
    if grep -q "Traceback" "$out/smoke/$name.log"; then
        echo "FAILED: $name raised an exception"; fail=1
        sed -n '/Traceback/,$p' "$out/smoke/$name.log" | head -30
    else
        echo "ok: $name"
    fi
}

launch files aurora-files
launch devhub aurora-devhub
launch welcome aurora-welcome
launch settings aurora-settings
for page in network bluetooth display sound power appearance desktop multitasking \
            notifications apps mouse keyboard printers accessibility privacy sharing \
            users language datetime updates about; do
    aurora-settings --page "$page" >>"$out/smoke/settings.log" 2>&1
    sleep 1.5
    grim "$out/smoke/settings-$page.png"
done
if grep -q "Traceback" "$out/smoke/settings.log"; then
    echo "FAILED: a settings page raised an exception"; fail=1
    sed -n '/Traceback/,$p' "$out/smoke/settings.log" | head -30
else
    echo "ok: settings pages"
fi

aurora-shell launcher spotlight; sleep 1; grim "$out/smoke/spotlight.png"
aurora-shell launcher spotlight
aurora-shell launcher grid; sleep 1; grim "$out/smoke/launchpad.png"
aurora-shell launcher grid

if grep -q "Traceback" "$out/shell.log"; then
    echo "FAILED: shell raised an exception"; fail=1
    sed -n '/Traceback/,$p' "$out/shell.log" | head -30
fi
pgrep -f aurora-shell >/dev/null || { echo "FAILED: shell is not running"; fail=1; }

echo "$fail" > "$out/smoke/result"
