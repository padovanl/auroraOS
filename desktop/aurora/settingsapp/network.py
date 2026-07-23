"""Network: connection status, Wi-Fi networks, airplane mode."""

from gi.repository import Adw, GLib, Gtk

from aurora import apps
from aurora.i18n import _
from aurora.settingsapp.util import Page, switch_row, toast
from aurora.shell.services import Network as NetworkService


class Network(Page):
    page_id = "network"
    title = _("Network")
    icon_name = "network-wireless-symbolic"

    def build(self):
        self.net = NetworkService()
        self.status_group = self.group(_("Status"))
        advanced = self.group(_("VPN and Advanced"),
                              _("VPNs (WireGuard, OpenVPN, OpenConnect), static IP addresses, "
                                "proxies, hotspots and every other connection option."))
        editor = Adw.ButtonRow(title=_("Open Connection Editor…"))
        editor.connect("activated", lambda *_: apps.spawn(["nm-connection-editor"]))
        advanced.add(editor)
        self.wifi_group = self.group(_("Wi-Fi"))
        self._status_rows = []
        self._wifi_rows = []
        if self.net.client is None:
            self.status_group.add(Adw.ActionRow(title=_("NetworkManager is not running")))
            return
        self.wifi_switch = switch_row(_("Wi-Fi"), self.net.wifi_enabled,
                                      self.net.set_wifi_enabled)
        self.wifi_group.add(self.wifi_switch)
        scan = Gtk.Button(icon_name="view-refresh-symbolic", css_classes=["flat"],
                          tooltip_text=_("Scan"))
        scan.connect("clicked", lambda *_: self.net.scan())
        self.wifi_group.set_header_suffix(scan)
        self.net.connect("changed", lambda *_: GLib.idle_add(self.refresh))
        self.refresh()

    def refresh(self):
        for row in self._status_rows:
            self.status_group.remove(row)
        for row in self._wifi_rows:
            self.wifi_group.remove(row)
        self._status_rows, self._wifi_rows = [], []

        for dev in self.net.client.get_devices():
            iface = dev.get_iface()
            if iface == "lo" or not dev.get_managed():
                continue
            conn = dev.get_active_connection()
            state = conn.get_id() if conn else _("Disconnected")
            ip4 = dev.get_ip4_config()
            addr = ""
            if ip4 and ip4.get_addresses():
                addr = ip4.get_addresses()[0].get_address()
            row = Adw.ActionRow(title=f"{dev.get_description() or iface}",
                                subtitle=" · ".join(x for x in (iface, state, addr) if x))
            kind = dev.get_device_type()
            icon = "network-wireless-symbolic" if kind == self.net.NM.DeviceType.WIFI \
                else "network-wired-symbolic"
            row.add_prefix(Gtk.Image(icon_name=icon))
            self.status_group.add(row)
            self._status_rows.append(row)

        self.wifi_group.set_visible(self.net.wifi_device() is not None)
        self.wifi_switch.set_active(self.net.wifi_enabled)
        if not self.net.wifi_enabled:
            return
        for entry in self.net.access_points():
            self._wifi_rows.append(self._wifi_row(entry))
        return GLib.SOURCE_REMOVE

    def _wifi_row(self, entry):
        level = ("excellent" if entry["strength"] > 75 else "good" if entry["strength"] > 50
                 else "ok" if entry["strength"] > 25 else "weak")
        if entry["secure"] and not entry["active"] and \
                self.net.known_connection(entry["ssid"]) is None:
            row = Adw.PasswordEntryRow(title=entry["ssid"], show_apply_button=True)
            row.connect("apply", lambda r: self._connect(entry, r.get_text()))
        else:
            row = Adw.ActionRow(title=entry["ssid"], activatable=not entry["active"])
            row.connect("activated", lambda *_: self._connect(entry, None))
            if entry["active"]:
                row.set_subtitle(_("Connected"))
                row.add_suffix(Gtk.Image(icon_name="object-select-symbolic"))
        row.add_prefix(Gtk.Image(icon_name=f"network-wireless-signal-{level}-symbolic"))
        self.wifi_group.add(row)
        return row

    def _connect(self, entry, password):
        def done(ok):
            toast(self, _("Connected to {ssid}").format(ssid=entry["ssid"]) if ok
                  else _("Could not connect to {ssid}").format(ssid=entry["ssid"]))
        self.net.connect_to(entry, password, done)
