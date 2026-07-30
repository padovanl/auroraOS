#!/bin/bash
# Desktop smoke test, run as a scenario inside the headless session
# (desktop/dev/run-headless.sh tests/smoke.sh). Starts every Aurora app,
# takes a screenshot of each and fails on any Python traceback.
set -u
out=/out
mkdir -p "$out/smoke"
fail=0

aurora-look >/dev/null 2>&1

# A tray app and a file on the desktop, to exercise the tray and desktop icons.
python3 /src/tests/fake-tray-item.py > "$out/smoke/tray.log" 2>&1 &
mkdir -p ~/Desktop && echo hello > ~/Desktop/notes.txt
for _i in $(seq 20); do grep -q registered "$out/smoke/tray.log" && break; sleep 0.5; done
sleep 1
grim "$out/smoke/tray.png"
grep -q registered "$out/smoke/tray.log" || { echo "FAILED: tray item did not register"; fail=1; }

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
    timeout 15 aurora-settings --page "$page" >>"$out/smoke/settings.log" 2>&1 ||
        echo "timeout or error opening page $page" >>"$out/smoke/settings.log"
    sleep 1.5
    grim "$out/smoke/settings-$page.png"
done
if grep -q "Traceback" "$out/smoke/settings.log"; then
    echo "FAILED: a settings page raised an exception"; fail=1
    sed -n '/Traceback/,$p' "$out/smoke/settings.log" | head -30
else
    echo "ok: settings pages"
fi

timeout 10 aurora-shell launcher spotlight; sleep 1; grim "$out/smoke/spotlight.png"
aurora-shell launcher spotlight
aurora-shell launcher grid; sleep 1; grim "$out/smoke/launchpad.png"
aurora-shell launcher grid

# Spotlight extras: unit conversion, emoji, clipboard history, projects.
mkdir -p ~/git/aurora-demo/.git && echo "ref: refs/heads/main" > ~/git/aurora-demo/.git/HEAD
printf 'ssh-keygen -t ed25519' | wl-copy; sleep 1
for q in "10 km in mi" ":rocket" "clip:" "aurora-demo"; do
    name=$(echo "$q" | tr -c 'a-z0-9' '-' | sed 's/-*$//; s/^-*//')
    aurora-shell search "$q"; sleep 1.5; grim "$out/smoke/spotlight-${name:-x}.png"
done
aurora-shell launcher spotlight
[ -s ~/.local/share/aurora/clipboard.json ] && echo "ok: clipboard history" ||
    { echo "FAILED: clipboard history is empty"; fail=1; }

# Quick Look on a picture, source code and a PDF.
python3 - <<'PY'
import cairo
s = cairo.PDFSurface("/tmp/sample.pdf", 595, 842)
c = cairo.Context(s); c.set_font_size(32); c.move_to(60, 120); c.show_text("Aurora OS")
c.set_font_size(14); c.move_to(60, 160); c.show_text("Quick Look renders PDF pages.")
s.finish()
PY
cp /src/desktop/aurora/sun.py /tmp/sample.py
launch quicklook-code aurora-quicklook /tmp/sample.py
pkill -f aurora-quicklook
launch quicklook-pdf aurora-quicklook /tmp/sample.pdf
pkill -f aurora-quicklook
launch quicklook-image aurora-quicklook /usr/share/backgrounds/aurora/aurora-dynamic-dusk.png
pkill -f aurora-quicklook

# Overview with a couple of windows open.
aurora-files >/dev/null 2>&1 &
gnome-text-editor >/dev/null 2>&1 &
sleep 4
aurora-shell overview; sleep 2; grim "$out/smoke/overview.png"
aurora-shell overview
pkill -f aurora-files; pkill -f gnome-text-editor

if grep -q "Traceback" "$out/shell.log"; then
    echo "FAILED: shell raised an exception"; fail=1
    sed -n '/Traceback/,$p' "$out/shell.log" | head -30
fi
pgrep -f aurora-shell >/dev/null || { echo "FAILED: shell is not running"; fail=1; }

echo "$fail" > "$out/smoke/result"
