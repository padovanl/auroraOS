"""Bluetooth and Printers pages."""

import shutil

from gi.repository import Adw, Gio, GLib, Gtk

from aurora import apps
from aurora.i18n import _
from aurora.settingsapp.util import Page, run, switch_row, toast

BLUEZ = "org.bluez"


class Bluetooth(Page):
    page_id = "bluetooth"
    title = _("Bluetooth")
    icon_name = "bluetooth-active-symbolic"

    def build(self):
        self.manager = None
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self.manager = Gio.DBusObjectManagerClient.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START, BLUEZ, "/",
                None, None, None)
        except GLib.Error:
            pass
        self.main = self.group()
        self.devices = self.group(_("Devices"))
        self._rows = []
        adapter = self._adapter()
        if adapter is None:
            self.main.add(Adw.ActionRow(title=_("No Bluetooth adapter found")))
            self.devices.set_visible(False)
            return
        self.adapter_path = adapter
        powered = self._prop(adapter, "org.bluez.Adapter1", "Powered")
        self.power = switch_row(_("Bluetooth"), bool(powered),
                                lambda v: self._set_prop(adapter, "org.bluez.Adapter1",
                                                         "Powered", GLib.Variant("b", v)))
        self.main.add(self.power)
        scan = Gtk.Button(label=_("Search"), css_classes=["flat"])
        scan.connect("clicked", lambda *_: self._discover())
        self.devices.set_header_suffix(scan)
        more = Adw.ButtonRow(title=_("Advanced Bluetooth Settings…"))
        more.connect("activated", lambda *_: apps.spawn(["blueman-manager"]))
        self.main.add(more)
        self.manager.connect("object-added", lambda *a: self.refresh())
        self.manager.connect("object-removed", lambda *a: self.refresh())
        self.manager.connect("interface-proxy-properties-changed", lambda *a: self.refresh())
        self.refresh()

    def _adapter(self):
        if self.manager is None:
            return None
        for obj in self.manager.get_objects():
            if obj.get_interface("org.bluez.Adapter1"):
                return obj.get_object_path()
        return None

    def _prop(self, path, iface, name):
        obj = self.manager.get_object(path)
        proxy = obj.get_interface(iface) if obj else None
        v = proxy.get_cached_property(name) if proxy else None
        return v.unpack() if v is not None else None

    def _set_prop(self, path, iface, name, value):
        self.bus.call(BLUEZ, path, "org.freedesktop.DBus.Properties", "Set",
                      GLib.Variant("(ssv)", (iface, name, value)), None,
                      Gio.DBusCallFlags.NONE, -1, None, None)

    def _call(self, path, method, done_msg=None):
        def finish(bus, res):
            try:
                bus.call_finish(res)
                if done_msg:
                    toast(self, done_msg)
            except GLib.Error as err:
                toast(self, err.message.split(":")[-1].strip())
            self.refresh()
        self.bus.call(BLUEZ, path, "org.bluez.Device1", method, None, None,
                      Gio.DBusCallFlags.NONE, 60000, None, finish)

    def _discover(self):
        self.bus.call(BLUEZ, self.adapter_path, "org.bluez.Adapter1", "StartDiscovery", None,
                      None, Gio.DBusCallFlags.NONE, -1, None, None)
        GLib.timeout_add_seconds(20, lambda: self.bus.call(
            BLUEZ, self.adapter_path, "org.bluez.Adapter1", "StopDiscovery", None, None,
            Gio.DBusCallFlags.NONE, -1, None, None) and False)

    def refresh(self):
        for r in self._rows:
            self.devices.remove(r)
        self._rows = []
        for obj in self.manager.get_objects():
            dev = obj.get_interface("org.bluez.Device1")
            if dev is None:
                continue
            path = obj.get_object_path()

            def prop(n, dev=dev):
                v = dev.get_cached_property(n)
                return v.unpack() if v is not None else None
            name = prop("Alias") or prop("Name")
            if not name:
                continue
            connected, paired = prop("Connected"), prop("Paired")
            row = Adw.ActionRow(title=name, subtitle=_("Connected") if connected else
                                _("Paired") if paired else _("Not set up"))
            row.add_prefix(Gtk.Image(icon_name=(prop("Icon") or "bluetooth") + "-symbolic"))
            if connected:
                b = Gtk.Button(label=_("Disconnect"), valign=Gtk.Align.CENTER)
                b.connect("clicked", lambda _b, p=path: self._call(p, "Disconnect"))
            elif paired:
                b = Gtk.Button(label=_("Connect"), valign=Gtk.Align.CENTER)
                b.connect("clicked", lambda _b, p=path: self._call(p, "Connect"))
            else:
                b = Gtk.Button(label=_("Pair"), valign=Gtk.Align.CENTER,
                               css_classes=["suggested-action"])
                b.connect("clicked", lambda _b, p=path: self._call(p, "Pair", _("Paired")))
            row.add_suffix(b)
            self.devices.add(row)
            self._rows.append(row)
        return GLib.SOURCE_REMOVE


class Printers(Page):
    page_id = "printers"
    title = _("Printers")
    icon_name = "printer-symbolic"

    def build(self):
        g = self.group(_("Printers"), _("Most network and USB printers are found automatically."))
        out = run(["lpstat", "-e"]).split()
        default = run(["lpstat", "-d"]).split(":")[-1].strip()
        if not out:
            g.add(Adw.ActionRow(title=_("No printers")))
        for name in out:
            row = Adw.ActionRow(title=name.replace("_", " "),
                                subtitle=_("Default") if name == default else "")
            row.add_prefix(Gtk.Image(icon_name="printer-symbolic"))
            if name != default:
                b = Gtk.Button(label=_("Make Default"), valign=Gtk.Align.CENTER, css_classes=["flat"])
                b.connect("clicked", lambda _b, n=name: (run(["lpoptions", "-d", n]),
                                                         toast(self, _("Default printer changed"))))
                row.add_suffix(b)
            g.add(row)
        if shutil.which("system-config-printer"):
            add = Adw.ButtonRow(title=_("Add or Configure Printers…"))
            add.connect("activated", lambda *_: apps.spawn(["system-config-printer"]))
            g.add(add)
