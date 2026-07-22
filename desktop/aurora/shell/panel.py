"""Top bar: Aurora menu, focused app, status indicators, clock."""

from gi.repository import Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.shell.layer import Keyboard, Layer, LayerWindow
from aurora.shell.quicksettings import QuickSettings


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
        self.bat_label.set_visible(bat.present)
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
            [(_("Force Quit…"), "app.force-quit")],
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
        bar.set_start_widget(left)

        right = Gtk.Box(spacing=2)
        search = Gtk.Button(icon_name="system-search-symbolic", tooltip_text=_("Search"),
                            css_classes=["flat", "panel-button"])
        search.connect("clicked", lambda *_: shell.launcher.toggle("spotlight"))
        right.append(search)
        self.status = StatusArea(shell)
        right.append(self.status)
        clock = Clock(shell)
        if s and s.get_string("clock-position") == "center":
            bar.set_center_widget(clock)
        else:
            right.append(clock)
        bar.set_end_widget(right)

        self.set_child(bar)
        shell.toplevels.connect("changed", lambda *a: self._update_app())
        self._update_app()

    def _update_app(self):
        active = self.shell.toplevels.active()
        if active is None:
            self.app_name.set_label(_("Desktop"))
            return
        app = apps.find_app(active.app_id)
        self.app_name.set_label(app.get_display_name() if app else
                                (active.app_id or active.title or ""))
        self.app_name.set_tooltip_text(active.title)

    def open_quick_settings(self):
        self.status.popup()
