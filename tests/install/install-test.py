#!/usr/bin/env python3
"""Install Aurora OS onto an empty virtual disk with the real installer, then
boot the installed system and check it.

Usage: install-test.py ISO [--firmware bios|uefi] [--out DIR] [--keep-disk]

Phase 1 boots the ISO, starts Calamares in the live session and drives it with
key presses sent through the QEMU monitor (exactly what a user's keyboard
would do): Next through welcome, location and keyboard, "Erase disk" with the
default btrfs file system, a user with a password, Install. A screenshot is
saved after every step.

Phase 2 boots the new disk alone and checks, through the QEMU guest agent:
the user, greetd and the Aurora session, the btrfs subvolumes, Timeshift's
configuration and the "Fresh install" snapshot, the grub-btrfs daemon, and
that installing a package takes a "Before: apt" snapshot that appears in the
boot menu. It also saves a screenshot of GRUB's "Aurora OS snapshots" menu.
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("boot_test", os.path.join(HERE, "..", "boot",
                                                                         "boot-test.py"))
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

USER_FULL, USER, PASSWORD = "Test User", "test", "Northern7Lights42"
DISK_SIZE = "24G"

# Characters sendkey needs names for.
KEYNAMES = {" ": "spc", "-": "minus", ".": "dot", "/": "slash", "_": "shift-minus",
            ":": "shift-semicolon", ",": "comma", "=": "equal"}


class VM:
    def __init__(self, args, disk, cdrom, out, name):
        self.tmp = tempfile.mkdtemp(prefix="aurora-install-")
        self.qga = os.path.join(self.tmp, "qga.sock")
        self.mon = os.path.join(self.tmp, "mon.sock")
        self.out, self.name, self.step = out, name, 0
        cmd = ["qemu-system-x86_64", "-machine", "q35", "-smp", "4", "-m", "4096",
               "-drive", f"file={disk},if=virtio,format=qcow2",
               "-device", "virtio-vga", "-display", "none",
               "-nic", "user,model=virtio-net-pci",
               "-monitor", f"unix:{self.mon},server,nowait",
               "-serial", f"file:{os.path.join(out, f'serial-{name}.log')}",
               "-device", "virtio-serial",
               "-chardev", f"socket,path={self.qga},server=on,wait=off,id=qga0",
               "-device", "virtserialport,chardev=qga0,name=org.qemu.guest_agent.0"]
        if cdrom:
            cmd += ["-cdrom", cdrom, "-boot", "d"]
        if os.access("/dev/kvm", os.W_OK):
            cmd[1:1] = ["-enable-kvm", "-cpu", "host"]
        if args.firmware == "uefi":
            if args.hyperv_identity:
                # Exercise our Hyper-V installer policy, not its firmware/drivers.
                cmd += ["-smbios", "type=1,manufacturer=Microsoft Corporation,product=Virtual Machine"]
            # Test the installer's registered entry first, then boot again after
            # package updates with fresh NVRAM to exercise the disk fallback.
            vars_file = os.path.join(out, f"OVMF_VARS-{name}.fd")
            vars_source = (os.path.join(out, "OVMF_VARS-install-uefi.fd")
                           if name == "installed-uefi"
                           else os.path.join(out, "OVMF_VARS-installed-uefi.fd")
                           if name == "after-efi-update-nvram"
                           else "/usr/share/OVMF/OVMF_VARS_4M.fd")
            shutil.copy(vars_source, vars_file)
            cmd += ["-drive", "if=pflash,format=raw,readonly=on,"
                              "file=/usr/share/OVMF/OVMF_CODE_4M.fd",
                    "-drive", f"if=pflash,format=raw,file={vars_file}"]
        self.qemu = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.agent = bt.Agent(self.qga)

    def wait_agent(self, timeout=300):
        deadline = time.time() + timeout
        while time.time() < deadline and self.qemu.poll() is None:
            try:
                if self.agent.sock is None:
                    self.agent.connect()
                self.agent.sync()
                return True
            except Exception:  # noqa: BLE001 - keep polling until the guest answers
                self.agent.sock = None
                time.sleep(3)
        return False

    def run(self, command, timeout=60):
        return self.agent.run(command, timeout=timeout)

    def shot(self, label):
        self.step += 1
        path = os.path.join(self.out, f"{self.name}-{self.step:02d}-{label}.png")
        return bt.screenshot(self.mon, path)

    def alive(self):
        """Raise with QEMU's own error message if it has exited."""
        if self.qemu.poll() is not None:
            err = self.qemu.stderr.read().decode(errors="replace").strip()
            raise RuntimeError(f"QEMU exited ({self.qemu.returncode}): {err}")

    def keys(self, *names, delay=0.15):
        self.alive()
        for name in names:
            bt.monitor(self.mon, f"sendkey {name}")
            time.sleep(delay)

    def type(self, text):
        names = []
        for ch in text:
            if ch.isupper():
                names.append(f"shift-{ch.lower()}")
            elif ch in KEYNAMES:
                names.append(KEYNAMES[ch])
            else:
                names.append(ch)
        self.keys(*names, delay=0.05)

    def stop(self):
        self.qemu.terminate()
        try:
            self.qemu.wait(15)
        except subprocess.TimeoutExpired:
            self.qemu.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


