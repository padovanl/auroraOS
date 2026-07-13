"""Quick settings popover: volume, brightness, toggles, Wi-Fi, power."""

from gi.repository import Gtk, GLib

from aurora import settings
from aurora.i18n import _


class Toggle(Gtk.ToggleButton):
    def __init__(self, icon, label, active, on_toggled):
        box = Gtk.Box(spacing=10)
        box.append(Gtk.Image(icon_name=icon))
        box.append(Gtk.Label(label=label, xalign=0, hexpand=True,
                             ellipsize=3))  # Pango.EllipsizeMode.END
        super().__init__(child=box, active=active, hexpand=True)
        self.add_css_class("qs-toggle")
        self._handler = self.connect("toggled", lambda b: on_toggled(b.get_active()))

    def set_state(self, active):
        self.handler_block(self._handler)
        self.set_active(active)
        self.handler_unblock(self._handler)


class SliderRow(Gtk.Box):
    def __init__(self, icon, on_change, on_icon_click=None):
        super().__init__(spacing=8)
        self.add_css_class("qs-slider")
        self.icon = Gtk.Button(icon_name=icon, css_classes=["flat", "circular"])
        if on_icon_click:
            self.icon.connect("clicked", lambda *_: on_icon_click())
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.01)
        self.scale.set_hexpand(True)
        self.scale.set_draw_value(False)
        self._handler = self.scale.connect("value-changed", lambda s: on_change(s.get_value()))
        self.append(self.icon)
        self.append(self.scale)

    def set_value(self, value, icon=None):
        self.scale.handler_block(self._handler)
        self.scale.set_value(value)
        self.scale.handler_unblock(self._handler)
        if icon:
            self.icon.set_icon_name(icon)


class WifiList(Gtk.Box):
    """Expandable list of Wi-Fi networks with inline password entry."""

    def __init__(self, network):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class("qs-wifi-list")
        self.network = network
        self._pending = None

    def refresh(self):
        while (child := self.get_first_child()) is not None:
            self.remove(child)
        entries = self.network.access_points()
        if not entries:
            self.append(Gtk.Label(label=_("No networks found"), css_classes=["dim-label"],
                                  margin_top=6, margin_bottom=6))
            return
        for entry in entries[:12]:
            self.append(self._row(entry))

    def _row(self, entry):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        btn = Gtk.Button(css_classes=["flat", "qs-wifi-row"])
        row = Gtk.Box(spacing=8)
        level = ("excellent" if entry["strength"] > 75 else "good" if entry["strength"] > 50
                 else "ok" if entry["strength"] > 25 else "weak")
        row.append(Gtk.Image(icon_name=f"network-wireless-signal-{level}-symbolic"))
        row.append(Gtk.Label(label=entry["ssid"], xalign=0, hexpand=True, ellipsize=3))
        if entry["active"]:
            row.append(Gtk.Image(icon_name="object-select-symbolic"))
        elif entry["secure"]:
            row.append(Gtk.Image(icon_name="network-wireless-encrypted-symbolic",
                                 css_classes=["dim-label"]))
        btn.set_child(row)
        box.append(btn)

        revealer = Gtk.Revealer()
        pw_box = Gtk.Box(spacing=6, margin_start=8, margin_end=8, margin_bottom=6)
        pw = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True,
                               placeholder_text=_("Password"))
        go = Gtk.Button(label=_("Connect"), css_classes=["suggested-action"])
        pw_box.append(pw)
        pw_box.append(go)
        revealer.set_child(pw_box)
        box.append(revealer)

        def connect_with_password(*_a):
            self.network.connect_to(entry, pw.get_text())
            revealer.set_reveal_child(False)

        def clicked(*_a):
            if entry["active"]:
                return
            if entry["secure"] and self.network.known_connection(entry["ssid"]) is None:
                revealer.set_reveal_child(not revealer.get_reveal_child())
                pw.grab_focus()
            else:
                self.network.connect_to(entry)

        btn.connect("clicked", clicked)
        go.connect("clicked", connect_with_password)
        pw.connect("activate", connect_with_password)
        return box


