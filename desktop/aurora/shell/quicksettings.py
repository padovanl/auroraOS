"""Control Center: the quick settings popover in the top bar.

Mirrors what Ubuntu's quick settings offer: sliders for output volume (with
device choice), microphone and brightness; toggles for Wi-Fi, Bluetooth,
power mode, night light, dark style, do not disturb, airplane mode and
screen recording (with detail lists where it makes sense); media controls;
battery, screenshot, settings, lock and the power menu.
"""

from gi.repository import Gdk, GLib, Gtk, Pango

from aurora import settings
from aurora.i18n import _
from aurora.shell.services import audio_nodes, set_default_audio

PROFILE_LABELS = {"performance": _("Performance"), "balanced": _("Balanced"),
                  "power-saver": _("Power Saver")}
PROFILE_ICONS = {"performance": "power-profile-performance-symbolic",
                 "balanced": "power-profile-balanced-symbolic",
                 "power-saver": "power-profile-power-saver-symbolic"}


def _signal_icon(strength):
    level = ("excellent" if strength > 75 else "good" if strength > 50
             else "ok" if strength > 25 else "weak")
    return f"network-wireless-signal-{level}-symbolic"


class Toggle(Gtk.Box):
    """A quick setting as in macOS' Control Center: a round icon, filled with the
    accent color while on, with its name and state beside it; the whole row
    switches it. A setting with details has a small chevron that opens them."""

    def __init__(self, icon, label, on_toggled, on_expand=None):
        super().__init__(css_classes=["qs-tile"], hexpand=True)
        self.title = label
        inner = Gtk.Box(spacing=10, halign=Gtk.Align.START)
        badge = Gtk.Box(css_classes=["qs-tile-badge"], valign=Gtk.Align.CENTER)
        self.image = Gtk.Image(icon_name=icon, hexpand=True, halign=Gtk.Align.CENTER,
                               valign=Gtk.Align.CENTER, vexpand=True)
        badge.append(self.image)
        inner.append(badge)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        text.append(Gtk.Label(label=label, xalign=0, ellipsize=Pango.EllipsizeMode.END,
                              css_classes=["qs-toggle-title"]))
        self.subtitle = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                  css_classes=["qs-toggle-subtitle"])
        text.append(self.subtitle)
        inner.append(text)
        self.button = Gtk.ToggleButton(child=inner, hexpand=True, css_classes=["qs-toggle"])
        self._handler = self.button.connect("toggled", lambda b: on_toggled(b.get_active()))
        self.append(self.button)
        self.arrow = None
        if on_expand:
            self.arrow = Gtk.Button(icon_name="go-next-symbolic", css_classes=["qs-expand"],
                                    valign=Gtk.Align.CENTER, tooltip_text=_("More"))
            self.arrow.connect("clicked", lambda *_: on_expand())
            self.append(self.arrow)

    def set_state(self, active, subtitle=None, icon=None):
        self.button.handler_block(self._handler)
        self.button.set_active(active)
        self.button.handler_unblock(self._handler)
        (self.add_css_class if active else self.remove_css_class)("active")
        self.subtitle.set_label(subtitle or (_("On") if active else _("Off")))
        if icon:
            self.image.set_from_icon_name(icon)


def module(title=None):
    """A frosted card that groups related controls (macOS-style)."""
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["qs-module"])
    if title:
        card.append(Gtk.Label(label=title, xalign=0, css_classes=["qs-module-title"]))
    grid = Gtk.Grid(column_spacing=4, row_spacing=2, column_homogeneous=True)
    card.append(grid)
    return card, grid