def install(args, disk, out, results):
    vm = VM(args, disk, args.iso, out, f"install-{args.firmware}")
    try:
        if not vm.wait_agent():
            results.append(("live system booted", False, ""))
            return False
        vm.run("for i in $(seq 180); do test -f /run/user/1000/aurora-shell.ready && exit 0; sleep 1; done",
               timeout=100)
        time.sleep(8)
        vm.run("pkill -f 'bin/aurora-welcom[e]'", timeout=10)
        # The guest agent ends a command's session when it returns: keep this one
        # running (the call just times out) so Calamares stays up.
        vm.run(f"{bt.USER_ENV} sh -c 'aurora-installer >/tmp/calamares.log 2>&1'", timeout=5)
        for _ in range(60):
            code, _o = vm.run("pgrep -x calamares")
            if code == 0:
                break
            time.sleep(1)
        # The welcome page checks the requirements before Next is enabled.
        time.sleep(25)
        vm.shot("welcome")
        # Welcome → Location → Keyboard → Partitions (Next = Alt+N).
        for label in ("location", "keyboard", "partitions"):
            vm.keys("alt-n")
            time.sleep(4)
            vm.shot(label)
        # "Erase disk" is preselected on the only disk; btrfs is the default.
        vm.keys("alt-n")
        time.sleep(4)
        vm.shot("users")
        # The full name field has the focus; login and host names follow it.
        vm.type(USER_FULL)
        vm.keys("tab")
        vm.keys("ctrl-a")
        vm.type(USER)
        vm.keys("tab", "tab")
        vm.type(PASSWORD)
        vm.keys("tab")
        vm.type(PASSWORD)
        time.sleep(1)
        vm.shot("users-filled")
        vm.keys("alt-n")
        time.sleep(4)
        vm.shot("summary")
        vm.keys("alt-i")           # Install
        time.sleep(3)
        vm.shot("confirm")
        vm.keys("alt-i")           # "Install now" in the confirmation dialog
        time.sleep(10)
        vm.shot("installing")
        # Calamares logs every job; the last one unmounts the target. A failure
        # at any point shows up as onInstallationFailed.
        done = False
        deadline = time.time() + args.timeout
        log_cmd = "cat /root/.cache/calamares/session.log 2>/dev/null"
        while time.time() < deadline:
            _code, log = vm.run(log_cmd)
            if "onInstallationFailed" in log:
                break
            if 'Starting job "umount"' in log or "Starting job \"Unmount" in log:
                time.sleep(20)
                _code, log = vm.run(log_cmd)
                done = "onInstallationFailed" not in log
                break
            code, _o = vm.run("pgrep -x calamares")
            if code != 0:
                break
            time.sleep(10)
        time.sleep(3)
        vm.shot("finished")
        _code, log = vm.run("cat /root/.cache/calamares/session.log 2>/dev/null | tail -400")
        with open(os.path.join(out, f"calamares-{args.firmware}.log"), "w") as f:
            f.write(log)
        failure = next((ln.split("ERROR:", 1)[1].strip() for ln in log.splitlines()
                        if "ERROR: Installation failed" in ln), "")
        results.append(("installer finished", done, failure))
        return done
    finally:
        vm.stop()


