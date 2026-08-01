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

# (screenshot name or None, shell command run in the session, seconds to wait)
STEPS = [
    (None, "pkill -f aurora-welcome; mkdir -p ~/Desktop; "
           "printf 'Welcome to Aurora' > ~/Desktop/Welcome.txt", 2),
    (None, "gio launch /usr/share/applications/org.aurora.Files.desktop", 5),
    (None, "notify-send -a Aurora -i software-update-available 'Updates installed' "
           "'Security updates were installed in the background. No restart needed.'", 1),
    ("desktop", None, 2),
    (None, "aurora-shell search disp", 2),
    ("spotlight-search", None, 0),
    (None, "aurora-shell search '10 km in mi'", 2),
    ("spotlight-convert", None, 0),
    (None, "aurora-shell launcher spotlight; aurora-shell launcher grid", 3),
    ("launchpad", None, 0),
    (None, "aurora-shell launcher grid; aurora-shell quick-settings", 3),
    ("control-center", None, 0),
    (None, "pkill -f aurora-files; gio launch /usr/share/applications/org.aurora.Settings.desktop; "
           "sleep 3; aurora-settings --page desktop", 4),
    ("settings-desktop", None, 0),
    (None, "aurora-settings --page appearance", 3),
    ("settings-appearance", None, 0),
    (None, "aurora-settings --page keyboard", 3),
    ("settings-keyboard", None, 0),
    (None, "pkill -f aurora-settings; gio launch /usr/share/applications/org.aurora.DevHub.desktop", 6),
    ("devhub", None, 0),
    (None, "pkill -f aurora-devhub; gio launch /usr/share/applications/org.gnome.Ptyxis.desktop", 5),
    ("terminal", None, 0),
    (None, "gio launch /usr/share/applications/org.gnome.TextEditor.desktop; "
           "gio launch /usr/share/applications/org.aurora.Files.desktop", 5),
    (None, "aurora-shell overview", 3),
    ("overview", None, 0),
    (None, "aurora-shell overview; pkill -f gnome-text-editor; "
           "aurora-quicklook /usr/lib/aurora/aurora/sun.py >/dev/null 2>&1 &", 4),
    ("quicklook", None, 0),
    (None, "pkill -f aurora-quicklook", 1),
    (None, "pkill -f ptyxis; gio launch /usr/share/applications/org.aurora.Files.desktop", 4),
    (None, PRESET.format(name="studio"), 4),
    ("layout-studio", None, 0),
    (None, PRESET.format(name="classic"), 4),
    ("layout-classic", None, 0),
    (None, PRESET.format(name="minimal"), 4),
    ("layout-minimal", None, 0),
    (None, PRESET.format(name="aurora"), 3),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "docs", "screenshots"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="aurora-shots-")
    qga, mon = os.path.join(tmp, "qga.sock"), os.path.join(tmp, "mon.sock")
    cmd = ["qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-machine", "q35", "-smp", "4",
           "-m", "6144", "-cdrom", args.iso, "-boot", "d",
           "-device", "virtio-vga,xres=1920,yres=1080", "-display", "none",
           "-nic", "user,model=virtio-net-pci", "-monitor", f"unix:{mon},server,nowait",
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
        agent.run("for i in $(seq 90); do pgrep -f [/]usr/bin/aurora-shell && exit 0; sleep 1; done",
                  timeout=100)
        time.sleep(8)
        for name, command, wait in STEPS:
            if command:
                code, out = agent.run(f"{U} sh -c {sh_quote(command)}", timeout=60)
                if code != 0:
                    print(f"step failed ({code}): {command}\n{out}")
            time.sleep(wait)
            if name:
                bt.screenshot(mon, os.path.join(args.out, f"{name}.png"))
                print(f"saved {name}.png")
    finally:
        qemu.terminate()
        qemu.wait(10)


def sh_quote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    sys.exit(main())