class Slider(Gtk.Box):
    """A slim slider in a glass pill: the icon on the left (click it to mute),
    the level in percent, an optional chevron at the end for the devices."""

    def __init__(self, icon, on_change, on_icon=None, on_expand=None):
        super().__init__(spacing=8, css_classes=["qs-slider"])
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.01)
        self.scale.set_hexpand(True)
        self.scale.set_draw_value(False)
        self.scale.add_css_class("qs-pill-scale")
        self._handler = self.scale.connect("value-changed", lambda s: on_change(s.get_value()))
        self.icon = Gtk.Button(icon_name=icon, css_classes=["flat", "circular", "qs-slider-icon"],
                               valign=Gtk.Align.CENTER)
        if on_icon:
            self.icon.connect("clicked", lambda *_: on_icon())
        else:
            self.icon.set_can_target(False)
        self.percent = Gtk.Label(css_classes=["qs-slider-value", "numeric"], width_chars=4,
                                 xalign=1)
        self.scale.connect("value-changed",
                           lambda sc: self.percent.set_label(f"{round(sc.get_value() * 100)}%"))
        self.append(self.icon)
        self.append(self.scale)
        self.append(self.percent)
        if on_expand:
            arrow = Gtk.Button(icon_name="go-next-symbolic",
                               css_classes=["circular", "qs-slider-more"],
                               valign=Gtk.Align.CENTER, tooltip_text=_("Devices"))
            arrow.connect("clicked", lambda *_: on_expand())
            self.append(arrow)

    def set_value(self, value, icon=None):
        self.scale.handler_block(self._handler)
        self.scale.set_value(value)
        self.scale.handler_unblock(self._handler)
        self.percent.set_label(f"{round(self.scale.get_value() * 100)}%")
        if icon:
            self.icon.set_icon_name(icon)


class DetailList(Gtk.Box):
    """The list shown under the toggles when an arrow is clicked."""

    def __init__(self, title):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                         css_classes=["qs-detail"])
        header = Gtk.Label(label=title, xalign=0, css_classes=["heading"], margin_bottom=4)
        self.append(header)
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.append(Gtk.ScrolledWindow(child=self.rows, max_content_height=240,
                                       propagate_natural_height=True,
                                       hscrollbar_policy=Gtk.PolicyType.NEVER))
        self.footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.append(self.footer)

    def clear(self):
        while (c := self.rows.get_first_child()) is not None:
            self.rows.remove(c)

    def add_row(self, icon, label, on_click=None, checked=False, dim=False, widget=None):
        btn = Gtk.Button(css_classes=["flat", "qs-row"])
        box = Gtk.Box(spacing=10)
        box.append(Gtk.Image(icon_name=icon))
        box.append(Gtk.Label(label=label, xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END,
                             css_classes=["dim-label"] if dim else []))
        if checked:
            box.append(Gtk.Image(icon_name="object-select-symbolic"))
        btn.set_child(box)
        if on_click:
            btn.connect("clicked", lambda *_: on_click())
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wrapper.append(btn)
        if widget is not None:
            wrapper.append(widget)
        self.rows.append(wrapper)
        return btn

    def add_empty(self, text):
        self.rows.append(Gtk.Label(label=text, css_classes=["dim-label"], margin_top=6,
                                   margin_bottom=6))

    def add_link(self, label, on_click):
        b = Gtk.Button(label=label, css_classes=["flat"], margin_top=4)
        b.get_child().set_xalign(0)
        b.connect("clicked", lambda *_: on_click())
        self.footer.append(b)


