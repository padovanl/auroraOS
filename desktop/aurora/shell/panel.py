"""Top bar: Aurora menu, focused app, status indicators, clock."""

import os

from gi.repository import Gdk, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import N_, _
from aurora.shell.layer import Keyboard, Layer, LayerWindow
from aurora.shell.quicksettings import QuickSettings
from aurora.shell.toplevels import window_labels
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
        from aurora import weather
        self._watch = weather.watch(self.refresh)

    def refresh(self):
        from aurora import weather
        s = settings.get()
        if s is not None and not s.get_boolean("weather-widget"):
            self.set_visible(False)
            return
        weather.locate_then(self.refresh)
        loc, self._place = weather.place()
        if loc is None:
            # No city for this time zone (UTC, as in the live system): ask for
            # one instead of hiding. Weather's first city is used from then on.
            self._clear_hours()
            self.icon.set_from_icon_name("find-location-symbolic")
            self.temp.set_label(_("Weather"))
            self.desc.set_label(_("Choose your city in Weather"))
            self.set_visible(True)
            return
        fahrenheit = weather.uses_fahrenheit()
        data = weather.cached(*loc, fahrenheit=fahrenheit)
        if data is not None:
            self._show(data)
            return
        if self._busy:
            return
        self._busy = True
        import threading

        def work():
            try:
                result = weather.fetch(*loc, fahrenheit=fahrenheit)
            except Exception as e:  # noqa: BLE001 - offline is normal
                print(f"aurora: weather unavailable: {e}")
                result = None
            GLib.idle_add(lambda: (self._done(result), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _done(self, data):
        self._busy = False
        if data is not None:
            self._show(data)

    def _clear_hours(self):
        while (c := self.hours.get_first_child()) is not None:
            self.hours.remove(c)

    def _show(self, data):
        from aurora import weather
        text, icon = weather.describe(data["code"], data["is_day"])
        unit = data["unit"]
        self.icon.set_from_icon_name(icon)
        self.temp.set_label(f"{data['temp']:.0f}{unit}")
        summary = _("{sky} · H {high:.0f}° L {low:.0f}°").format(
            sky=_(text), high=data["high"], low=data["low"])
        self.desc.set_label(f"{self._place} · {summary}" if self._place else summary)
        self._clear_hours()
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
        self._date.set_label(now.format("%A, %-d %B %Y").replace("  ", " "))
        self._weather.refresh()

    def _tick(self):
        s = settings.get()
        seconds = s is not None and s.get_boolean("clock-show-seconds")
        fmt_24 = s is None or s.get_string("clock-format") == "24h"
        now = GLib.DateTime.new_now_local()
        time_fmt = ("%H:%M" if fmt_24 else "%l:%M") + (":%S" if seconds else "")
        if not fmt_24:
            time_fmt += " %p"
        self._label.set_label(now.format(f"%a %-d %b  {time_fmt}").replace("  ", " ").strip())
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


class ActivityCenter(Gtk.MenuButton):
    """Recent transfers from Aurora apps, including cross-process progress."""

    def __init__(self):
        super().__init__(icon_name="view-list-symbolic", css_classes=["flat", "panel-button"],
                         tooltip_text=_("Activities"))
        self.pop = Gtk.Popover(has_arrow=False)
        self.pop.add_css_class("aurora-context-menu")
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                            margin_top=12, margin_bottom=12,
                            margin_start=12, margin_end=12)
        self.rows.set_size_request(320, -1)
        self.pop.set_child(self.rows)
        self.pop.connect("show", lambda *_: self.refresh())
        self.set_popover(self.pop)
        GLib.timeout_add_seconds(2, self._tick)
        self._tick()

    def _tick(self):
        from aurora import activities
        items = activities.list_recent()
        self.set_visible(bool(items))
        self.set_tooltip_text(_("Activities ({n} running)").format(
            n=sum(item.get("status") == "running" for item in items)))
        if self.pop.get_visible():
            self.refresh(items)
        return GLib.SOURCE_CONTINUE

    def refresh(self, items=None):
        from aurora import activities
        if items is None:
            items = activities.list_recent()
        while (child := self.rows.get_first_child()) is not None:
            self.rows.remove(child)
        self.rows.append(Gtk.Label(label=_("Activities"), xalign=0,
                                   css_classes=["heading"]))
        if not items:
            self.rows.append(Gtk.Label(label=_("No recent activities"), xalign=0,
                                       css_classes=["dim-label"]))
        for item in items[:8]:
            line = Gtk.Box(spacing=8)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
            text.append(Gtk.Label(label=item.get("label", ""), xalign=0, ellipsize=3))
            state = item.get("status")
            detail = item.get("item") or ""
            if state == "failed":
                detail = item.get("error") or _("Failed")
            elif state == "cancelled":
                detail = _("Cancelled")
            elif state == "finished":
                detail = _("Finished")
            text.append(Gtk.Label(label=detail, xalign=0, ellipsize=3,
                                  css_classes=["dim-label", "caption"]))
            if state == "running":
                progress = item.get("progress", 0)
                if progress:
                    text.append(Gtk.ProgressBar(fraction=max(0, min(1, progress))))
                else:
                    text.append(Gtk.Spinner(spinning=True, halign=Gtk.Align.START))
                line.append(text)
                if item.get("cancellable", True):
                    cancel = Gtk.Button(icon_name="process-stop-symbolic",
                                        tooltip_text=_("Cancel transfer"))
                    cancel.connect("clicked", lambda _b, ident=item["id"]: activities.cancel(ident))
                    line.append(cancel)
            else:
                line.append(text)
            self.rows.append(line)


class StatusArea(Gtk.MenuButton):
    """Network / volume / battery icons; opens the control center."""

    def __init__(self, shell):
        super().__init__(css_classes=["flat", "panel-button", "panel-status"],
                         tooltip_text=_("Control Center · scroll for volume"))
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
        # As on Windows: the wheel over the status icons changes the volume,
        # a middle-click mutes.
        wheel = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL
                                          | Gtk.EventControllerScrollFlags.DISCRETE)
        wheel.connect("scroll", lambda _c, _dx, dy: (shell.handle(
            ["volume", "down" if dy > 0 else "up"]), True)[1])
        self.add_controller(wheel)
        middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle.connect("pressed", lambda *_a: shell.handle(["volume", "mute"]))
        self.add_controller(middle)

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
    """The logo menu: who you are, system-wide actions with their shortcuts,
    and the power choices as round buttons at the bottom."""

    ITEMS = (
        (("computer-symbolic", N_("About This Computer"), "settings", "about", ""),),
        (("emblem-system-symbolic", N_("System Settings"), "settings", "", "Super+I"),
         ("system-software-install-symbolic", N_("App Center"), "software", None, ""),
         ("applications-engineering-symbolic", N_("Dev Hub"), "devhub", None, "")),
        (("utilities-system-monitor-symbolic", N_("System Health"), "settings", "health", ""),
         ("process-stop-symbolic", N_("Task Manager"), "force-quit", None, "Ctrl+Shift+Esc")),
    )
    POWER = (("weather-clear-night-symbolic", N_("Sleep"), "suspend"),
             ("system-reboot-symbolic", N_("Restart"), "reboot"),
             ("system-shutdown-symbolic", N_("Shut Down"), "poweroff"),
             ("system-log-out-symbolic", N_("Log Out"), "logout"))

    def __init__(self, shell):
        super().__init__(css_classes=["flat", "panel-button", "panel-logo"],
                         tooltip_text=_("Aurora Menu"))
        self.shell = shell
        self.set_child(Gtk.Image(icon_name="aurora-logo-symbolic", pixel_size=16))
        pop = Gtk.Popover(has_arrow=False, css_classes=["aurora-menu"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_size_request(300, -1)

        head = Gtk.Box(spacing=12, css_classes=["aurora-menu-head"])
        from gi.repository import Adw
        name = GLib.get_real_name()
        if not name or name == "Unknown":
            name = GLib.get_user_name()
        avatar = Adw.Avatar(size=44, text=name, show_initials=True)
        face = os.path.expanduser("~/.face")
        if os.path.exists(face):
            try:
                avatar.set_custom_image(Gdk.Texture.new_from_filename(face))
            except GLib.Error:
                pass
        head.append(avatar)
        who = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        who.append(Gtk.Label(label=name, xalign=0, css_classes=["aurora-menu-name"]))
        from aurora import VERSION
        who.append(Gtk.Label(label=f"{GLib.get_host_name()} · Aurora OS {VERSION}", xalign=0,
                             css_classes=["aurora-menu-sub"]))
        head.append(who)
        lock = Gtk.Button(icon_name="system-lock-screen-symbolic", hexpand=True,
                          halign=Gtk.Align.END, valign=Gtk.Align.CENTER,
                          css_classes=["circular", "aurora-menu-round"],
                          tooltip_text=_("Lock Screen") + "  (Super+L)")
        lock.connect("clicked", lambda *_a: self._run(pop, "lock", None))
        head.append(lock)
        box.append(head)

        for section in self.ITEMS:
            group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["aurora-menu-group"])
            for icon, label, action, param, keys in section:
                row = Gtk.Button(css_classes=["flat", "aurora-menu-row"])
                inner = Gtk.Box(spacing=12)
                inner.append(Gtk.Image(icon_name=icon))
                inner.append(Gtk.Label(label=_(label), xalign=0, hexpand=True))
                if keys:
                    inner.append(Gtk.Label(label=keys, css_classes=["aurora-menu-keys"]))
                row.set_child(inner)
                row.connect("clicked", lambda _b, a=action, p=param: self._run(pop, a, p))
                group.append(row)
            box.append(group)

        power = Gtk.Box(homogeneous=True, spacing=4, css_classes=["aurora-menu-power"])
        for icon, label, action in self.POWER:
            b = Gtk.Button(css_classes=["flat", "aurora-menu-power-item"], focusable=False)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            inner.append(Gtk.Image(icon_name=icon, css_classes=["aurora-menu-round-icon"],
                                   halign=Gtk.Align.CENTER))
            inner.append(Gtk.Label(label=_(label), css_classes=["aurora-menu-power-label"]))
            b.set_child(inner)
            b.connect("clicked", lambda _b, a=action: self._run(pop, a, None))
            power.append(b)
        box.append(power)
        pop.set_child(box)
        self.set_popover(pop)

    def _run(self, pop, action, param):
        pop.popdown()
        self.shell.activate_action(action, GLib.Variant("s", param) if param is not None
                                   else None)


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
        # Every open window gets one stable switcher button, including minimized ones.
        self.windows = Gtk.Box(spacing=2, css_classes=["panel-windows"])
        self.window_scroll = Gtk.ScrolledWindow(child=self.windows,
                                               hscrollbar_policy=Gtk.PolicyType.NEVER,
                                               vscrollbar_policy=Gtk.PolicyType.NEVER,
                                               propagate_natural_width=True,
                                               max_content_width=650)
        left.append(self.window_scroll)
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
        self.activities = ActivityCenter()
        right.append(self.activities)
        search = Gtk.Button(icon_name="system-search-symbolic", tooltip_text=_("Search"),
                            css_classes=["flat", "panel-button"])
        search.connect("clicked", lambda *_: shell.launcher.toggle("spotlight"))
        right.append(search)
        from aurora.shell.sysmon import SystemMonitor
        self.sysmon = SystemMonitor()
        if s:
            s.bind("panel-system-monitor", self.sysmon, "visible", 0)
        else:
            self.sysmon.set_visible(False)
        right.append(self.sysmon)
        self.status = StatusArea(shell)
        right.append(self.status)
        clock = self.clock = Clock(shell)
        if s and s.get_string("clock-position") == "center":
            bar.set_center_widget(clock)
        else:
            right.append(clock)
        # Windows' "Show desktop" sliver at the far end of the bar.
        peek = Gtk.Button(css_classes=["flat", "panel-show-desktop"],
                          tooltip_text=_("Show Desktop"),
                          visible=s is None or s.get_boolean("show-desktop-button"))
        sliver = Gtk.Box()
        sliver.set_size_request(8, 20)
        peek.set_child(sliver)
        peek.connect("clicked", lambda *_a: shell.toggle_desktop())
        right.append(peek)
        if s is not None:
            s.connect("changed::show-desktop-button",
                      lambda st, k: peek.set_visible(st.get_boolean(k)))
        bar.set_end_widget(right)

        self.set_child(bar)
        shell.toplevels.connect("changed", lambda *a: self._update_windows())
        self._update_windows()
        # A menu opened from a shortcut must get the keyboard (Esc, arrows),
        # and give it back when it closes.
        self._menus = (left.get_first_child(), self.activities,
                       self.status, clock)
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

    def _update_windows(self):
        while (child := self.windows.get_first_child()) is not None:
            self.windows.remove(child)
        windows = sorted(self.shell.toplevels.toplevels, key=lambda w: w.serial)
        labels = window_labels(windows, _("Window"))
        for t in windows:
            app = apps.find_app(t.app_id)
            icon = Gtk.Image(pixel_size=16)
            if app and app.get_icon():
                icon.set_from_gicon(app.get_icon())
            else:
                icon.set_from_icon_name("application-x-executable")
            name = labels.get(t) or (app.get_display_name() if app else t.app_id)
            content = Gtk.Box(spacing=5)
            content.append(icon)
            content.append(Gtk.Label(label=name, ellipsize=3, max_width_chars=16))
            classes = ["flat", "panel-button", "panel-window"]
            if t.activated:
                classes.append("focused")
            if t.minimized:
                classes.append("minimized")
            b = Gtk.Button(child=content, css_classes=classes, tooltip_text=t.title or name)
            b.connect("clicked", lambda _b, t=t: t.activate())
            right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY,
                                     propagation_phase=Gtk.PropagationPhase.CAPTURE)
            right.connect("pressed", self._window_context_menu, t, b)
            b.add_controller(right)
            self.windows.append(b)
        self.window_scroll.set_visible(bool(windows))

    def _window_context_menu(self, gesture, _n, x, y, active, button):
        """Window-specific right-click actions on its stable top-bar button."""
        pop = Gtk.Popover(has_arrow=False, halign=Gtk.Align.START,
                          css_classes=["aurora-context-menu"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                      margin_top=5, margin_bottom=5, margin_start=5, margin_end=5)
        pop.set_child(box)
        pop.set_parent(button)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        app = apps.find_app(active.app_id)
        windows = sorted(self.shell.toplevels.for_app(active.app_id), key=lambda w: w.serial)
        labels = window_labels(windows, _("Window"))

        def add(label, callback, checked=None):
            b = Gtk.Button(css_classes=["flat", "context-action"])
            row = Gtk.Box(spacing=8)
            if checked is not None:  # a window: a check mark on the focused one
                row.append(Gtk.Image(icon_name="object-select-symbolic" if checked else None,
                                     pixel_size=16, width_request=16))
            row.append(Gtk.Label(label=label, xalign=0, hexpand=True))
            b.set_child(row)
            b.connect("clicked", lambda *_: (pop.popdown(), callback()))
            box.append(b)
            return b

        for w in windows:
            text = labels[w] + (f"  ({_('Minimized')})" if w.minimized else "")
            add(text, w.activate, checked=w.activated)
        box.append(Gtk.Separator())
        if app is not None:
            actions = list(app.list_actions())
            new_window = next((a for a in actions if a.replace("_", "-").lower()
                               in ("new-window", "new-window-action", "window")), None)
            add(_("New Window"), (lambda: apps.launch(app, action=new_window)) if new_window
                else (lambda: apps.launch(app)))
        add(_("Minimize"), active.minimize)
        add(_("Close Window"), active.close)
        if len(windows) > 1:
            add(_("Quit {n} Windows").format(n=len(windows)),
                lambda: [w.close() for w in windows])
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.popup()
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def _toggle_menu(self, button):
        """Open or close a bar menu from a shortcut. The bar takes the keyboard
        first: a menu opened before that gets no keys (not even Esc)."""
        if button.get_active():
            button.popdown()
            return
        self.shell.close_overlays(self)
        self.set_keyboard(Keyboard.EXCLUSIVE)
        GLib.timeout_add(120, lambda: button.popup() or False)

    def open_quick_settings(self):
        # Toggle, like the other shell commands: a second press closes it.
        self._toggle_menu(self.status)

    def close_menus(self):
        """Close the Control Center and the notification center if open."""
        for button in (self.status, self.clock):
            if button.get_active():
                button.popdown()

    def open_notifications(self):
        self._toggle_menu(self.clock)
