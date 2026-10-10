"""Real pictures of the open windows, for the overview, the dock and Snap Assist.

No Wayland protocol here hands one client the contents of another client's
window: wlr-screencopy copies a whole output, and per-window capture
(ext-image-copy-capture) landed in wlroots after the version Debian 13 carries.
So a preview is a crop of the screen taken while the window was on top of it —
the moment its pixels really are on screen — and kept for when it isn't. That
is also what the big desktops show you: the window as you last saw it.

Wayfire says where the focused window is (window-rules/get-focused-view);
labwc has no such interface, so the compatibility session has no previews and
the cards keep their app icons.
"""

import collections
import os
import time

from gi.repository import Gdk, GdkPixbuf, Gio, GLib

from aurora import compositor, settings, wayfirelayout

MAX_SHOTS = 14          # windows remembered; a 480px wide crop is ~1 MB
SHOT_WIDTH = 480        # wide enough for an overview card on a 4K screen
SETTLE_MS = 700         # after the focus lands: let the window finish drawing
MIN_GAP = 1.5           # seconds between two captures of the same window


def available():
    """Previews need Wayfire's IPC (for the geometry) and grim (for the pixels)."""
    return (compositor.is_wayfire() and bool(os.environ.get("WAYFIRE_SOCKET"))
            and GLib.find_program_in_path("grim") is not None)


def enabled():
    s = settings.get()
    if s is None:
        return available()
    return available() and s.get_boolean("window-previews")


class Previews:
    """Keeps one picture per window, taken when that window was in front."""

    def __init__(self, shell):
        self.shell = shell
        self._shots = collections.OrderedDict()   # (app_id, title) -> Gdk.Texture
        self._taken = {}                          # key -> when, so focus churn is cheap
        self._pending = 0
        self._busy = False
        if available():
            shell.toplevels.connect("changed", lambda *_a: self._schedule())
            s = settings.get()
            if s is not None:
                s.connect("changed::window-previews", lambda *_a: self._setting_changed())
            self._schedule()

    def _setting_changed(self):
        if not enabled():
            self._shots.clear()
            self._taken.clear()
        else:
            self._schedule()

    # --- lookup ---

    def get(self, toplevel):
        """The picture of this window, the newest one of its app, or None."""
        if not enabled() or toplevel is None:
            return None
        shot = self._shots.get((toplevel.app_id, toplevel.title))
        if shot is not None:
            return shot
        for (app_id, _title), texture in reversed(self._shots.items()):
            if app_id == toplevel.app_id:
                return texture
        return None

    def for_view(self, view):
        """The same, from a Wayfire view dictionary (Snap Assist works on those)."""
        if not enabled() or not isinstance(view, dict):
            return None
        shot = self._shots.get((view.get("app-id") or "", view.get("title") or ""))
        if shot is not None:
            return shot
        for (app_id, _title), texture in reversed(self._shots.items()):
            if app_id == (view.get("app-id") or ""):
                return texture
        return None

    # --- capturing ---

    def _schedule(self):
        """Something changed: capture the window in front once it settles."""
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(SETTLE_MS, self._capture_focused)

    def _busy_shell(self):
        """Our own overlays would be in the picture, so don't take one."""
        for name in ("overview", "launcher", "shortcuts_overlay", "snap"):
            surface = getattr(self.shell, name, None)
            if surface is not None and surface.get_visible():
                return True
        return False

    def _capture_focused(self):
        self._pending = 0
        if not enabled() or self._busy or self._busy_shell():
            return GLib.SOURCE_REMOVE
        try:
            info = (wayfirelayout.request("window-rules/get-focused-view") or {}).get("info")
        except (OSError, ValueError, ConnectionError):
            return GLib.SOURCE_REMOVE
        if not isinstance(info, dict) or not info.get("mapped", True):
            return GLib.SOURCE_REMOVE
        if info.get("minimized") or info.get("app-id") == "org.aurora.Shell":
            return GLib.SOURCE_REMOVE
        # bbox: where the window really is on the screen, decorations and all.
        geometry = info.get("bbox") or info.get("geometry") or {}
        key = (info.get("app-id") or "", info.get("title") or "")
        if not key[0]:
            return GLib.SOURCE_REMOVE
        if time.monotonic() - self._taken.get(key, 0) < MIN_GAP:
            return GLib.SOURCE_REMOVE
        self._grab(key, geometry)
        return GLib.SOURCE_REMOVE

    def _grab(self, key, geometry):
        try:
            x, y, w, h = (int(geometry[k]) for k in ("x", "y", "width", "height"))
        except (KeyError, TypeError, ValueError):
            return
        if w < 80 or h < 60:
            return
        # A window can hang off the screen; grim refuses a region that does.
        x, y = max(0, x), max(0, y)
        scale = min(1.0, SHOT_WIDTH / float(w))
        argv = ["grim", "-l", "0", "-t", "png", "-s", f"{scale:.3f}",
                "-g", f"{x},{y} {w}x{h}", "-"]
        try:
            proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_PIPE |
                                      Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error as err:
            print(f"aurora: window previews unavailable: {err.message}")
            return
        self._busy = True
        self._taken[key] = time.monotonic()
        proc.communicate_async(None, None, self._grabbed, key)

    def _grabbed(self, proc, result, key):
        self._busy = False
        try:
            ok, out, _err = proc.communicate_finish(result)
        except GLib.Error:
            return
        if not ok or not proc.get_successful() or out is None or out.get_size() == 0:
            return
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write_bytes(out)
            loader.close()
            pixbuf = loader.get_pixbuf()
        except GLib.Error:
            return
        if pixbuf is None:
            return
        self._shots.pop(key, None)
        self._shots[key] = Gdk.Texture.new_for_pixbuf(pixbuf)
        while len(self._shots) > MAX_SHOTS:
            old, _ = self._shots.popitem(last=False)
            self._taken.pop(old, None)

    def count(self):
        """How many windows there is a picture of. Asked by tests, and by
        anyone wondering whether previews are working at all."""
        return len(self._shots)

    def forget_closed(self, open_keys):
        """Drop the pictures of windows that are gone."""
        for key in [k for k in self._shots if k not in open_keys]:
            self._shots.pop(key, None)
            self._taken.pop(key, None)