class QuickSettings(Gtk.Popover):
    def __init__(self, shell):
        super().__init__(has_arrow=False)
        self.add_css_class("aurora-quicksettings")
        self.shell = shell
        self._detail = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=14, margin_bottom=14, margin_start=14, margin_end=14)
        box.set_size_request(392, -1)
        self.set_child(box)

        # --- header: the time and date, like the top of Android's shade ---
        header = Gtk.Box(spacing=8, css_classes=["qs-header"])
        clock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.header_time = Gtk.Label(xalign=0, css_classes=["qs-time", "numeric"])
        self.header_date = Gtk.Label(xalign=0, css_classes=["qs-date"])
        clock.append(self.header_time)
        clock.append(self.header_date)
        header.append(clock)
        self.battery_pill = Gtk.Label(css_classes=["qs-battery"], valign=Gtk.Align.CENTER,
                                      visible=False)
        header.append(self.battery_pill)
        box.append(header)

        # --- sliders ---
        self.volume = Slider("audio-volume-high-symbolic", shell.audio.set_volume,
                             shell.audio.toggle_mute, lambda: self._show_detail("output"))
        self.mic = Slider("audio-input-microphone-symbolic", shell.microphone.set_volume,
                          shell.microphone.toggle_mute, lambda: self._show_detail("input"))
        self.brightness = Slider("display-brightness-symbolic", shell.brightness.set_level)
        sliders = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          css_classes=["qs-module", "qs-sliders"])
        for w in (self.volume, self.mic, self.brightness):
            sliders.append(w)
        box.append(sliders)

        # --- toggles ---
        s = settings.get()
        iface = settings.interface()
        self.t_wifi = Toggle("network-wireless-symbolic", _("Wi-Fi"),
                             shell.network.set_wifi_enabled, lambda: self._show_detail("wifi"))
        self.t_wired = Toggle("network-wired-symbolic", _("Wired"),
                              lambda v: self._open("network"))
        self.t_bt = Toggle("bluetooth-active-symbolic", _("Bluetooth"),
                           shell.bluetooth.set_powered, lambda: self._show_detail("bluetooth"))
        self.t_power = Toggle("power-profile-balanced-symbolic", _("Power Mode"),
                              lambda v: self._show_detail("power"),
                              lambda: self._show_detail("power"))
        self.t_night = Toggle("daytime-sunset-symbolic", _("Night Light"),
                              lambda v: s and s.set_boolean("night-light", v))
        self.t_dark = Toggle("weather-clear-night-symbolic", _("Dark Style"), self._set_dark)
        self.t_dnd = Toggle("notifications-disabled-symbolic", _("Do Not Disturb"),
                            lambda v: s and s.set_boolean("do-not-disturb", v))
        self.t_air = Toggle("airplane-mode-symbolic", _("Airplane Mode"), self._set_airplane)
        self.t_rec = Toggle("media-record-symbolic", _("Screen Recording"),
                            lambda v: self._record(), lambda: self._show_detail("record"))
        self.t_awake = Toggle("view-reveal-symbolic", _("Keep Awake"),
                              shell.keep_awake.set_active)
        shell.keep_awake.connect("changed", lambda *_: self.refresh())
        self.t_hotspot = Toggle("network-wireless-hotspot-symbolic", _("Mobile Hotspot"),
                                self._set_hotspot, lambda: self._show_detail("hotspot"))
        self.t_osk = Toggle("input-keyboard-symbolic", _("Screen Keyboard"),
                            self._set_screen_keyboard)
        self.modules = []
        for title in (_("Connections"), _("Modes"), _("Screen")):
            card, grid = module(title)
            self.modules.append((card, grid))
            box.append(card)

        # --- detail area ---
        self.detail_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                                      vhomogeneous=False)
        self.details = {}
        for key, title in (("wifi", _("Wi-Fi Networks")), ("bluetooth", _("Bluetooth Devices")),
                           ("power", _("Power Mode")), ("output", _("Sound Output")),
                           ("input", _("Sound Input")), ("record", _("Screen Recording")),
                           ("hotspot", _("Mobile Hotspot"))):
            d = DetailList(title)
            self.details[key] = d
            self.detail_stack.add_named(d, key)
        self.details["wifi"].add_link(_("Network Settings"),
                                      lambda: self._open("network"))
        self.details["bluetooth"].add_link(_("Bluetooth Settings"),
                                           lambda: self._open("bluetooth"))
        self.details["power"].add_link(_("Power Settings"), lambda: self._open("power"))
        self.details["output"].add_link(_("Sound Settings"), lambda: self._open("sound"))
        self.details["input"].add_link(_("Sound Settings"), lambda: self._open("sound"))
        self.detail_revealer = Gtk.Revealer(child=self.detail_stack)
        box.append(self.detail_revealer)

        # --- media ---
        self.media_box = Gtk.Box(spacing=10, css_classes=["qs-media"], visible=False)
        self.media_icon = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=32)
        meta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True,
                       valign=Gtk.Align.CENTER)
        self.media_title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                     css_classes=["heading"])
        self.media_artist = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                      css_classes=["dim-label"])
        meta.append(self.media_title)
        meta.append(self.media_artist)
        self.media_box.append(self.media_icon)
        self.media_box.append(meta)
        for icon, cmd in (("media-skip-backward-symbolic", "previous"),
                          ("media-playback-start-symbolic", "play_pause"),
                          ("media-skip-forward-symbolic", "next")):
            b = Gtk.Button(icon_name=icon, css_classes=["flat", "circular"],
                           valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda _b, c=cmd: shell.media.command(c))
            if cmd == "play_pause":
                self.play_button = b
            self.media_box.append(b)
        box.append(self.media_box)

        # --- footer ---
        footer = Gtk.Box(spacing=8, css_classes=["qs-footer"])
        self.battery_label = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END,
                                       css_classes=["qs-footer-label"])
        footer.append(self.battery_label)
        for icon, tip, cb in (
            ("applets-screenshooter-symbolic", _("Screenshot"),
             lambda: GLib.timeout_add(300, lambda: shell.screenshot(area=True) and False)),
            ("emblem-system-symbolic", _("Settings"), lambda: shell.open_settings("")),
            ("system-lock-screen-symbolic", _("Lock"), shell.lock),
        ):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip, css_classes=["circular", "qs-round"])
            b.connect("clicked", lambda _b, cb=cb: (self.popdown(), cb()))
            footer.append(b)
        power = Gtk.MenuButton(icon_name="system-shutdown-symbolic",
                               tooltip_text=_("Power Off / Log Out"),
                               css_classes=["circular", "qs-round", "qs-power"],
                               direction=Gtk.ArrowType.UP)
        power.set_popover(self._power_menu())
        footer.append(power)
        box.append(footer)

        for svc in (shell.network, shell.bluetooth, shell.audio, shell.microphone,
                    shell.power_profiles, shell.recorder, shell.media, shell.battery):
            svc.connect("changed", lambda *a: self.get_visible() and self.refresh())
        if iface is not None:
            iface.connect("changed::color-scheme", lambda *a: self.get_visible() and self.refresh())
        self.connect("show", lambda *_: self._on_show())

    # --- actions ---

    def _open(self, page):
        self.popdown()
        self.shell.open_settings(page)

    def _record(self, area=False):
        self.popdown()
        s = settings.get()
        sound = s is not None and s.get_boolean("record-sound")
        # Give the popover time to close so it isn't in the recording.
        GLib.timeout_add(400, lambda: self.shell.recorder.toggle(area, sound) and False)

    def _set_screen_keyboard(self, on):
        """Show or hide the on-screen keyboard (for touch screens and tablets)."""
        self.popdown()
        (self.shell.osk.show_keyboard if on else self.shell.osk.hide_keyboard)()

    def _set_hotspot(self, on):
        self.t_hotspot.set_state(on, _("Starting…") if on else None)

        def done(ok):
            if not ok:
                self.shell.notifications.notify(
                    _("Mobile Hotspot"), 0, "network-wireless-hotspot-symbolic",
                    _("Couldn't start the hotspot"),
                    _("This Wi-Fi card may not support it, or Wi-Fi is off."), [],
                    {"transient": True}, -1)
            self.refresh()
            if ok and on:
                self._show_detail("hotspot") if self._detail != "hotspot" else \
                    self._fill_detail("hotspot")
        self.shell.network.set_hotspot(on, done)

    def _airplane_on(self):
        net, bt = self.shell.network, self.shell.bluetooth
        wifi_off = net.wifi_device() is None or not net.wifi_enabled
        bt_off = not bt.available or not bt.powered
        return wifi_off and bt_off and (net.wifi_device() is not None or bt.available)

    def _set_dark(self, value):
        # Choosing a style by hand stops the automatic sunset/sunrise switch.
        s, iface = settings.get(), settings.interface()
        if s is not None:
            s.set_boolean("color-scheme-auto", False)
        if iface is not None:
            iface.set_string("color-scheme", "prefer-dark" if value else "default")
        self.refresh()

    def _set_airplane(self, on):
        self.shell.network.set_wifi_enabled(not on)
        self.shell.bluetooth.set_powered(not on)

    def _power_menu(self):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        p = self.shell.power
        for label, cb in ((_("Suspend"), p.suspend), (_("Restart…"), p.reboot),
                          (_("Power Off…"), p.poweroff), (_("Log Out"), p.logout)):
            b = Gtk.Button(label=label, css_classes=["flat"])
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), self.popdown(), cb()))
            box.append(b)
        pop.set_child(box)
        return pop

    def _show_detail(self, key):
        if self._detail == key and self.detail_revealer.get_reveal_child():
            self.detail_revealer.set_reveal_child(False)
            self._detail = None
            return
        self._detail = key
        if key == "wifi":
            self.shell.network.scan()
        self._fill_detail(key)
        self.detail_stack.set_visible_child_name(key)
        self.detail_revealer.set_reveal_child(True)

    # --- detail lists ---

    def _fill_detail(self, key):
        d = self.details[key]
        d.clear()
        sh = self.shell
        if key == "wifi":
            entries = sh.network.access_points() if sh.network.wifi_enabled else []
            if not entries:
                d.add_empty(_("No networks found") if sh.network.wifi_enabled
                            else _("Wi-Fi is off"))
            for entry in entries[:15]:
                self._wifi_row(d, entry)
        elif key == "bluetooth":
            devices = sh.bluetooth.devices() if sh.bluetooth.powered else []
            if not devices:
                d.add_empty(_("No paired devices") if sh.bluetooth.powered
                            else _("Bluetooth is off"))
            for dev in devices:
                label = dev["name"]
                if dev["connected"] and dev.get("battery") is not None:
                    label += f"  ·  🔋 {dev['battery']}%"
                d.add_row(dev["icon"], label, lambda dev=dev: sh.bluetooth.toggle_device(dev),
                          checked=dev["connected"])
        elif key == "power":
            for profile in sh.power_profiles.choices():
                d.add_row(PROFILE_ICONS[profile], PROFILE_LABELS[profile],
                          lambda p=profile: (sh.power_profiles.set(p), self._fill_detail("power")),
                          checked=profile == sh.power_profiles.current)
        elif key == "hotspot":
            ssid, password = sh.network.hotspot_credentials()
            d.add_row("network-wireless-symbolic", _("Network: {name}").format(name=ssid))
            d.add_row("dialog-password-symbolic", _("Password: {pw}").format(pw=password),
                      lambda: Gdk.Display.get_default().get_clipboard().set(password))
            if sh.network.hotspot_active():
                try:
                    from aurora.settingsapp.network import qr_svg, wifi_qr_payload
                    texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(
                        qr_svg(wifi_qr_payload(ssid, password))))
                    pic = Gtk.Picture(paintable=texture, can_shrink=True,
                                      css_classes=["qs-qr"], halign=Gtk.Align.CENTER)
                    pic.set_size_request(150, 150)
                    d.rows.append(pic)
                    d.add_empty(_("Point a phone's camera at the code to join"))
                except Exception as err:  # noqa: BLE001 - no qrcode module: names are enough
                    print(f"aurora: hotspot QR unavailable: {err}")
            else:
                d.add_empty(_("Turn the tile on to share this computer's connection"))
        elif key == "record":
            s = settings.get()
            sound = s is not None and s.get_boolean("record-sound")
            d.add_row("view-fullscreen-symbolic", _("Record the whole screen"),
                      lambda: self._record(False))
            d.add_row("edit-select-all-symbolic", _("Record an area…"),
                      lambda: self._record(True))
            d.add_row("audio-speakers-symbolic", _("Record the computer's sound"),
                      lambda: s and (s.set_boolean("record-sound", not sound),
                                     self._fill_detail("record")),
                      checked=sound)
        elif key in ("output", "input"):
            sinks, sources, dsink, dsource = audio_nodes()
            if key == "output":
                # Each app's own volume, under the devices (Windows' Volume Mixer).
                from aurora import mixerui
                from aurora.shell.services import app_streams
                streams = app_streams()
                if streams:
                    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                                  margin_top=8, css_classes=["qs-mixer"])
                    box.append(Gtk.Label(label=_("Apps"), xalign=0, css_classes=["heading"]))
                    apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                    mixerui.fill(apps_box, streams)
                    box.append(apps_box)
                    d.rows.append(box)
            nodes, default = (sinks, dsink) if key == "output" else (sources, dsource)
            icon = "audio-speakers-symbolic" if key == "output" else "audio-input-microphone-symbolic"
            if not nodes:
                d.add_empty(_("No devices found"))
            for n in nodes:
                d.add_row(icon, n["label"],
                          lambda n=n: (set_default_audio(n["id"]), sh.audio.refresh(),
                                       sh.microphone.refresh(), self._fill_detail(key)),
                          checked=n["name"] == default)

    def _wifi_row(self, d, entry):
        net = self.shell.network
        pw_box = Gtk.Box(spacing=6, margin_start=8, margin_end=8, margin_bottom=6)
        pw = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True, placeholder_text=_("Password"))
        go = Gtk.Button(label=_("Connect"), css_classes=["suggested-action"])
        pw_box.append(pw)
        pw_box.append(go)
        revealer = Gtk.Revealer(child=pw_box)

        def with_password(*_a):
            net.connect_to(entry, pw.get_text())
            revealer.set_reveal_child(False)

        def clicked():
            if entry["active"]:
                return
            if entry["secure"] and net.known_connection(entry["ssid"]) is None:
                revealer.set_reveal_child(not revealer.get_reveal_child())
                pw.grab_focus()
            else:
                net.connect_to(entry)
        go.connect("clicked", with_password)
        pw.connect("activate", with_password)
        label = entry["ssid"] + ("  🔒" if entry["secure"] and not entry["active"] else "")
        d.add_row(_signal_icon(entry["strength"]), label, clicked, checked=entry["active"],
                  widget=revealer)

    # --- state ---

    def _on_show(self):
        self.shell.audio.refresh()
        self.shell.microphone.refresh()
        self.shell.brightness.refresh()
        self.shell.power_profiles.refresh()
        self.refresh()

    def refresh(self):
        sh = self.shell
        s = settings.get()
        iface = settings.interface()
        now = GLib.DateTime.new_now_local()
        twelve = s is not None and s.get_string("clock-format") == "12h"
        self.header_time.set_label(now.format("%l:%M %p" if twelve else "%H:%M").strip())
        self.header_date.set_label(now.format("%A, %-d %B").replace("  ", " "))

        self.volume.scale.set_range(0, sh.audio.maximum)
        self.volume.set_value(0 if sh.audio.muted else sh.audio.volume, sh.audio.icon_name)
        self.volume.set_visible(sh.audio.available)
        self.mic.set_value(0 if sh.microphone.muted else sh.microphone.volume,
                           "microphone-sensitivity-muted-symbolic" if sh.microphone.muted
                           else "audio-input-microphone-symbolic")
        self.mic.set_visible(sh.microphone.available)
        self.brightness.set_value(sh.brightness.level)
        self.brightness.set_visible(sh.brightness.available)

        # Toggles that apply to this machine, in three cards, two per row.
        net = sh.network
        toggles = []
        if net.wifi_device() is not None:
            _icon, name = net.status()
            ap_name = name if net.wifi_enabled and name else None
            self.t_wifi.set_state(net.wifi_enabled, ap_name)
            toggles.append(self.t_wifi)
        wired = net.wired_connection() if hasattr(net, "wired_connection") else None
        if wired is not None:
            self.t_wired.set_state(True, wired)
            toggles.append(self.t_wired)
        if sh.bluetooth.available:
            connected = [d for d in sh.bluetooth.devices() if d["connected"]]
            sub = None
            if connected:
                sub = connected[0]["name"] + (f" · {connected[0]['battery']}%"
                                              if connected[0].get("battery") is not None else "")
            self.t_bt.set_state(sh.bluetooth.powered, sub)
            toggles.append(self.t_bt)
        if sh.power_profiles.available:
            cur = sh.power_profiles.current
            self.t_power.set_state(cur != "balanced", PROFILE_LABELS[cur], PROFILE_ICONS[cur])
            toggles.append(self.t_power)
        from aurora.shell.daycycle import night_light_unsupported
        night = s is not None and s.get_boolean("night-light")
        self.t_night.set_state(night, _("Not supported here")
                               if night and night_light_unsupported() else None)
        from aurora import look
        self.t_dark.set_state(look.is_dark())
        self.t_dnd.set_state(s is not None and s.get_boolean("do-not-disturb"))
        self.t_awake.set_state(sh.keep_awake.active,
                               _("Screen stays on") if sh.keep_awake.active else None)
        toggles += [self.t_night, self.t_dark, self.t_dnd, self.t_awake]
        if net.wifi_device() is not None or sh.bluetooth.available:
            self.t_air.set_state(self._airplane_on())
            toggles.append(self.t_air)
        if net.wifi_device() is not None:
            active = net.hotspot_active()
            self.t_hotspot.set_state(active, net.hotspot_credentials()[0] if active else None)
            toggles.append(self.t_hotspot)
        self.t_osk.set_state(getattr(sh, "_osk", None) is not None and sh.osk.showing)
        toggles.append(self.t_osk)
        if sh.recorder.available:
            self.t_rec.set_state(sh.recorder.recording,
                                 _("Recording…") if sh.recorder.recording else None)
            toggles.append(self.t_rec)
        groups = (
            [self.t_wifi, self.t_wired, self.t_bt, self.t_air, self.t_hotspot],
            [self.t_dnd, self.t_awake, self.t_power],
            [self.t_dark, self.t_night, self.t_osk, self.t_rec],
        )
        for (card, grid), members in zip(self.modules, groups):
            while (c := grid.get_first_child()) is not None:
                grid.remove(c)
            shown = [t for t in members if t in toggles]
            for i, t in enumerate(shown):
                grid.attach(t, i % 2, i // 2, 1, 1)
            card.set_visible(bool(shown))

        if self._detail and self.detail_revealer.get_reveal_child():
            self._fill_detail(self._detail)

        info = sh.media.info()
        self.media_box.set_visible(info is not None)
        if info:
            title, artist, playing = info
            self.media_title.set_label(title)
            self.media_artist.set_label(artist)
            self.play_button.set_icon_name("media-playback-pause-symbolic" if playing
                                           else "media-playback-start-symbolic")

        bat = sh.battery
        self.battery_label.set_label(bat.describe() if bat.present else "")
        self.battery_pill.set_visible(bat.present)
        if bat.present:
            self.battery_pill.set_label(f"{'⚡ ' if bat.charging else ''}{bat.percentage:.0f}%")
