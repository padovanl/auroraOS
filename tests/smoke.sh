#!/bin/bash
# Desktop smoke test, run as a scenario inside the headless session
# (desktop/dev/run-headless.sh tests/smoke.sh). Starts every Aurora app,
# takes a screenshot of each and fails on any Python traceback.
set -u
out=/out
rm -rf "$out/smoke"
mkdir -p "$out/smoke"
fail=0

aurora-look >/dev/null 2>&1

# A tray app and a file on the desktop, to exercise the tray and desktop icons.
# The headless shell may still be registering its D-Bus watcher after the
# fixed startup sleep; launch the item only once that service is available.
for _i in $(seq 30); do
    gdbus introspect --session --dest org.kde.StatusNotifierWatcher \
        --object-path /StatusNotifierWatcher >/dev/null 2>&1 && break
    sleep 0.5
done
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
launch gamehub aurora-gamehub
pkill -f aurora-gamehub
launch assistant-off aurora-assistant
pkill -f aurora-assistant
launch devhub aurora-devhub
if PYTHONPATH=/src/desktop python3 /src/tests/devhub-install-dialog.py \
        >"$out/smoke/devhub-install-dialog.log" 2>&1; then
    echo "ok: Dev Hub install dialog"
else
    echo "FAILED: Dev Hub install dialog"; fail=1
    tail -30 "$out/smoke/devhub-install-dialog.log"
fi
launch welcome aurora-welcome
launch settings aurora-settings
for page in network bluetooth display sound power appearance desktop multitasking \
            notifications apps mouse keyboard printers accessibility privacy sharing \
            users language datetime updates ai health about; do
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

# Aurora AI against a fake OpenAI-compatible server: the Assistant streams an
# answer, and the Writing Tools open on the selected text.
python3 - >"$out/smoke/fake-llm.log" 2>&1 <<'PY' &
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        answer = "To see what uses space, run:\n```bash\ndu -sh ~/* | sort -h\n```\nThe biggest folders are listed last."
        for i in range(0, len(answer), 12):
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": answer[i:i+12]}}]}) + "\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")
HTTPServer(("127.0.0.1", 47699), H).serve_forever()
PY
gsettings set org.aurora.desktop ai-provider openai
gsettings set org.aurora.desktop ai-openai-url http://127.0.0.1:47699/v1
gsettings set org.aurora.desktop ai-openai-model fake
gsettings set org.aurora.desktop ai-enabled true
sleep 1
aurora-assistant --ask "What uses the space on my disk?" >"$out/smoke/assistant.log" 2>&1 &
sleep 5; grim "$out/smoke/assistant.png"
pkill -f aurora-assistant
printf 'Their going to the meeting tomorow, we should prepare the slides.' | wl-copy --primary
aurora-assistant --writing >"$out/smoke/writing.log" 2>&1 &
sleep 4; grim "$out/smoke/writing-tools.png"
pkill -f aurora-assistant
for f in assistant writing; do
    if grep -q Traceback "$out/smoke/$f.log"; then
        echo "FAILED: $f raised an exception"; fail=1; sed -n '/Traceback/,$p' "$out/smoke/$f.log" | head -20
    else
        echo "ok: $f"
    fi
done
# Chat follows the reply to the bottom; attachments reach a local model only.
if PYTHONPATH=/src/desktop python3 -X faulthandler /src/tests/assistant-interactions.py \
        >"$out/smoke/assistant-interactions.log" 2>&1; then
    echo "ok: assistant interactions"
else
    echo "FAILED: assistant interactions"; fail=1; tail -20 "$out/smoke/assistant-interactions.log"
fi
gsettings reset org.aurora.desktop ai-provider; gsettings reset org.aurora.desktop ai-openai-url
aurora-shell search "? how do I free disk space"; sleep 1.5; grim "$out/smoke/spotlight-ask.png"
aurora-shell launcher spotlight

# These tests require a real GDK display.  The unit-test container deliberately
# skips them when no compositor is available; exercise them here so widget
# popover allocation and repeated Customize/Done cycles remain covered.
if PYTHONPATH=/src/desktop python3 -m pytest -q -p no:cacheprovider \
        /src/tests/unit/test_widgets.py \
        -k 'widget_allocation_presents_popovers or widget_customize_can_be_closed' \
        >"$out/smoke/widget-popovers.log" 2>&1; then
    echo "ok: widget popovers"
else
    echo "FAILED: widget popovers"; fail=1; tail -30 "$out/smoke/widget-popovers.log"
fi

if grep -q "Traceback" "$out/shell.log"; then
    echo "FAILED: shell raised an exception"; fail=1
    sed -n '/Traceback/,$p' "$out/shell.log" | head -30
fi
pgrep -f aurora-shell >/dev/null || { echo "FAILED: shell is not running"; fail=1; }

echo "$fail" > "$out/smoke/result"
