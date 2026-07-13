"""System services used by the shell: audio, brightness, battery, network, power."""

import re
import shutil
import subprocess

import gi
from gi.repository import Gio, GLib, GObject

from aurora import apps


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


class Audio(GObject.Object):
    """Default sink volume through wpctl (PipeWire)."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}
    SINK = "@DEFAULT_AUDIO_SINK@"

    def __init__(self):
        super().__init__()
        self.available = shutil.which("wpctl") is not None
        self.volume = 0.0
        self.muted = False
        self.refresh()

    def refresh(self):
        if not self.available:
            return
        out = _run(["wpctl", "get-volume", self.SINK])
        m = re.search(r"Volume:\s*([\d.]+)", out)
        if m:
            self.volume = float(m.group(1))
            self.muted = "[MUTED]" in out
        self.emit("changed")

    def set_volume(self, value):
        value = max(0.0, min(1.0, value))
        _run(["wpctl", "set-volume", self.SINK, f"{value:.2f}"])
        if self.muted and value > 0:
            _run(["wpctl", "set-mute", self.SINK, "0"])
        self.refresh()

    def step(self, delta):
        self.set_volume(self.volume + delta)

    def toggle_mute(self):
        _run(["wpctl", "set-mute", self.SINK, "toggle"])
        self.refresh()

    @property
    def icon_name(self):
        if self.muted or self.volume <= 0:
            return "audio-volume-muted-symbolic"
        if self.volume < 0.34:
            return "audio-volume-low-symbolic"
        if self.volume < 0.67:
            return "audio-volume-medium-symbolic"
        return "audio-volume-high-symbolic"


class Brightness(GObject.Object):
    """Backlight control through brightnessctl (uses logind, no root needed)."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self.level = 1.0
        self.available = False
        if shutil.which("brightnessctl"):
            self.refresh()

    def refresh(self):
        out = _run(["brightnessctl", "--class=backlight", "-m"]).strip()
        parts = out.split(",")
        if len(parts) >= 5 and parts[4].isdigit():
            self.available = True
            self.level = int(parts[2]) / max(1, int(parts[4]))
            self.emit("changed")

    def set_level(self, value):
        value = max(0.01, min(1.0, value))
        _run(["brightnessctl", "--class=backlight", "-q", "set", f"{round(value * 100)}%"])
        self.refresh()

    def step(self, delta):
        self.set_level(self.level + delta)


class Battery(GObject.Object):
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self.present = False
        self.percentage = 0.0
        self.icon_name = "battery-missing-symbolic"
        self.charging = False
        self._device = None
        try:
            gi.require_version("UPowerGlib", "1.0")
            from gi.repository import UPowerGlib
            client = UPowerGlib.Client.new_full(None)
            self._device = client.get_display_device()
            self._device.connect("notify", lambda *a: self._update())
            self._update()
        except (ValueError, ImportError, GLib.Error) as err:
            print(f"aurora: battery status unavailable ({err})")

    def _update(self):
        d = self._device
        self.present = bool(d.props.is_present) and d.props.type == 2  # UP_DEVICE_KIND_BATTERY
        self.percentage = d.props.percentage
        self.icon_name = d.props.icon_name or "battery-missing-symbolic"
        self.charging = d.props.state in (1, 4)  # charging, fully charged
        self.emit("changed")


