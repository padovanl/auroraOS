"""Read and revoke per-app grants from the portal permission store.

Static manifest permissions are displayed separately: removing a remembered
portal decision cannot override broad filesystem access in an app manifest.
"""

import subprocess

from gi.repository import Gio, GLib

TABLES = ("documents", "devices", "screencast", "remote-desktop")
BUS = "org.freedesktop.impl.portal.PermissionStore"
PATH = "/org/freedesktop/impl/portal/PermissionStore"


def installed_apps():
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application,name"],
            capture_output=True, text=True, timeout=8, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    apps = []
    for line in result.stdout.splitlines():
        app_id, _, name = line.partition("\t")
        if app_id and app_id != "Application ID":
            apps.append((app_id, name or app_id))
    return apps


def _store():
    return Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None, BUS, PATH, BUS, None)


def grants(app_id):
    try:
        proxy = _store()
    except GLib.Error:
        return []
    found = []
    for table in TABLES:
        try:
            ids = proxy.call_sync("List", GLib.Variant("(s)", (table,)),
                                  Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
        except GLib.Error:
            continue
        for object_id in ids[:300]:
            try:
                values = proxy.call_sync(
                    "GetPermission", GLib.Variant("(sss)", (table, object_id, app_id)),
                    Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
                if values:
                    found.append((table, object_id, ", ".join(values)))
            except GLib.Error:
                continue
    return found


def declared(app_id):
    try:
        result = subprocess.run(["flatpak", "info", "--show-permissions", app_id],
                                capture_output=True, text=True, timeout=8, check=True)
        return result.stdout[:8000]
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def revoke(table, object_id, app_id):
    if table not in TABLES or not app_id or not object_id:
        return False
    try:
        return subprocess.run(["flatpak", "permission-remove", table, object_id, app_id],
                              capture_output=True, timeout=8).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
