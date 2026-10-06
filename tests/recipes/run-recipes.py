#!/usr/bin/env python3
"""Run every Dev Hub and Game Hub recipe on an installed Aurora, and record
whether the tool ends up installed.

Runs inside the test VM as the desktop user (sudo without a password there),
one recipe at a time, each with a time limit:

    python3 run-recipes.py [--only id,id] [--skip id,id] [--out FILE]

Each line of the output (JSON) says: id, name, ok (installed after the
recipe), rc (the script's exit code), seconds, and the end of its log.
Recipes whose services reach out on their own (Tailscale joins its VPN) are
skipped by default: company firewalls flag them.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.environ.get("AURORA_LIBDIR", "/usr/lib/aurora"))

from aurora.devhub import games, recipes  # noqa: E402

SKIP = {"tailscale"}
TIMEOUT = 40 * 60


def check(recipe):
    try:
        return subprocess.run(["bash", "-c", recipe["check"]], capture_output=True,
                              timeout=30).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def run(recipe):
    fd, path = tempfile.mkstemp(prefix=f"recipe-{recipe['id']}-", suffix=".sh")
    with os.fdopen(fd, "w") as f:
        f.write("#!/bin/bash\nset -euo pipefail\nexport DEBIAN_FRONTEND=noninteractive\n")
        f.write(recipe["script"])
    start = time.time()
    try:
        proc = subprocess.run(["bash", path], capture_output=True, text=True,
                              timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        rc, log = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as err:
        rc, log = "timeout", (err.stdout or b"").decode(errors="replace") if isinstance(
            err.stdout, bytes) else (err.stdout or "")
    os.remove(path)
    return rc, log, time.time() - start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--skip", default="")
    ap.add_argument("--out", default="/var/tmp/recipes.jsonl")
    args = ap.parse_args()
    only = {x for x in args.only.split(",") if x}
    skip = SKIP | {x for x in args.skip.split(",") if x}
    done = set()
    if os.path.exists(args.out):
        with open(args.out) as f:
            done = {json.loads(line)["id"] for line in f if line.strip()}
    for recipe in recipes.RECIPES + games.RECIPES:
        rid = recipe["id"]
        if (only and rid not in only) or rid in skip or rid in done:
            continue
        before = check(recipe)
        rc, log, seconds = run(recipe)
        ok = check(recipe)
        result = {"id": rid, "name": recipe["name"], "ok": ok, "rc": rc,
                  "already": before, "seconds": round(seconds),
                  "log": log[-3000:] if not ok or rc != 0 else log[-300:]}
        with open(args.out, "a") as f:
            f.write(json.dumps(result) + "\n")
        print(f"{'OK ' if ok and rc == 0 else 'FAIL'} {rid} ({round(seconds)} s)", flush=True)


if __name__ == "__main__":
    main()
