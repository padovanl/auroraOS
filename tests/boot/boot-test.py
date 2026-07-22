#!/usr/bin/env python3
"""Boot the ISO in QEMU through its real boot loader and check the live system.

Usage: boot-test.py ISO [--firmware bios|uefi] [--out DIR] [--timeout SECONDS]

Talks to the QEMU guest agent (qemu-guest-agent is part of the image) to run
checks inside the guest, and uses the QEMU monitor for screenshots. Exits
non-zero if any check fails, so it can gate a release.
"""

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

OVMF_CANDIDATES = ["/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/ovmf/OVMF.fd",
                   "/usr/share/OVMF/OVMF_CODE.fd"]

# (description, shell command run in the guest; success = exit status 0)
CHECKS = [
    ("live medium mounted", "test -f /run/live/medium/live/filesystem.squashfs"),
    ("booted in graphical target", "systemctl is-active graphical.target"),
    ("no failed system units", "test -z \"$(systemctl --failed --plain --no-legend)\""),
    ("greetd running", "systemctl is-active greetd"),
    ("live user created", "id aurora"),
    ("compositor running", "pgrep -x labwc"),
    ("aurora shell running", "pgrep -f /usr/bin/aurora-shell"),
    ("no shell exceptions",
     "! grep -q Traceback /run/user/$(id -u aurora)/aurora-shell.log"),
    ("NetworkManager up", "nmcli -t -f RUNNING general | grep -q running"),
    ("network connected", "nmcli -t -f STATE general | grep -q connected"),
    ("firewall active", "ufw status | grep -q 'Status: active'"),
    ("plymouth theme", "plymouth-set-default-theme | grep -qx aurora"),
    ("installer available", "test -x /usr/bin/calamares"),
]


class Agent:
    def __init__(self, path):
        self.path = path
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect(self.path)
        self.buf = b""

    def request(self, execute, args=None, timeout=10):
        msg = {"execute": execute}
        if args:
            msg["arguments"] = args
        self.sock.settimeout(timeout)
        self.sock.sendall(json.dumps(msg).encode() + b"\n")
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("agent closed")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        reply = json.loads(line)
        if "error" in reply:
            raise RuntimeError(reply["error"].get("desc"))
        return reply.get("return")

    def sync(self):
        token = int(time.time()) & 0x7FFFFFFF
        self.request("guest-sync", {"id": token}, timeout=3)

    def run(self, command, timeout=30):
        pid = self.request("guest-exec", {"path": "/bin/sh", "arg": ["-c", command],
                                          "capture-output": True})["pid"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.request("guest-exec-status", {"pid": pid})
            if st.get("exited"):
                out = base64.b64decode(st.get("out-data", "")).decode(errors="replace")
                err = base64.b64decode(st.get("err-data", "")).decode(errors="replace")
                return st.get("exitcode", 1), out + err
            time.sleep(0.5)
        return 124, "timeout"


MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                        "config", "apps.manifest")

USER_ENV = ("uid=$(id -u aurora); runuser -u aurora -- env XDG_RUNTIME_DIR=/run/user/$uid "
            "WAYLAND_DISPLAY=wayland-0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus "
            "XDG_CURRENT_DESKTOP=Aurora:wlroots ")


def manifest_apps():
    apps = []
    with open(MANIFEST) as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            _cat, name, desktop_id, launch = [c.strip() for c in line.split("|")]
            if launch == "yes":
                apps.append((name, desktop_id))
    return apps


def launch_check(agent, name, desktop_id):
    """Start an app as the live user; pass if its process is alive a few seconds later."""
    path = (f"$(for d in /usr/local/share/applications /usr/share/applications; do "
            f"[ -f $d/{desktop_id} ] && echo $d/{desktop_id} && break; done)")
    exe = (f"$(sed -n 's/^Exec=//p' {path} | head -1 | awk '{{print $1}}' | xargs basename)")
    script = (f"p={path}; e={exe}; "
              f"{USER_ENV} gio launch \"$p\" >/dev/null 2>&1 & "
              f"sleep 8; pgrep -u aurora -f \"$e\" >/dev/null; r=$?; "
              f"pkill -u aurora -f \"$e\"; sleep 1; exit $r")
    code, out = agent.run(script, timeout=40)
    return code == 0, out.strip()[:200]


def monitor(path, command):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    s.recv(4096)
    s.sendall(command.encode() + b"\n")
    time.sleep(1.5)
    s.close()