class QuickSettings(Gtk.Popover):
    def __init__(self, shell):
        super().__init__(has_arrow=False)
        self.add_css_class("aurora-quicksettings")
        self.shell = shell
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        box.set_size_request(340, -1)
        self.set_child(box)

        # Sliders
        audio, bright = shell.audio, shell.brightness
        self.volume = SliderRow("audio-volume-high-symbolic", audio.set_volume,
                                audio.toggle_mute)
        box.append(self.volume)
        self.brightness = SliderRow("display-brightness-symbolic", bright.set_level)
        box.append(self.brightness)

        # Toggles
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        net = shell.network
        self.wifi = Toggle("network-wireless-symbolic", _("Wi-Fi"), net.wifi_enabled,
                           net.set_wifi_enabled)
        self.wifi_expand = Gtk.Button(icon_name="go-next-symbolic",
                                      css_classes=["flat", "qs-expand"])
        wifi_box = Gtk.Box(css_classes=["linked"])
        wifi_box.append(self.wifi)
        wifi_box.append(self.wifi_expand)
        grid.attach(wifi_box, 0, 0, 1, 1)

        iface = settings.interface()
        dark = iface is not None and iface.get_string("color-scheme") == "prefer-dark"
        self.dark = Toggle("weather-clear-night-symbolic", _("Dark Style"), dark,
                           self._set_dark)
        grid.attach(self.dark, 1, 0, 1, 1)

        s = settings.get()
        dnd = s is not None and s.get_boolean("do-not-disturb")
        self.dnd = Toggle("notifications-disabled-symbolic", _("Do Not Disturb"), dnd,
                          lambda v: s and s.set_boolean("do-not-disturb", v))
        grid.attach(self.dnd, 0, 1, 1, 1)

        self.night = Toggle("night-light-symbolic", _("Night Light"),
                            s is not None and s.get_boolean("night-light"),
                            lambda v: s and s.set_boolean("night-light", v))
        grid.attach(self.night, 1, 1, 1, 1)
        box.append(grid)

        self.wifi_list = WifiList(net)
        self.wifi_revealer = Gtk.Revealer(child=Gtk.ScrolledWindow(
            child=self.wifi_list, max_content_height=260, propagate_natural_height=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER))
        box.append(self.wifi_revealer)
        self.wifi_expand.connect("clicked", self._toggle_wifi_list)

        # Footer: battery + actions
        footer = Gtk.Box(spacing=6)
        self.battery_label = Gtk.Label(xalign=0, hexpand=True, css_classes=["dim-label"])
        footer.append(self.battery_label)
        for icon, tip, cb in (
            ("emblem-system-symbolic", _("Settings"), lambda: shell.open_settings("")),
            ("system-lock-screen-symbolic", _("Lock"), shell.power.lock),
        ):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip, css_classes=["circular"])
            b.connect("clicked", lambda _b, cb=cb: (self.popdown(), cb()))
            footer.append(b)
        power = Gtk.MenuButton(icon_name="system-shutdown-symbolic",
                               tooltip_text=_("Power Off / Log Out"),
                               css_classes=["circular"], direction=Gtk.ArrowType.UP)
        power.set_popover(self._power_menu())
        footer.append(power)
        box.append(footer)

        self.connect("show", lambda *_: self.refresh())

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

    def _toggle_wifi_list(self, *_a):
        reveal = not self.wifi_revealer.get_reveal_child()
        if reveal:
            self.shell.network.scan()
            self.wifi_list.refresh()
        self.wifi_revealer.set_reveal_child(reveal)
        self.wifi_expand.set_icon_name("go-down-symbolic" if reveal else "go-next-symbolic")

    def _set_dark(self, active):
        iface = settings.interface()
        if iface is not None:
            iface.set_string("color-scheme", "prefer-dark" if active else "default")

    def refresh(self):
        sh = self.shell
        sh.audio.refresh()
        sh.brightness.refresh()
        self.volume.set_value(0 if sh.audio.muted else sh.audio.volume, sh.audio.icon_name)
        self.volume.set_visible(sh.audio.available)
        self.brightness.set_value(sh.brightness.level)
        self.brightness.set_visible(sh.brightness.available)
        self.wifi.set_state(sh.network.wifi_enabled)
        self.wifi.get_parent().set_visible(sh.network.wifi_device() is not None)
        if sh.battery.present:
            state = _("charging") if sh.battery.charging else _("on battery")
            self.battery_label.set_label(f"{sh.battery.percentage:.0f}% · {state}")
        else:
            self.battery_label.set_label(GLib.get_host_name())
        if self.wifi_revealer.get_reveal_child():
            self.wifi_list.refresh()

