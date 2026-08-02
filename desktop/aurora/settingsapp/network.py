"""Network: connection status, Wi-Fi networks (share one with a QR code), VPNs."""

import subprocess

from gi.repository import Adw, Gdk, GLib, Gtk

from aurora import apps
from aurora.i18n import _
from aurora.settingsapp.util import Page, switch_row, toast
from aurora.shell.services import Network as NetworkService


def wifi_qr_payload(ssid, password, security="WPA"):
    """The standard Wi-Fi QR text phones understand (camera app → join)."""
    def esc(v):
        return "".join("\\" + c if c in '\\;,:"' else c for c in v)
    if not password:
        return f"WIFI:T:nopass;S:{esc(ssid)};;"
    return f"WIFI:T:{security};S:{esc(ssid)};P:{esc(password)};;"


def qr_svg(text):
    import io
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathFillImage, box_size=12,
                      border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


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
                share = Gtk.Button(icon_name="qr-code-symbolic", valign=Gtk.Align.CENTER,
                                   css_classes=["flat"], tooltip_text=_("Share Wi-Fi"))
                share.connect("clicked", lambda *_: self._share(entry["ssid"]))
                row.add_suffix(share)
                row.add_suffix(Gtk.Image(icon_name="object-select-symbolic"))
        row.add_prefix(Gtk.Image(icon_name=f"network-wireless-signal-{level}-symbolic"))
        self.wifi_group.add(row)
        return row

    def _connect(self, entry, password):
        def done(ok):
            toast(self, _("Connected to {ssid}").format(ssid=entry["ssid"]) if ok
                  else _("Could not connect to {ssid}").format(ssid=entry["ssid"]))
        self.net.connect_to(entry, password, done)

    def _share(self, ssid):
        conn = self.net.known_connection(ssid)
        name = conn.get_id() if conn is not None else ssid
        password = subprocess.run(["nmcli", "-s", "-g", "802-11-wireless-security.psk",
                                   "connection", "show", name],
                                  capture_output=True, text=True).stdout.strip()
        try:
            svg = qr_svg(wifi_qr_payload(ssid, password))
        except ImportError:
            toast(self, _("QR codes need the python3-qrcode package"))
            return
        texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(svg))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12,
                      margin_bottom=18, margin_start=24, margin_end=24)
        pic = Gtk.Picture(paintable=texture, can_shrink=True, width_request=260,
                          height_request=260)
        box.append(pic)
        box.append(Gtk.Label(label=_("Point a phone's camera at the code to join “{ssid}”.").format(
            ssid=ssid), wrap=True, justify=Gtk.Justification.CENTER))
        if password:
            box.append(Gtk.Label(label=_("Password: {p}").format(p=password), selectable=True,
                                 css_classes=["dim-label"]))
        dialog = Adw.Dialog(title=_("Share Wi-Fi"), content_width=340)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(Adw.HeaderBar())
        dialog.set_child(view)
        dialog.present(self.get_root())
