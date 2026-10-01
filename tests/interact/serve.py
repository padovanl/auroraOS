#!/usr/bin/env python3
"""Keep an Aurora VM running and drive it step by step (for exploring by hand).

    tests/interact/serve.py ISO OUT_DIR [--firmware uefi]     # boots and waits
    tests/interact/do.py 'vm.click(953, 1037)' 'vm.shot("dock")'

Each expression is evaluated with `vm` (a tests/interact/vm.VM) and its result is
printed. The socket lives at /tmp/aurora-interact.sock, or at
$AURORA_INTERACT_SOCK to drive several VMs at once.
"""

import argparse
import os
import socket
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vm import VM  # noqa: E402

SOCK = os.environ.get("AURORA_INTERACT_SOCK", "/tmp/aurora-interact.sock")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("out")
    ap.add_argument("--firmware", default="bios")
    ap.add_argument("--vga", default="virtio-vga")
    ap.add_argument("--disk", default="", help="an empty virtual disk (qcow2, created if "
                    "missing), so the installer has somewhere to install")
    ap.add_argument("--grub-keys", default="",
                    help="keys for the boot menu, e.g. down,down,ret for safe graphics")
    args = ap.parse_args()
    vm = VM(args.iso, args.out, args.firmware, args.vga,
            [k for k in args.grub_keys.split(",") if k], disk=args.disk)
    if os.path.exists(SOCK):
        os.remove(SOCK)
    server = socket.socket(socket.AF_UNIX)
    server.bind(SOCK)
    server.listen(1)
    print("ready", flush=True)
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                expr = conn.makefile().readline().strip()
                if expr == "quit":
                    break
                try:
                    result = repr(eval(expr, {"vm": vm}))  # noqa: S307 - local tool
                except Exception:  # noqa: BLE001
                    result = traceback.format_exc()
                conn.sendall(result.encode() + b"\n")
    finally:
        vm.close()
        os.remove(SOCK)


if __name__ == "__main__":
    main()
