"""System services used by the shell: audio, brightness, battery, network, Bluetooth,
power profiles, screen recording, media players and power actions."""

import json
import os
import re
import shutil
import signal
import subprocess

import gi
from gi.repository import Gio, GLib, GObject

from aurora import apps


def _run(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def audio_nodes():
    """Return (sinks, sources, default_sink_name, default_source_name)."""
    try:
        data = json.loads(_run(["pw-dump"]) or "[]")
    except json.JSONDecodeError:
        data = []
    sinks, sources = [], []
    default_sink = default_source = None
    for obj in data:
        if obj.get("type") == "PipeWire:Interface:Metadata":
            for entry in obj.get("metadata", []) or []:
                val = entry.get("value")
                if isinstance(val, dict):
                    if entry.get("key") == "default.audio.sink":
                        default_sink = val.get("name")
                    elif entry.get("key") == "default.audio.source":
                        default_source = val.get("name")
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = (obj.get("info") or {}).get("props") or {}
        cls = props.get("media.class")
        node = {"id": obj["id"], "name": props.get("node.name", ""),
                "label": props.get("node.description") or props.get("node.nick")
                or props.get("node.name", "?")}
        if cls == "Audio/Sink":
            sinks.append(node)
        elif cls == "Audio/Source":
            sources.append(node)
    return sinks, sources, default_sink, default_source


def get_volume(target):
    out = _run(["wpctl", "get-volume", target])
    m = re.search(r"Volume:\s*([\d.]+)", out)
    return (float(m.group(1)) if m else 0.0), "[MUTED]" in out



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
        self.remaining = 0
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
        seconds = d.props.time_to_full if self.charging else d.props.time_to_empty
        self.remaining = seconds or 0
        self.emit("changed")

    def describe(self):
        """E.g. '84% · 2 h 10 min left' for the control center."""
        from aurora.i18n import _
        text = f"{self.percentage:.0f}%"
        if self.remaining > 60:
            h, m = divmod(int(self.remaining) // 60, 60)
            left = (f"{h} h {m} min" if h else f"{m} min")
            text += " · " + (_("{t} until full").format(t=left) if self.charging
                             else _("{t} left").format(t=left))
        elif self.charging:
            text += " · " + _("charging")
        return text


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

    def wired_connection(self):
        """Name of the active wired connection, or None."""
        if self.client is None:
            return None
        for conn in self.client.get_active_connections():
            if conn.get_connection_type() == "802-3-ethernet":
                return conn.get_id()
        return None

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


class Microphone(GObject.Object):
    """Default source (microphone) volume through wpctl."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}
    SOURCE = "@DEFAULT_AUDIO_SOURCE@"

    def __init__(self):
        super().__init__()
        self.volume, self.muted, self.available = 0.0, False, False
        self.refresh()

    def refresh(self):
        if shutil.which("wpctl") is None:
            return
        _sinks, sources, _ds, _dsrc = audio_nodes()
        self.available = bool(sources)
        if self.available:
            self.volume, self.muted = get_volume(self.SOURCE)
        self.emit("changed")

    def set_volume(self, value):
        _run(["wpctl", "set-volume", self.SOURCE, f"{max(0.0, min(1.0, value)):.2f}"])
        self.refresh()

    def toggle_mute(self):
        _run(["wpctl", "set-mute", self.SOURCE, "toggle"])
        self.refresh()


def set_default_audio(node_id):
    _run(["wpctl", "set-default", str(node_id)])


class Bluetooth(GObject.Object):
    """BlueZ adapter power and devices, over D-Bus."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}
    BLUEZ = "org.bluez"

    def __init__(self):
        super().__init__()
        self.manager = None
        self.bus = None
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error:
            return
        # Async and without auto-start: on a machine with no adapter, activating
        # bluetoothd blocks for dbus's 25 s service timeout. The manager follows
        # the name owner, so objects appear if bluetoothd starts later.
        Gio.DBusObjectManagerClient.new_for_bus(
            Gio.BusType.SYSTEM, Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START,
            self.BLUEZ, "/", None, None, None, None, self._on_manager)

    def _on_manager(self, _source, result):
        try:
            self.manager = Gio.DBusObjectManagerClient.new_for_bus_finish(result)
        except GLib.Error:
            return
        for sig in ("object-added", "object-removed", "interface-proxy-properties-changed"):
            self.manager.connect(sig, lambda *a: self.emit("changed"))
        self.emit("changed")

    def _objects(self, iface):
        if self.manager is None:
            return []
        return [(o.get_object_path(), o.get_interface(iface)) for o in self.manager.get_objects()
                if o.get_interface(iface) is not None]

    @staticmethod
    def _prop(proxy, name):
        v = proxy.get_cached_property(name)
        return v.unpack() if v is not None else None

    @property
    def adapter(self):
        found = self._objects("org.bluez.Adapter1")
        return found[0] if found else None

    @property
    def available(self):
        return self.adapter is not None

    @property
    def powered(self):
        a = self.adapter
        return bool(a and self._prop(a[1], "Powered"))

    def set_powered(self, on):
        a = self.adapter
        if a is None:
            return
        self.bus.call(self.BLUEZ, a[0], "org.freedesktop.DBus.Properties", "Set",
                      GLib.Variant("(ssv)", ("org.bluez.Adapter1", "Powered",
                                             GLib.Variant("b", on))),
                      None, Gio.DBusCallFlags.NONE, -1, None, None)

    def devices(self):
        """Paired devices: [{path, name, icon, connected}]"""
        out = []
        for path, dev in self._objects("org.bluez.Device1"):
            if not self._prop(dev, "Paired"):
                continue
            out.append({"path": path, "name": self._prop(dev, "Alias") or path.rsplit("/", 1)[-1],
                        "icon": (self._prop(dev, "Icon") or "bluetooth") + "-symbolic",
                        "connected": bool(self._prop(dev, "Connected"))})
        return sorted(out, key=lambda d: (not d["connected"], d["name"].lower()))

    def toggle_device(self, device):
        method = "Disconnect" if device["connected"] else "Connect"
        self.bus.call(self.BLUEZ, device["path"], "org.bluez.Device1", method, None, None,
                      Gio.DBusCallFlags.NONE, 30000, None, None)


class PowerProfiles(GObject.Object):
    """power-profiles-daemon through powerprofilesctl."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}
    PROFILES = ["performance", "balanced", "power-saver"]

    def __init__(self):
        super().__init__()
        self.available = shutil.which("powerprofilesctl") is not None
        self.current = "balanced"
        self.refresh()

    def refresh(self):
        if self.available:
            cur = _run(["powerprofilesctl", "get"]).strip()
            self.available = cur in self.PROFILES
            if self.available:
                self.current = cur
        self.emit("changed")

    def choices(self):
        out = _run(["powerprofilesctl", "list"])
        return [p for p in self.PROFILES if re.search(rf"^\*?\s*{p}:", out, re.M)] or self.PROFILES

    def set(self, profile):
        _run(["powerprofilesctl", "set", profile])
        self.refresh()


class Recorder(GObject.Object):
    """Screen recording with wf-recorder into ~/Videos/Screencasts."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
                    "saved": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self):
        super().__init__()
        self.available = shutil.which("wf-recorder") is not None
        self.proc = None
        self.path = None

    @property
    def recording(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        if self.recording or not self.available:
            return
        videos = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS) \
            or os.path.expanduser("~/Videos")
        folder = os.path.join(videos, "Screencasts")
        os.makedirs(folder, exist_ok=True)
        stamp = GLib.DateTime.new_now_local().format("%Y-%m-%d_%H-%M-%S")
        self.path = os.path.join(folder, f"Screencast_{stamp}.mp4")
        self.proc = subprocess.Popen(["wf-recorder", "-f", self.path],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.emit("changed")

    def stop(self):
        if not self.recording:
            return
        self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        self.emit("changed")
        self.emit("saved", self.path)

    def toggle(self):
        self.stop() if self.recording else self.start()


class Media(GObject.Object):
    """MPRIS media players (music, videos, browsers) through Playerctl."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self.player = None
        self.manager = None
        try:
            gi.require_version("Playerctl", "2.0")
            from gi.repository import Playerctl
            self.Playerctl = Playerctl
            self.manager = Playerctl.PlayerManager()
            self.manager.connect("name-appeared", self._on_name)
            self.manager.connect("player-vanished", self._on_vanished)
            for name in self.manager.props.player_names:
                self._on_name(self.manager, name)
        except (ValueError, ImportError, GLib.Error) as err:
            print(f"aurora: media controls unavailable ({err})")

    def _on_name(self, _manager, name):
        player = self.Playerctl.Player.new_from_name(name)
        for sig in ("playback-status", "metadata"):
            player.connect(sig, lambda *a: self.emit("changed"))
        self.manager.manage_player(player)
        self.player = player
        self.emit("changed")

    def _on_vanished(self, _manager, player):
        players = [p for p in self.manager.props.players if p != player]
        self.player = players[0] if players else None
        self.emit("changed")

    def info(self):
        """(title, artist, playing) of the current player, or None."""
        p = self.player
        if p is None:
            return None
        try:
            title = p.get_title() or ""
            artist = p.get_artist() or ""
            playing = p.props.playback_status == self.Playerctl.PlaybackStatus.PLAYING
        except GLib.Error:
            return None
        if not title and not artist:
            return None
        return title, artist, playing

    def command(self, name):
        if self.player is not None:
            try:
                getattr(self.player, name)()
            except GLib.Error as err:
                print(f"aurora: media {name} failed: {err.message}")
