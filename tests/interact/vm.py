"""Drive a real Aurora session in QEMU like a person would.

A USB tablet gives absolute pointer positions and QMP injects clicks, drags and
key presses; the guest agent runs commands in the session and asks the shell
what is on screen (`aurora-shell windows`). Screenshots are saved after every
step so a failure can be looked at.
"""

import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("boot_test", os.path.join(HERE, "..", "boot", "boot-test.py"))
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

W, H = 1920, 1080


def quote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


class VM:
    def __init__(self, iso, out, firmware="bios", vga="virtio-vga", grub_keys=(), disk=""):
        self.out = out
        os.makedirs(out, exist_ok=True)
        self.tmp = tempfile.mkdtemp(prefix="aurora-interact-")
        self.qga = os.path.join(self.tmp, "qga.sock")
        self.mon = os.path.join(self.tmp, "mon.sock")
        self.qmp_path = os.path.join(self.tmp, "qmp.sock")
        self.step = 0
        cmd = ["qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-machine", "q35",
               "-smp", "4", "-m", "6144",
               # Only this display, as on real machines and Hyper-V: without
               # -vga none, QEMU adds a second, empty standard VGA screen.
               "-vga", "none",
               "-device", f"{vga},xres={W},yres={H}" if vga.startswith("virtio") else vga,
               "-display", "none", "-nic", "user,model=virtio-net-pci",
               "-monitor", f"unix:{self.mon},server,nowait",
               "-qmp", f"unix:{self.qmp_path},server,nowait",
               "-device", "qemu-xhci", "-device", "usb-tablet",
               "-device", "virtio-serial",
               "-chardev", f"socket,path={self.qga},server=on,wait=off,id=qga0",
               "-device", "virtserialport,chardev=qga0,name=org.qemu.guest_agent.0"]
        if iso:
            cmd += ["-cdrom", iso, "-boot", "d"]
        if disk:
            if not os.path.exists(disk):
                subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", disk, "40G"],
                               check=True)
            cmd += ["-drive", f"file={disk},if=virtio,format=qcow2"]
        if firmware == "uefi":
            ovmf = next(p for p in bt.OVMF_CANDIDATES if os.path.exists(p))
            cmd += ["-drive", f"if=pflash,format=raw,readonly=on,file={ovmf}"]
        self.qemu = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if grub_keys:
            # Pick another boot menu entry, e.g. ("down", "down", "ret") for
            # "Try Aurora OS (safe graphics)".
            time.sleep(7 if firmware == "uefi" else 4)
            for key in grub_keys:
                bt.monitor(self.mon, f"sendkey {key}")
        self.agent = bt.Agent(self.qga)
        for _ in range(100):
            try:
                if self.agent.sock is None:
                    self.agent.connect()
                self.agent.sync()
                break
            except Exception:  # noqa: BLE001 - keep polling until the guest answers
                self.agent.sock = None
                time.sleep(3)
        self.root("for i in $(seq 180); do test -f /run/user/1000/aurora-shell.ready && exit 0; "
                  "sleep 1; done; exit 1", timeout=200)
        time.sleep(6)
        self._qmp = self._qmp_connect()
        # No screen blanking or welcome window while testing.
        self.user("gsettings set org.aurora.desktop idle-dim-minutes 0; pkill -x swayidle; "
                  "wlopm --on '*'; pkill -f [a]urora-welcome")
        self.move(W - 200, H // 2)
        time.sleep(1)

    # --- guest commands -------------------------------------------------------

    def root(self, command, timeout=60):
        return self.agent.run(command, timeout=timeout)

    def user(self, command, timeout=60):
        """Run a command in the live user's session; returns (code, output)."""
        return self.agent.run(f"{bt.USER_ENV} sh -c {quote(command)}", timeout=timeout)

    def launch(self, desktop_id):
        self.user(f"setsid -f gio launch /usr/share/applications/{desktop_id} >/dev/null 2>&1")

    def windows(self):
        _code, out = self.user("aurora-shell windows")
        return [json.loads(line) for line in out.splitlines() if line.startswith("{")]

    def window(self, app_id):
        return next((w for w in self.windows() if w["app_id"] == app_id), None)

    def wait_for(self, predicate, timeout=15, what="condition"):
        end = time.time() + timeout
        while time.time() < end:
            if predicate():
                return True
            time.sleep(0.5)
        return False

    def push(self, local, remote):
        """Copy a file into the running system (to try a change without a rebuild)."""
        import base64
        data = base64.b64encode(open(local, "rb").read()).decode()
        self.root(f"rm -f {remote}.b64")
        for i in range(0, len(data), 60000):
            self.root(f"printf %s {data[i:i + 60000]} >> {remote}.b64")
        code, out = self.root(f"base64 -d {remote}.b64 > {remote} && rm {remote}.b64")
        return code

    def push_desktop(self, repo):
        """Copy every Aurora Python module and data file that changed into the VM."""
        pushed = []
        for base, target in (("desktop/aurora", "/usr/lib/aurora/aurora"),
                             ("desktop/bin", "/usr/bin"),
                             ("desktop/data/style", "/usr/share/aurora/style"),
                             ("desktop/data/gtk", "/usr/share/aurora/gtk")):
            for root, _dirs, files in os.walk(os.path.join(repo, base)):
                if "__pycache__" in root:
                    continue
                for name in files:
                    local = os.path.join(root, name)
                    remote = os.path.join(target, os.path.relpath(local, os.path.join(repo, base)))
                    _c, same = self.root(f"test -f {remote} && md5sum {remote} | cut -d' ' -f1")
                    import hashlib
                    if same.strip() == hashlib.md5(open(local, "rb").read()).hexdigest():
                        continue
                    self.push(local, remote)
                    if base == "desktop/bin":
                        self.root(f"chmod +x {remote}")
                    pushed.append(remote)
        return pushed

    def restart_shell(self):
        # Let the session's real watchdog restart it. Starting a replacement
        # here detached it from that watchdog, making later crash-recovery
        # checks fail even though the installed session behaves correctly.
        self.user("rm -f $XDG_RUNTIME_DIR/aurora-shell.ready; "
                  "pkill -f '^/usr/bin/python3 /usr/bin/[a]urora-shell$'; "
                  "for i in $(seq 40); do test -f $XDG_RUNTIME_DIR/aurora-shell.ready && exit 0; "
                  "sleep 0.5; done; exit 1", timeout=40)
        time.sleep(2)

    # --- input ------------------------------------------------------------------

    def _qmp_connect(self):
        sock = socket.socket(socket.AF_UNIX)
        sock.connect(self.qmp_path)
        f = sock.makefile("rw")
        f.readline()
        self._qmp_file = f
        self._qmp_send({"execute": "qmp_capabilities"})
        return sock

    def _qmp_send(self, cmd):
        f = self._qmp_file
        f.write(json.dumps(cmd) + "\n")
        f.flush()
        while True:
            reply = json.loads(f.readline())
            if "return" in reply or "error" in reply:
                return reply

    def _events(self, events):
        self._qmp_send({"execute": "input-send-event", "arguments": {"events": events}})

    def move(self, x, y):
        self._events([{"type": "abs", "data": {"axis": "x", "value": int(x * 32767 / W)}},
                      {"type": "abs", "data": {"axis": "y", "value": int(y * 32767 / H)}}])

    def button(self, name, down):
        self._events([{"type": "btn", "data": {"down": down, "button": name}}])

    def click(self, x, y, button="left", double=False, pause=0.6):
        self.move(x, y)
        time.sleep(0.15)
        for _ in range(2 if double else 1):
            self.button(button, True)
            time.sleep(0.05)
            self.button(button, False)
            time.sleep(0.08)
        time.sleep(pause)

    def scroll(self, x, y, clicks, pause=0.6):
        """Turn the wheel over (x, y): positive clicks scroll down."""
        self.move(x, y)
        time.sleep(0.15)
        wheel = "wheel-down" if clicks > 0 else "wheel-up"
        for _ in range(abs(clicks)):
            self.button(wheel, True)
            self.button(wheel, False)
            time.sleep(0.03)
        time.sleep(pause)

    def right_click(self, x, y, pause=0.8):
        self.click(x, y, button="right", pause=pause)

    def keys(self, *combo, pause=0.6):
        """Press keys together, e.g. keys("meta_l", "m")."""
        self._qmp_send({"execute": "send-key", "arguments": {
            "keys": [{"type": "qcode", "data": k} for k in combo]}})
        time.sleep(pause)

    # --- evidence ---------------------------------------------------------------

    def shot(self, label):
        self.step += 1
        path = os.path.join(self.out, f"{self.step:02d}-{label}.png")
        bt.screenshot(self.mon, path)
        return path

    def record_start(self, x, y, w, h, frames=60, gap=0.03, delay=0.3):
        """Film a screen region inside the guest (grim), to look at an animation."""
        self.user(f"rm -rf /tmp/fr; mkdir -p /tmp/fr; setsid -f sh -c 'sleep {delay}; i=0; "
                  f"while [ $i -lt {frames} ]; do grim -g \"{x},{y} {w}x{h}\" -t ppm "
                  f"/tmp/fr/$(printf %03d $i).ppm; sleep {gap}; i=$((i+1)); done' >/dev/null 2>&1")

    def record_sheet(self, label, cols=6, thumb=(253, 147)):
        """Wait for the film, then save a contact sheet of its frames."""
        import base64
        time.sleep(0.5)
        py = ("import os,glob\nfrom PIL import Image\n"
              "fs=sorted(glob.glob('/tmp/fr/*.ppm'))\n"
              f"ims=[Image.open(f).resize({thumb}) for f in fs]\n"
              f"rows=(len(ims)+{cols}-1)//{cols}\n"
              f"sheet=Image.new('RGB',({thumb[0]}*{cols},{thumb[1]}*rows))\n"
              f"[sheet.paste(im,((i%{cols})*{thumb[0]},(i//{cols})*{thumb[1]})) for i,im in enumerate(ims)]\n"
              "sheet.save('/tmp/sheet.jpg',quality=80)\n")
        self.user(f"python3 -c {quote(py)}")
        _c, out = self.user("base64 -w0 /tmp/sheet.jpg", timeout=60)
        self.step += 1
        path = os.path.join(self.out, f"{self.step:02d}-{label}.jpg")
        with open(path, "wb") as f:
            f.write(base64.b64decode(out.strip()))
        return path

    def close(self):
        self.qemu.terminate()
        try:
            self.qemu.wait(15)
        except subprocess.TimeoutExpired:
            self.qemu.kill()