def screenshot(mon, dest):
    ppm = dest + ".ppm"
    monitor(mon, f"screendump {ppm}")
    try:
        from PIL import Image
        img = Image.open(ppm).convert("RGB")
        img.save(dest)
        os.remove(ppm)
        return img
    except ImportError:
        return None


def desktop_visible(img):
    """Heuristic: a dark translucent top bar and a non-uniform picture."""
    if img is None:
        return True
    w, h = img.size
    bar = [img.getpixel((x, 10)) for x in range(0, w, max(1, w // 50))]
    dark_bar = sum(1 for p in bar if sum(p) < 200) > len(bar) * 0.8
    colors = len(set(img.resize((64, 36)).getdata()))
    return dark_bar and colors > 200


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--firmware", choices=["bios", "uefi"], default="bios")
    ap.add_argument("--out", default="boot-test-out")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--no-apps", action="store_true",
                    help="skip starting every default app from config/apps.manifest")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="aurora-boot-")
    qga, mon = os.path.join(tmp, "qga.sock"), os.path.join(tmp, "mon.sock")
    serial = os.path.join(args.out, f"serial-{args.firmware}.log")
    cmd = ["qemu-system-x86_64", "-machine", "q35", "-smp", "2", "-m", "4096",
           "-cdrom", args.iso, "-boot", "d", "-device", "virtio-vga", "-display", "none",
           "-nic", "user,model=virtio-net-pci",
           "-monitor", f"unix:{mon},server,nowait", "-serial", f"file:{serial}",
           "-device", "virtio-serial",
           "-chardev", f"socket,path={qga},server=on,wait=off,id=qga0",
           "-device", "virtserialport,chardev=qga0,name=org.qemu.guest_agent.0"]
    if os.access("/dev/kvm", os.W_OK):
        cmd[1:1] = ["-enable-kvm", "-cpu", "host"]
    if args.firmware == "uefi":
        ovmf = next((p for p in OVMF_CANDIDATES if os.path.exists(p)), None)
        if ovmf is None:
            sys.exit("OVMF firmware not found (install the ovmf package)")
        cmd += ["-drive", f"if=pflash,format=raw,readonly=on,file={ovmf}"]

    print(f"booting {args.iso} ({args.firmware})")
    qemu = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    results = []
    try:
        agent = Agent(qga)
        deadline = time.time() + args.timeout
        up = False
        while time.time() < deadline and qemu.poll() is None:
            try:
                if agent.sock is None:
                    agent.connect()
                agent.sync()
                agent.request("guest-ping")
                up = True
                break
            except (OSError, RuntimeError, ConnectionError, json.JSONDecodeError):
                agent.sock = None
                time.sleep(3)
        boot_time = args.timeout - (deadline - time.time())
        results.append(("guest agent answered", up, f"{boot_time:.0f}s"))
        if up:
            # Give the session a moment to start after the agent comes up.
            code, _ = agent.run("for i in $(seq 60); do pgrep -f /usr/bin/aurora-shell && "
                                "exit 0; sleep 1; done; exit 1", timeout=70)
            time.sleep(5)
            for desc, command in CHECKS:
                code, out = agent.run(command)
                results.append((desc, code == 0, out.strip()[:200]))
            # Keep logs as test artifacts.
            for name, command in (("shell", "cat /run/user/$(id -u aurora)/aurora-shell.log"),
                                  ("journal", "journalctl -b -p warning --no-pager | tail -300")):
                _code, out = agent.run(command)
                with open(os.path.join(args.out, f"{name}-{args.firmware}.log"), "w") as f:
                    f.write(out)
        img = screenshot(mon, os.path.join(args.out, f"desktop-{args.firmware}.png"))
        results.append(("desktop visible on screen", desktop_visible(img), ""))
        if up and not args.no_apps:
            for name, desktop_id in manifest_apps():
                ok, detail = launch_check(agent, name, desktop_id)
                results.append((f"app starts: {name}", ok, detail))
    finally:
        qemu.terminate()
        try:
            qemu.wait(10)
        except subprocess.TimeoutExpired:
            qemu.kill()
        shutil.rmtree(tmp, ignore_errors=True)

    failed = 0
    for desc, ok, detail in results:
        print(f"{'ok' if ok else 'FAILED'}: {desc}" + (f"  ({detail})" if detail and not ok else ""))
        failed += not ok
    with open(os.path.join(args.out, f"report-{args.firmware}.json"), "w") as f:
        json.dump([{"check": d, "ok": o, "detail": x} for d, o, x in results], f, indent=2)
    print(f"\n{len(results) - failed}/{len(results)} checks passed ({args.firmware})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
