"""Small, scoped controls for the active Aurora compositor."""

import os
import signal
import subprocess


def is_wayfire():
    return os.environ.get("AURORA_COMPOSITOR") == "wayfire"


def refresh():
    if is_wayfire():
        from aurora.wayfireconf import generate
        generate()
    else:
        subprocess.run(["labwc", "--reconfigure"], stderr=subprocess.DEVNULL, check=False)


def logout():
    if not is_wayfire():
        subprocess.Popen(["labwc", "--exit"], stderr=subprocess.DEVNULL)
        return
    pidfile = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "aurora-wayfire.pid")
    try:
        with open(pidfile, encoding="ascii") as stream:
            pid = int(stream.read().strip())
        if pid > 1:
            with open(f"/proc/{pid}/comm", encoding="ascii") as stream:
                if stream.read().strip() == "wayfire":
                    os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass
