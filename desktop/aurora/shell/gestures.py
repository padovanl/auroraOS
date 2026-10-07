"""Touchpad gestures, like a Mac's:

    three fingers up        show all windows (overview)
    three fingers down      show the desktop
    three fingers left/right  previous / next workspace
    pinch with four fingers  Launchpad

labwc 0.8 doesn't handle touchpad gestures, so the shell reads them from
`libinput debug-events` (the user is in the `input` group) and acts. Workspace
switches press labwc's own shortcut (Ctrl+Alt+Left/Right) through `wtype`.
"""

import re
import shutil
import subprocess
import threading

from aurora import apps

from gi.repository import GLib

SWIPE_DISTANCE = 120      # accumulated libinput units before a swipe counts
PINCH_SCALE = 0.7         # fingers closing to 70 % of their distance

LINE = re.compile(r"^\s*\S+\s+(GESTURE_(?:SWIPE|PINCH)_(?:BEGIN|UPDATE|END))\s+\S+\s+(\d+)"
                  r"(?:\s+(-?[\d.]+)/\s*(-?[\d.]+))?(?:.*?\s(-?[\d.]+)\s*@)?")


def parse(line):
    """→ (event, fingers, dx, dy, scale) or None. `libinput debug-events` lines:
    ' event7  GESTURE_SWIPE_UPDATE  +1.2s  3  2.50/-0.30 ( 5.00/-0.60 unaccelerated)'
    ' event7  GESTURE_PINCH_UPDATE  +1.2s  4  0.10/ 0.20 ( ...) 0.85 @ 0.00'"""
    m = LINE.match(line)
    if not m:
        return None
    event, fingers = m.group(1), int(m.group(2))
    dx = float(m.group(3)) if m.group(3) else 0.0
    dy = float(m.group(4)) if m.group(4) else 0.0
    scale = float(m.group(5)) if m.group(5) else 1.0
    return event, fingers, dx, dy, scale


class Recognizer:
    """Turns a stream of parsed events into actions ('overview', 'desktop',
    'workspace-left', 'workspace-right', 'launchpad')."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.kind, self.fingers, self.x, self.y, self.scale = None, 0, 0.0, 0.0, 1.0

    def feed(self, parsed):
        event, fingers, dx, dy, scale = parsed
        if event.endswith("BEGIN"):
            self.reset()
            self.kind = "swipe" if "SWIPE" in event else "pinch"
            self.fingers = fingers
            return None
        if event.endswith("UPDATE"):
            self.x += dx
            self.y += dy
            self.scale = scale if "PINCH" in event else self.scale
            return None
        action = self._decide()
        self.reset()
        return action

    def _decide(self):
        if self.kind == "pinch" and self.fingers >= 4 and self.scale < PINCH_SCALE:
            return "launchpad"
        if self.kind != "swipe" or self.fingers != 3:
            return None
        if max(abs(self.x), abs(self.y)) < SWIPE_DISTANCE:
            return None
        if abs(self.y) > abs(self.x):
            return "overview" if self.y < 0 else "desktop"
        # Content follows the fingers: swiping left brings the next workspace.
        return "workspace-right" if self.x < 0 else "workspace-left"


class Gestures:
    def __init__(self, shell):
        self.shell = shell
        self.proc = None

    def start(self):
        if self.proc is not None or not shutil.which("libinput"):
            return
        try:
            self.proc = subprocess.Popen(apps.tied(["libinput", "debug-events"]),
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, text=True)
        except OSError:
            return
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def stop(self):
        if self.proc is not None:
            self.proc.terminate()
            self.proc = None

    def _read(self, proc):
        rec = Recognizer()
        for line in proc.stdout:
            parsed = parse(line)
            if parsed is None:
                continue
            action = rec.feed(parsed)
            if action:
                GLib.idle_add(self._act, action)

    def _act(self, action):
        shell = self.shell
        if action == "overview":
            shell.overview.toggle()
        elif action == "desktop":
            shell.overview.show_desktop()
        elif action == "launchpad":
            shell.launcher.toggle("grid")
        elif action.startswith("workspace-"):
            key = "Right" if action.endswith("right") else "Left"
            subprocess.Popen(["wtype", "-M", "ctrl", "-M", "alt", "-k", key,
                              "-m", "alt", "-m", "ctrl"])
        return False
