"""Mounting disks from the sidebar, with a read-only retry for Windows.

Windows leaves its NTFS partition marked as in use when Fast Startup (on by
default) or hibernation is on, or when a disk check is pending (installing
Aurora next to Windows schedules one); Linux then refuses to mount it for
writing. The files are still readable: mount it read-only through UDisks and
say why, instead of failing without a word.
"""

from gi.repository import Gio, GLib

UDISKS = "org.freedesktop.UDisks2"
WINDOWS_TYPES = ("ntfs", "ntfs3")


def block_object_path(device):
    """/dev/nvme0n1p3 → UDisks' object path for that block device."""
    name = device.rsplit("/", 1)[-1]
    escaped = "".join(c if c.isalnum() else f"_{ord(c):02x}" for c in name)
    return f"/org/freedesktop/UDisks2/block_devices/{escaped}"


def is_cancelled(err):
    """The person closed the password prompt: nothing to report."""
    if (err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.FAILED_HANDLED)
            or err.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED)):
        return True
    return (Gio.DBusError.get_remote_error(err) or "").endswith("NotAuthorizedDismissed")


def filesystem_type(device):
    """The file system UDisks sees on a block device ('ntfs', 'ext4'…), or ''."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        reply = bus.call_sync(UDISKS, block_object_path(device),
                              "org.freedesktop.DBus.Properties", "Get",
                              GLib.Variant("(ss)", ("org.freedesktop.UDisks2.Block", "IdType")),
                              GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 3000, None)
        return reply.unpack()[0]
    except GLib.Error:
        return ""


def mount(device, callback, read_only=False):
    """Mount a block device through UDisks; callback(mount_point or None, error).

    One system-bus connection for every call: the password, once given,
    covers the read-only retry too (polkit keeps it per connection)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    except GLib.Error as err:
        callback(None, err)
        return

    def done(conn, res):
        try:
            path = conn.call_finish(res).unpack()[0]
        except GLib.Error as err:
            callback(None, err)
            return
        callback(path, None)
    options = {"auth.no_user_interaction": GLib.Variant("b", False)}
    if read_only:
        options["options"] = GLib.Variant("s", "ro")
    bus.call(UDISKS, block_object_path(device), "org.freedesktop.UDisks2.Filesystem", "Mount",
             GLib.Variant("(a{sv})", (options,)), GLib.VariantType("(s)"),
             Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 120000, None, done)


def mount_windows(device, callback):
    """Mount Windows' partition, read-only when Windows left it in use.
    callback(mount_point or None, error or None, read_only)."""
    def first(path, err):
        if path is not None or is_cancelled(err):
            callback(path, err, False)
            return
        mount(device, lambda p, e: callback(p, err if p is None else None, True),
              read_only=True)
    mount(device, first)
