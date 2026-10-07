"""Desktop application lookup and launching."""

import os
import stat

from gi.repository import Gdk, Gio, GLib

_by_wmclass = None


def all_apps():
    return [a for a in Gio.AppInfo.get_all()
            if isinstance(a, Gio.DesktopAppInfo) and a.should_show()]


def _wmclass_index():
    global _by_wmclass
    if _by_wmclass is None:
        _by_wmclass = {}
        for app in Gio.AppInfo.get_all():
            if isinstance(app, Gio.DesktopAppInfo):
                wmclass = app.get_startup_wm_class()
                if wmclass:
                    _by_wmclass[wmclass.lower()] = app
    return _by_wmclass


def invalidate():
    global _by_wmclass
    _by_wmclass = None


def find_app(app_id):
    """Map a Wayland app_id (or X11 class) to a DesktopAppInfo."""
    if not app_id:
        return None
    candidates = [app_id, app_id.lower()]
    if "." in app_id:
        candidates.append(app_id.rsplit(".", 1)[-1].lower())
    for cand in candidates:
        try:
            info = Gio.DesktopAppInfo.new(cand + ".desktop")
        except TypeError:
            info = None
        if info:
            return info
    info = _wmclass_index().get(app_id.lower())
    if info:
        return info
    for group in Gio.DesktopAppInfo.search(app_id):
        for desktop_id in group:
            info = Gio.DesktopAppInfo.new(desktop_id)
            if info:
                return info
    return None


def app_by_id(desktop_id):
    try:
        return Gio.DesktopAppInfo.new(desktop_id)
    except TypeError:
        return None


def launch(app, files=None, action=None):
    display = Gdk.Display.get_default()
    ctx = display.get_app_launch_context() if display else None
    try:
        if action:
            app.launch_action(action, ctx)
        elif files:
            app.launch([Gio.File.new_for_path(f) for f in files], ctx)
        else:
            app.launch([], ctx)
        return True
    except GLib.Error as err:
        print(f"aurora: failed to launch {app.get_id()}: {err.message}")
        return False


def spawn(argv):
    """Start a detached process, ignoring failures."""
    try:
        GLib.spawn_async(argv, flags=GLib.SpawnFlags.SEARCH_PATH)
        return True
    except GLib.Error as err:
        print(f"aurora: failed to run {argv[0]}: {err.message}")
        return False


def spawn_shell(command):
    return spawn(["sh", "-c", command])


def special_file(path):
    """A pipe, socket or device: opening one to read waits until something
    writes to it, forever for a pipe nobody uses. Nothing to open or preview."""
    try:
        mode = os.stat(path).st_mode
    except (OSError, TypeError, ValueError):
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode)
