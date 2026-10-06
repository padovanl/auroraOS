#!/usr/bin/env python3
"""Take the website/README screenshots from the real ISO running in QEMU.

Usage: tools/vm-screenshots.py ISO [--out docs/screenshots]

Boots the live system (1920x1080), then drives the real session through the
QEMU guest agent: opens apps, Spotlight, Launchpad, the Control Center and the
layout presets, and saves a PNG after each step.
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "boot_test", os.path.join(HERE, "..", "tests", "boot", "boot-test.py"))
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

# In the session: aurora-shell/gsettings/gio as the live user.
U = bt.USER_ENV

PRESET = ("python3 -c \"import sys; sys.path.insert(0, '/usr/lib/aurora'); "
          "from aurora import settings, look; from aurora.settingsapp.desktop import PRESETS; "
          "s = settings.get(); v = PRESETS['{name}']['values']; "
          "[s.set_boolean(k, x) if isinstance(x, bool) else s.set_int(k, x) if isinstance(x, int) "
          "else s.set_double(k, x) if isinstance(x, float) else s.set_string(k, x) for k, x in v.items()]; "
          "s.set_string('layout', '{name}'); look.apply()\"")

def launch(desktop_id):
    """Start an app detached, so the guest agent does not wait on its output."""
    return f"setsid -f gio launch /usr/share/applications/{desktop_id} >/dev/null 2>&1"


# Close every app between scenes, so no window is left behind the next one
# (the [x] keeps pkill from matching its own command line).
CLEAN = ("aurora-shell quick-settings hide; "
         "pkill -f '[a]urora-files|[a]urora-settings|[a]urora-devhub|[a]urora-gamehub|"
         "[p]tyxis|[g]nome-text-editor|[a]urora-quicklook|[a]urora-assistant'; sleep 1")

# (screenshot name or None, shell command run in the session, seconds to wait)
STEPS = [
    # No screen blanking while the screenshots are taken.
    (None, "gsettings set org.aurora.desktop idle-dim-minutes 0; pkill -x swayidle; "
           "wlopm --on '*'", 1),
    # The desktop starts without widgets; the showcase puts three on it.
    (None, "gsettings set org.aurora.desktop desktop-widget-list "
           "'[{\"kind\": \"clock\", \"x\": 0.86, \"y\": 0.06}, "
           "{\"kind\": \"calendar\", \"x\": 0.86, \"y\": 0.3}, "
           "{\"kind\": \"weather\", \"x\": 0.86, \"y\": 0.54}]'", 2),
    (None, "pkill -f [a]urora-welcome; mkdir -p ~/Desktop; "
           "printf 'Welcome to Aurora' > ~/Desktop/Welcome.txt", 2),
    (None, launch("org.aurora.Files.desktop"), 6),
    ("desktop", None, 2),
    (None, "aurora-shell search disp", 3),
    ("spotlight-search", None, 0),
    (None, "aurora-shell search '10 km in mi'", 3),
    ("spotlight-convert", None, 0),
    (None, "aurora-shell launcher spotlight; aurora-shell launcher grid", 3),
    ("launchpad", None, 0),
    (None, "aurora-shell launcher grid; aurora-shell quick-settings", 3),
    ("control-center", None, 0),
    (None, CLEAN, 1),
    (None, launch("org.aurora.Settings.desktop"), 4),
    (None, "setsid -f aurora-settings --page desktop >/dev/null 2>&1", 5),
    ("settings-desktop", None, 0),
    (None, "setsid -f aurora-settings --page appearance >/dev/null 2>&1", 5),
    ("settings-appearance", None, 0),
    (None, "setsid -f aurora-settings --page keyboard >/dev/null 2>&1", 5),
    ("settings-keyboard", None, 0),
    (None, "setsid -f aurora-settings --page accessibility >/dev/null 2>&1", 5),
    ("settings-accessibility", None, 0),
    (None, "setsid -f aurora-settings --page power >/dev/null 2>&1", 5),
    ("settings-power", None, 0),
    (None, "setsid -f aurora-settings --page health >/dev/null 2>&1", 10),
    ("settings-health", None, 0),
    (None, "setsid -f aurora-settings --page ai >/dev/null 2>&1", 6),
    ("settings-ai", None, 0),
    (None, CLEAN, 1),
    (None, launch("org.aurora.DevHub.desktop"), 8),
    ("devhub", None, 0),
    (None, CLEAN, 1),
    (None, launch("org.aurora.GameHub.desktop"), 8),
    ("gamehub", None, 0),
    (None, CLEAN, 1),
    (None, launch("org.gnome.Ptyxis.desktop"), 6),
    ("terminal", None, 0),
    (None, launch("org.gnome.TextEditor.desktop"), 3),
    (None, launch("org.aurora.Files.desktop"), 5),
    (None, "aurora-shell overview", 3),
    ("overview", None, 0),
    (None, "aurora-shell overview", 1),
    (None, CLEAN, 1),
    (None, "setsid -f aurora-quicklook /usr/lib/aurora/aurora/sun.py >/dev/null 2>&1", 5),
    ("quicklook", None, 0),
    (None, CLEAN, 1),
    (None, launch("org.aurora.Files.desktop"), 6),
    ("files", None, 0),
    # Aurora AI's screens: the Assistant, asking from Spotlight, Writing Tools on a
    # selection (the AI is off by default; the screens don't need a model).
    (None, CLEAN + "; gsettings set org.aurora.desktop ai-enabled true; "
           "gsettings set org.aurora.desktop ai-writing-tools true", 1),
    (None, "aurora-shell search '? how do I free disk space'", 3),
    ("spotlight-ask", None, 0),
    (None, "aurora-shell launcher spotlight", 1),
    (None, launch("org.aurora.Files.desktop"), 5),
    (None, "aurora-shell assistant", 6),
    ("assistant", None, 0),
    (None, CLEAN, 1),
    (None, launch("org.gnome.TextEditor.desktop"), 4),
    (None, "wl-copy --primary 'Their going to the meeting tomorrow, we should prepare "
           "the slides.'; aurora-shell writing", 5),
    ("writing-tools", None, 0),
    (None, CLEAN, 1),
    (None, launch("org.aurora.Files.desktop"), 6),
    # The Assistant floats over the window you are working in, like picture-in-picture.
    (None, "setsid -f aurora-assistant >/dev/null 2>&1", 6),
    ("assistant-pip", None, 0),
    (None, "pkill -f '[a]urora-assistant'", 1),
    (None, PRESET.format(name="studio"), 5),
    ("layout-studio", None, 0),
    (None, PRESET.format(name="classic"), 5),
    ("layout-classic", None, 0),
    (None, PRESET.format(name="minimal"), 5),
    ("layout-minimal", None, 0),
    (None, PRESET.format(name="aurora"), 3),
    (None, CLEAN, 1),
]


def park_pointer(qmp_path, x=1700, y=620):
    """Move the pointer (a USB tablet: absolute coordinates) onto empty desktop,
    away from icons, tooltips and hot corners."""
    import json
    import socket
    with socket.socket(socket.AF_UNIX) as sock:
        sock.connect(qmp_path)
        f = sock.makefile("rw")
        f.readline()  # greeting
        for cmd in ({"execute": "qmp_capabilities"},
                    {"execute": "input-send-event", "arguments": {"events": [
                        {"type": "abs", "data": {"axis": "x", "value": x * 32767 // 1920}},
                        {"type": "abs", "data": {"axis": "y", "value": y * 32767 // 1080}}]}}):
            f.write(json.dumps(cmd) + "\n")
            f.flush()
            while "return" not in (reply := json.loads(f.readline())) and "error" not in reply:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "screenshots"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="aurora-shots-")
    qga, mon = os.path.join(tmp, "qga.sock"), os.path.join(tmp, "mon.sock")
    qmp = os.path.join(tmp, "qmp.sock")
    cmd = ["qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-machine", "q35", "-smp", "4",
           "-m", "6144", "-cdrom", args.iso, "-boot", "d",
           "-device", "virtio-vga,xres=1920,yres=1080", "-display", "none",
           "-nic", "user,model=virtio-net-pci", "-monitor", f"unix:{mon},server,nowait",
           "-qmp", f"unix:{qmp},server,nowait", "-device", "qemu-xhci", "-device", "usb-tablet",
           "-device", "virtio-serial",
           "-chardev", f"socket,path={qga},server=on,wait=off,id=qga0",
           "-device", "virtserialport,chardev=qga0,name=org.qemu.guest_agent.0"]
    qemu = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        agent = bt.Agent(qga)
        for _ in range(100):
            try:
                if agent.sock is None:
                    agent.connect()
                agent.sync()
                break
            except Exception:  # noqa: BLE001 - keep polling until the guest answers
                agent.sock = None
                time.sleep(3)
        agent.run("for i in $(seq 180); do test -f /run/user/1000/aurora-shell.ready && exit 0; sleep 1; done",
                  timeout=100)
        time.sleep(8)
        park_pointer(qmp)
        for name, command, wait in STEPS:
            if command:
                code, out = agent.run(f"{U} sh -c {sh_quote(command)}", timeout=60)
                if code != 0:
                    print(f"step failed ({code}): {command}\n{out}")
            time.sleep(wait)
            if name:
                park_pointer(qmp)
                time.sleep(0.5)
                bt.screenshot(mon, os.path.join(args.out, f"{name}.png"))
                print(f"saved {name}.png")
    finally:
        qemu.terminate()
        qemu.wait(10)


def sh_quote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    sys.exit(main())