CHECKS = [
    ("installed system is not the live one", "! grep -qw boot=live /proc/cmdline"),
    ("graphical target", "systemctl is-active graphical.target"),
    ("no failed units", "test -z \"$(systemctl --failed --plain --no-legend)\""),
    ("greetd running", "systemctl is-active greetd"),
    (f"user {USER} exists and is an admin", f"id {USER} | grep -q '(sudo)'"),
    ("live user removed", "! id aurora"),
    ("live-only files removed", "! test -e /etc/sudoers.d/aurora-live"),
    ("root is btrfs", "test \"$(findmnt -no FSTYPE /)\" = btrfs"),
    ("root on subvolume @", "findmnt -no OPTIONS / | grep -q 'subvol=/@'"),
    ("home on subvolume @home", "findmnt -no OPTIONS /home | grep -q 'subvol=/@home'"),
    ("compression on", "findmnt -no OPTIONS / | grep -q compress=zstd"),
    ("Timeshift configured for btrfs", "grep -q '\"btrfs_mode\" *: *\"true\"' /etc/timeshift/timeshift.json"),
    ("grub-btrfsd enabled", "systemctl is-enabled grub-btrfsd"),
    ("grub-btrfs menu script enabled", "test -x /etc/grub.d/41_snapshots-btrfs"),
    ("\"Fresh install\" snapshot", "for i in $(seq 60); do timeshift --list 2>/dev/null | "
     "grep -q 'Fresh install' && exit 0; sleep 2; done; exit 1"),
    ("apt install takes a snapshot", "rm -f /var/lib/aurora/last-apt-snapshot; "
     "DEBIAN_FRONTEND=noninteractive apt-get install -y -q sl >/dev/null 2>&1; "
     "timeshift --list | grep -q 'Before: apt'"),
    ("snapshots in the boot menu", "for i in $(seq 60); do grep -q 'snapshots' "
     "/boot/grub/grub-btrfs.cfg 2>/dev/null && exit 0; sleep 2; done; exit 1"),
    ("desktop sounds installed", "test -s /usr/share/sounds/aurora/startup.wav"),
    ("apt sources written", "grep -rq trixie /etc/apt/sources.list.d/"),
]


