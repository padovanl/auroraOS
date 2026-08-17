"""Top bar: Aurora menu, focused app, status indicators, clock."""

from gi.repository import Gdk, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.shell.layer import Keyboard, Layer, LayerWindow
from aurora.shell.quicksettings import QuickSettings
from aurora.shell.tray import Tray


class WeatherWidget(Gtk.Button):
    """Current weather and the next hours; click opens the Weather app."""

    def __init__(self):
        super().__init__(css_classes=["flat", "weather-widget"], visible=False)
        self.connect("clicked", lambda *_: apps.spawn(["gnome-weather"]))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        top = Gtk.Box(spacing=10)
        self.icon = Gtk.Image(pixel_size=40)
        top.append(self.icon)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.temp = Gtk.Label(xalign=0, css_classes=["title-2"])
        self.desc = Gtk.Label(xalign=0, css_classes=["dim-label", "caption"])
        text.append(self.temp)
        text.append(self.desc)
        top.append(text)
        box.append(top)
        self.hours = Gtk.Box(spacing=4, homogeneous=True)
        box.append(self.hours)
        self.set_child(box)
        self._busy = False

    def refresh(self):
        from aurora import sun, weather
        s = settings.get()
        loc = sun.location()
        if (s is not None and not s.get_boolean("weather-widget")) or loc is None:
            self.set_visible(False)
            return
        data = weather.cached(*loc)
        if data is not None:
            self._show(data)
            return
        if self._busy:
            return
        self._busy = True
        import threading

        def work():
            try:
                result = weather.fetch(*loc, fahrenheit=weather.uses_fahrenheit())
            except Exception as e:  # noqa: BLE001 - offline is normal
                print(f"aurora: weather unavailable: {e}")
                result = None
            GLib.idle_add(lambda: (self._done(result), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _done(self, data):
        self._busy = False
        if data is not None:
            self._show(data)

    def _show(self, data):
        from aurora import weather
        text, icon = weather.describe(data["code"], data["is_day"])
        unit = data["unit"]
        self.icon.set_from_icon_name(icon)
        self.temp.set_label(f"{data['temp']:.0f}{unit}")
        self.desc.set_label(_("{sky} · H {high:.0f}° L {low:.0f}°").format(
            sky=_(text), high=data["high"], low=data["low"]))
        while (c := self.hours.get_first_child()) is not None:
            self.hours.remove(c)
        for hour, temp, code in data["hours"]:
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            col.append(Gtk.Label(label=hour, css_classes=["dim-label", "caption"]))
            col.append(Gtk.Image(icon_name=weather.describe(code)[1]))
            col.append(Gtk.Label(label=f"{temp:.0f}°", css_classes=["caption"]))
            self.hours.append(col)
        self.set_visible(True)


class Clock(Gtk.MenuButton):
    """Clock; opens the calendar and notification center."""

    def __init__(self, shell):
        super().__init__(css_classes=["flat", "panel-button", "panel-clock"])
        self.shell = shell
        self._label = Gtk.Label()
        self.set_child(self._label)

        pop = Gtk.Popover(has_arrow=False)
        pop.add_css_class("aurora-calendar")
        box = Gtk.Box(spacing=12, margin_top=12, margin_bottom=12,
                      margin_start=12, margin_end=12)
        box.append(shell.notifications.history_widget())
        cal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._date = Gtk.Label(xalign=0, css_classes=["title-3"])
        cal_box.append(self._date)
        self._calendar = Gtk.Calendar()
        cal_box.append(self._calendar)
        self._weather = WeatherWidget()
        cal_box.append(self._weather)
        events = Gtk.Button(label=_("Open Calendar"), css_classes=["flat"],
                            halign=Gtk.Align.START)
        events.connect("clicked", lambda *_: (pop.popdown(), apps.spawn(["gnome-calendar"])))
        cal_box.append(events)
        box.append(cal_box)
        pop.set_child(box)
        pop.connect("show", self._on_show)
        self.set_popover(pop)

        self._source = 0
        s = settings.get()
        if s:
            s.connect("changed::clock-show-seconds", lambda *a: self._tick())
            s.connect("changed::clock-format", lambda *a: self._tick())
        self._tick()

    def _on_show(self, *_a):
        now = GLib.DateTime.new_now_local()
        self._calendar.select_day(now)
        self._date.set_label(now.format("%A, %e %B %Y").replace("  ", " "))
        self._weather.refresh()

    def _tick(self):
        s = settings.get()
        seconds = s is not None and s.get_boolean("clock-show-seconds")
        fmt_24 = s is None or s.get_string("clock-format") == "24h"
        now = GLib.DateTime.new_now_local()
        time_fmt = ("%H:%M" if fmt_24 else "%l:%M") + (":%S" if seconds else "")
        if not fmt_24:
            time_fmt += " %p"
        self._label.set_label(now.format(f"%a %e %b  {time_fmt}").replace("  ", " ").strip())
        # Wake up right at the next second/minute boundary.
        delay = 1000 - now.get_microsecond() // 1000 if seconds else \
            (60 - now.get_second()) * 1000
        if self._source:
            GLib.source_remove(self._source)
        self._source = GLib.timeout_add(max(delay, 50), self._on_timeout)

    def _on_timeout(self):
        self._source = 0
        self._tick()
        return GLib.SOURCE_REMOVE


class StatusArea(Gtk.MenuButton):
    """Network / volume / battery icons; opens the control center."""

    def __init__(self, shell):
        super().__init__(css_classes=["flat", "panel-button", "panel-status"],
                         tooltip_text=_("Control Center"))
        self.shell = shell
        box = Gtk.Box(spacing=10)
        self.net_icon = Gtk.Image()
        self.vol_icon = Gtk.Image()
        self.bat_icon = Gtk.Image()
        self.bat_label = Gtk.Label(css_classes=["panel-battery-label"])
        self.bt_icon = Gtk.Image(icon_name="bluetooth-active-symbolic")
        self.rec_icon = Gtk.Image(icon_name="media-record-symbolic", css_classes=["panel-recording"],
                                  tooltip_text=_("Recording the screen"))
        self.cc_icon = Gtk.Image(icon_name="view-more-horizontal-symbolic")
        for w in (self.rec_icon, self.bat_label, self.bat_icon, self.bt_icon, self.net_icon,
                  self.vol_icon, self.cc_icon):
            box.append(w)
        self.set_child(box)
        self.set_popover(QuickSettings(shell))

        shell.network.connect("changed", lambda *a: self._update())
        shell.audio.connect("changed", lambda *a: self._update())
        shell.battery.connect("changed", lambda *a: self._update())
        shell.bluetooth.connect("changed", lambda *a: self._update())
        shell.recorder.connect("changed", lambda *a: self._update())
        s = settings.get()
        if s:
            s.connect("changed::show-battery-percentage", lambda *a: self._update())
        self._update()

    def _update(self):
        icon, name = self.shell.network.status()
        self.net_icon.set_from_icon_name(icon)
        self.net_icon.set_tooltip_text(name or _("Not connected"))
        self.vol_icon.set_from_icon_name(self.shell.audio.icon_name)
        self.vol_icon.set_visible(self.shell.audio.available)
        self.bt_icon.set_visible(self.shell.bluetooth.powered)
        self.rec_icon.set_visible(self.shell.recorder.recording)
        bat = self.shell.battery
        self.bat_icon.set_visible(bat.present)
        s = settings.get()
        show_pct = s is None or s.get_boolean("show-battery-percentage")
        self.bat_label.set_visible(bat.present and show_pct)
        if bat.present:
            self.bat_icon.set_from_icon_name(bat.icon_name)
            self.bat_label.set_label(f"{bat.percentage:.0f}%")


class AuroraMenu(Gtk.MenuButton):
    """The logo menu: system-wide actions, like the menu in the corner of a Mac."""

    def __init__(self, shell):
        super().__init__(css_classes=["flat", "panel-button", "panel-logo"],
                         tooltip_text=_("Aurora Menu"))
        self.set_child(Gtk.Image(icon_name="aurora-logo-symbolic", pixel_size=16))
        menu = Gio.Menu()
        for section in (
            [(_("About This Computer"), "app.settings::about")],
            [(_("System Settings…"), "app.settings::"),
             (_("App Center…"), "app.software"),
             (_("Dev Hub…"), "app.devhub")],
            [(_("System Health…"), "app.settings::health"), (_("Force Quit…"), "app.force-quit")],
            [(_("Sleep"), "app.suspend"), (_("Restart…"), "app.reboot"),
             (_("Shut Down…"), "app.poweroff")],
            [(_("Lock Screen"), "app.lock"), (_("Log Out"), "app.logout")],
        ):
            sec = Gio.Menu()
            for label, action in section:
                sec.append(label, action)
            menu.append_section(None, sec)
        self.set_menu_model(menu)


class Panel(LayerWindow):
    HEIGHT = 30

    def __init__(self, shell, monitor):
        s = settings.get()
        edge = s.get_string("panel-position") if s else "top"
        super().__init__(shell, "aurora-panel", layer=Layer.TOP,
                         anchors=(edge, "left", "right"), monitor=monitor,
                         exclusive=True, keyboard=Keyboard.ON_DEMAND)
        self.add_css_class("aurora-panel")
        self.add_css_class(f"panel-{edge}")
        self.shell = shell
        self.set_default_size(-1, self.HEIGHT)

        bar = Gtk.CenterBox(css_classes=["panel-bar"])
        bar.set_size_request(-1, self.HEIGHT)

        left = Gtk.Box(spacing=2)
        left.append(AuroraMenu(shell))
        self.app_name = Gtk.Label(css_classes=["panel-app-name"], ellipsize=3,
                                  max_width_chars=40, margin_start=6)
        left.append(self.app_name)
        # Minimized windows, one icon each: a click brings the window back.
        self.minimized = Gtk.Box(spacing=2, margin_start=10, css_classes=["panel-minimized"])
        left.append(self.minimized)
        bar.set_start_widget(left)

        right = Gtk.Box(spacing=2)
        right.append(Tray())
        # Aurora Assistant, one click away (it explains how to turn AI on if it's off).
        assistant = Gtk.Button(icon_name="aurora-assistant-symbolic",
                               tooltip_text=_("Aurora Assistant (Super+Shift+Space)"),
                               css_classes=["flat", "panel-button", "panel-assistant"])
        assistant.connect("clicked", lambda *_: apps.spawn(["aurora-assistant"]))
        if s:
            s.bind("ai-panel-button", assistant, "visible", 0)
        right.append(assistant)
        search = Gtk.Button(icon_name="system-search-symbolic", tooltip_text=_("Search"),
                            css_classes=["flat", "panel-button"])
        search.connect("clicked", lambda *_: shell.launcher.toggle("spotlight"))
        right.append(search)
        self.status = StatusArea(shell)
        right.append(self.status)
        clock = self.clock = Clock(shell)
        if s and s.get_string("clock-position") == "center":
            bar.set_center_widget(clock)
        else:
            right.append(clock)
        bar.set_end_widget(right)

        self.set_child(bar)
        shell.toplevels.connect("changed", lambda *a: self._update_app())
        self._update_app()
        # A menu opened from a shortcut must get the keyboard (Esc, arrows),
        # and give it back when it closes.
        self._menus = (left.get_first_child(), self.status, clock)
        for button in self._menus:
            button.connect("notify::active", self._on_menu_active)
        # Opened from a shortcut, a menu has no pointer grab: its keys arrive at
        # the bar, so the bar closes it on Esc.
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    def _on_key(self, _ctrl, keyval, _code, _state):
        if keyval != Gdk.KEY_Escape:
            return False
        for button in self._menus:
            if button.get_active():
                button.popdown()
                return True
        return False

    def _on_menu_active(self, button, _pspec):
        if button.get_active():
            self.set_keyboard(Keyboard.EXCLUSIVE)
            return
        # NONE first, so the compositor gives the keyboard back to the window
        # (on-demand alone would keep it on the bar), then on-demand again.
        self.set_keyboard(Keyboard.NONE)
        GLib.timeout_add(150, lambda: self.set_keyboard(Keyboard.ON_DEMAND) or False)

    def _update_minimized(self):
        while (c := self.minimized.get_first_child()) is not None:
            self.minimized.remove(c)
        windows = [t for t in self.shell.toplevels.toplevels if t.minimized]
        for t in sorted(windows, key=lambda w: w.serial):
            app = apps.find_app(t.app_id)
            icon = Gtk.Image(pixel_size=16)
            if app and app.get_icon():
                icon.set_from_gicon(app.get_icon())
            else:
                icon.set_from_icon_name("application-x-executable")
            name = app.get_display_name() if app else (t.app_id or "")
            b = Gtk.Button(child=icon, css_classes=["flat", "panel-button", "panel-minimized-item"],
                           tooltip_text=_("{title} (minimized) — click to restore").format(
                               title=t.title or name))
            b.connect("clicked", lambda _b, t=t: t.activate())
            self.minimized.append(b)
        self.minimized.set_visible(bool(windows))

    def _update_app(self):
        self._update_minimized()
        active = self.shell.toplevels.active()
        if active is None:
            self.app_name.set_label(_("Desktop"))
            return
        app = apps.find_app(active.app_id)
        self.app_name.set_label(app.get_display_name() if app else
                                (active.app_id or active.title or ""))
        self.app_name.set_tooltip_text(active.title)

    def _toggle_menu(self, button):
        """Open or close a bar menu from a shortcut. The bar takes the keyboard
        first: a menu opened before that gets no keys (not even Esc)."""
        if button.get_active():
            button.popdown()
            return
        self.set_keyboard(Keyboard.EXCLUSIVE)
        GLib.timeout_add(120, lambda: button.popup() or False)

    def open_quick_settings(self):
        # Toggle, like the other shell commands: a second press closes it.
        self._toggle_menu(self.status)

    def open_notifications(self):
        self._toggle_menu(self.clock)