class Network(GObject.Object):
    """NetworkManager status and Wi-Fi control."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self.client = None
        try:
            gi.require_version("NM", "1.0")
            from gi.repository import NM
            self.NM = NM
            self.client = NM.Client.new(None)
        except (ValueError, ImportError, GLib.Error) as err:
            print(f"aurora: NetworkManager unavailable ({err})")
            return
        for sig in ("notify::primary-connection", "notify::state",
                    "notify::wireless-enabled", "device-added", "device-removed"):
            self.client.connect(sig, lambda *a: self.emit("changed"))
        self._watch_wifi()

    def _watch_wifi(self):
        dev = self.wifi_device()
        if dev is not None:
            dev.connect("notify::active-access-point", lambda *a: self.emit("changed"))
            dev.connect("access-point-added", lambda *a: self.emit("changed"))
            dev.connect("access-point-removed", lambda *a: self.emit("changed"))

    def wifi_device(self):
        if self.client is None:
            return None
        for dev in self.client.get_devices():
            if dev.get_device_type() == self.NM.DeviceType.WIFI:
                return dev
        return None

    @property
    def wifi_enabled(self):
        return self.client is not None and self.client.wireless_get_enabled()

    def set_wifi_enabled(self, enabled):
        if self.client is None:
            return
        # wireless_set_enabled is deprecated; set the property over D-Bus instead.
        self.client.dbus_set_property(
            self.NM.DBUS_PATH, self.NM.DBUS_INTERFACE, "WirelessEnabled",
            GLib.Variant("b", enabled), -1, None, None)

    def status(self):
        """Return (icon_name, label) for the current primary connection."""
        if self.client is None:
            return "network-offline-symbolic", ""
        conn = self.client.get_primary_connection()
        if conn is None:
            if self.client.get_state() == self.NM.State.CONNECTING:
                return "network-wireless-acquiring-symbolic", ""
            return "network-offline-symbolic", ""
        ctype = conn.get_connection_type()
        if ctype == "802-11-wireless":
            ap = self.wifi_device().get_active_access_point() if self.wifi_device() else None
            strength = ap.get_strength() if ap else 0
            level = ("excellent" if strength > 75 else "good" if strength > 50
                     else "ok" if strength > 25 else "weak")
            return f"network-wireless-signal-{level}-symbolic", conn.get_id()
        if ctype in ("802-3-ethernet", "veth"):
            return "network-wired-symbolic", conn.get_id()
        if ctype in ("vpn", "wireguard"):
            return "network-vpn-symbolic", conn.get_id()
        return "network-wired-symbolic", conn.get_id()

    def access_points(self):
        """Visible networks, strongest first, one entry per SSID."""
        dev = self.wifi_device()
        if dev is None:
            return []
        active = dev.get_active_access_point()
        best = {}
        for ap in dev.get_access_points():
            ssid = ap.get_ssid()
            if ssid is None:
                continue
            name = self.NM.utils_ssid_to_utf8(ssid.get_data())
            if not name:
                continue
            if name not in best or ap.get_strength() > best[name].get_strength():
                best[name] = ap
        result = []
        for name, ap in best.items():
            # NM_802_11_AP_FLAGS_PRIVACY == 1 (the enum name is not a valid identifier)
            secure = ap.get_wpa_flags() != 0 or ap.get_rsn_flags() != 0 or \
                (int(ap.get_flags()) & 1) != 0
            is_active = active is not None and active.get_ssid() is not None and \
                self.NM.utils_ssid_to_utf8(active.get_ssid().get_data()) == name
            result.append({"ssid": name, "strength": ap.get_strength(), "secure": secure,
                           "active": is_active, "ap": ap})
        result.sort(key=lambda r: (not r["active"], -r["strength"]))
        return result

    def scan(self):
        dev = self.wifi_device()
        if dev is not None:
            dev.request_scan_async(None, None, None)

    def known_connection(self, ssid):
        dev = self.wifi_device()
        for conn in self.client.get_connections():
            s = conn.get_setting_wireless()
            if s and s.get_ssid() and \
                    self.NM.utils_ssid_to_utf8(s.get_ssid().get_data()) == ssid:
                if dev is None or dev.connection_valid(conn):
                    return conn
        return None

    def connect_to(self, entry, password=None, callback=None):
        """Connect to an access point entry from access_points()."""
        dev = self.wifi_device()
        NM = self.NM

        def done(client, res, finish):
            ok = True
            try:
                finish(res)
            except GLib.Error as err:
                print(f"aurora: wifi connect failed: {err.message}")
                ok = False
            if callback:
                callback(ok)

        conn = self.known_connection(entry["ssid"])
        if conn is not None and password is None:
            self.client.activate_connection_async(
                conn, dev, None, None,
                lambda c, r: done(c, r, c.activate_connection_finish))
            return

        partial = NM.SimpleConnection.new()
        if entry["secure"] and password:
            sec = NM.SettingWirelessSecurity.new()
            sec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-psk")
            sec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            partial.add_setting(sec)
        self.client.add_and_activate_connection_async(
            partial, dev, entry["ap"].get_path(), None,
            lambda c, r: done(c, r, c.add_and_activate_connection_finish))


class Power:
    """Session and system power actions."""

    def __init__(self):
        self._logind = None

    def _manager(self):
        if self._logind is None:
            self._logind = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                "org.freedesktop.login1", "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager", None)
        return self._logind

    def _call(self, method):
        try:
            self._manager().call_sync(method, GLib.Variant("(b)", (True,)),
                                      Gio.DBusCallFlags.NONE, -1, None)
        except GLib.Error as err:
            print(f"aurora: {method} failed: {err.message}")

    def poweroff(self):
        self._call("PowerOff")

    def reboot(self):
        self._call("Reboot")

    def suspend(self):
        self._call("Suspend")

    def lock(self):
        apps.spawn(["aurora-lock"])

    def logout(self):
        apps.spawn(["labwc", "--exit"])