def check_installed(args, disk, out, results):
    vm = VM(args, disk, None, out, f"installed-{args.firmware}")
    try:
        # Catch GRUB's menu: open the snapshots submenu for the website's screenshot.
        time.sleep(4 if args.firmware == "bios" else 8)
        vm.keys("down")
        time.sleep(1)
        vm.shot("grub")
        vm.keys("up", "ret")
        up = vm.wait_agent()
        results.append(("installed system boots", up, ""))
        if not up:
            return
        time.sleep(20)
        # The login screen (or the desktop with autologin).
        vm.shot("login")
        for desc, command in CHECKS:
            code, output = vm.run(command, timeout=300)
            results.append((desc, code == 0, output.strip()[:200]))
        if args.firmware == "uefi":
            mode = "shim-no-nvram" if args.hyperv_identity else "shim"
            code, output = vm.run(f"test \"$(cat /var/lib/aurora/efi-managed)\" = {mode}")
            results.append((f"EFI mode is {mode}", code == 0, output))
            # Both paths complete: shim + signed GRUB in \EFI\debian and \EFI\BOOT,
            # the config GRUB reads in \EFI\debian, no fallback tool in \EFI\BOOT.
            both = ("cd /boot/efi/EFI && cmp -s BOOT/BOOTX64.EFI debian/shimx64.efi && "
                    "cmp -s BOOT/grubx64.efi debian/grubx64.efi && "
                    "grep -q '^search' debian/grub.cfg && test ! -e BOOT/fbx64.efi")
            code, output = vm.run(both)
            results.append(("both EFI paths hold the signed chain", code == 0, output))
            # Exercise the real package hooks that may overwrite EFI binaries.
            code, output = vm.run("DEBIAN_FRONTEND=noninteractive apt-get install -y --reinstall "
                                  "grub-efi-amd64 grub-efi-amd64-signed shim-signed", timeout=300)
            results.append(("bootloader packages reinstalled", code == 0, output[-500:]))
            code, output = vm.run(f"test \"$(cat /var/lib/aurora/efi-managed)\" = {mode}")
            results.append(("EFI policy survives package reinstall", code == 0, output))
            code, output = vm.run(both)
            results.append(("both EFI paths survive package reinstall", code == 0, output))
            if args.hyperv_identity:
                code, output = vm.run("lsinitramfs /initrd.img | grep -E '/hv_storvsc\\.ko(\\.|$)'")
                results.append(("Hyper-V storage driver in initramfs", code == 0, output))
                # Like a fresh Hyper-V VM (the only way the disk was seen to start
                # there): no firmware entry for this disk, started via \EFI\BOOT.
                code, output = vm.run(
                    "uuid=$(lsblk -no PARTUUID $(findmnt -no SOURCE /boot/efi)); "
                    "! efibootmgr -v | grep -qi \"$uuid\"")
                results.append(("no firmware boot entry written on Hyper-V", code == 0, output))
        _c, grubcfg = vm.run("cat /boot/grub/grub-btrfs.cfg 2>/dev/null | head -60")
        with open(os.path.join(out, f"grub-btrfs-{args.firmware}.cfg"), "w") as f:
            f.write(grubcfg)
        vm.run("sync", timeout=120)
    finally:
        vm.stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--firmware", choices=["bios", "uefi"], default="bios")
    ap.add_argument("--out", default="work/install-test")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds allowed for installing")
    ap.add_argument("--keep-disk", action="store_true")
    ap.add_argument("--hyperv-identity", action="store_true",
                    help="exercise Hyper-V EFI policy using QEMU SMBIOS (not Hyper-V firmware)")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    disk = os.path.join(out, f"disk-{args.firmware}.qcow2")
    if os.path.exists(disk):
        ap.error(f"refusing to overwrite existing test disk: {disk}")
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", disk, DISK_SIZE], check=True)

    results = []
    if install(args, disk, out, results):
        check_installed(args, disk, out, results)
        if args.firmware == "uefi":
            for name in ("after-efi-update-nvram", "after-efi-update"):
                vm = VM(args, disk, None, out, name)
                try:
                    up = vm.wait_agent()
                    results.append((f"boots {name}", up, ""))
                    if up and args.hyperv_identity and name.endswith("-nvram"):
                        code, output = vm.run(
                            "uuid=$(lsblk -no PARTUUID $(findmnt -no SOURCE /boot/efi)); "
                            "! efibootmgr -v | grep -qi \"$uuid\"")
                        results.append(("updates write no firmware boot entry", code == 0, output))
                    if up:
                        vm.run("sync", timeout=120)
                finally:
                    vm.stop()
    if not args.keep_disk:
        os.remove(disk)

    failed = 0
    for desc, ok, detail in results:
        print(f"{'ok' if ok else 'FAILED'}: {desc}" + (f"  ({detail})" if detail and not ok else ""))
        failed += not ok
    print(f"\n{len(results) - failed}/{len(results)} checks passed (install, {args.firmware})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
