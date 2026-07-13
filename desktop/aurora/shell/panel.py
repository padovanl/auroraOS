"""Top bar: launcher button, focused window, clock, status indicators."""

from gi.repository import GLib, Gtk

from aurora import settings
from aurora.i18n import _
from aurora.shell.layer import Keyboard, Layer, LayerWindow
from aurora.shell.quicksettings import QuickSettings


class Clock(Gtk.MenuButton):
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
    """Network / volume / battery icons; opens quick settings."""

    def __init__(self, shell):
        super().__init__(css_classes=["flat", "panel-button", "panel-status"])
        self.shell = shell
        box = Gtk.Box(spacing=8)
        self.net_icon = Gtk.Image()
        self.vol_icon = Gtk.Image()
        self.bat_icon = Gtk.Image()
        self.bat_label = Gtk.Label(css_classes=["panel-battery-label"])
        for w in (self.net_icon, self.vol_icon, self.bat_icon, self.bat_label):
            box.append(w)
        self.set_child(box)
        self.set_popover(QuickSettings(shell))

        shell.network.connect("changed", lambda *a: self._update())
        shell.audio.connect("changed", lambda *a: self._update())
        shell.battery.connect("changed", lambda *a: self._update())
        self._update()

    def _update(self):
        icon, name = self.shell.network.status()
        self.net_icon.set_from_icon_name(icon)
        self.net_icon.set_tooltip_text(name or _("Not connected"))
        self.vol_icon.set_from_icon_name(self.shell.audio.icon_name)
        self.vol_icon.set_visible(self.shell.audio.available)
        bat = self.shell.battery
        self.bat_icon.set_visible(bat.present)
        self.bat_label.set_visible(bat.present)
        if bat.present:
            self.bat_icon.set_from_icon_name(bat.icon_name)
            self.bat_label.set_label(f"{bat.percentage:.0f}%")


class Panel(LayerWindow):
    HEIGHT = 34

    def __init__(self, shell, monitor):
        super().__init__(shell, "aurora-panel", layer=Layer.TOP,
                         anchors=("top", "left", "right"), monitor=monitor,
                         exclusive=True, keyboard=Keyboard.ON_DEMAND)
        self.add_css_class("aurora-panel")
        self.shell = shell
        self.set_default_size(-1, self.HEIGHT)

        bar = Gtk.CenterBox(css_classes=["panel-bar"])
        bar.set_size_request(-1, self.HEIGHT)

        left = Gtk.Box(spacing=4)
        launcher_btn = Gtk.Button(css_classes=["flat", "panel-button", "panel-logo"],
                                  tooltip_text=_("Applications"))
        logo = Gtk.Box(spacing=6)
        logo.append(Gtk.Image(icon_name="aurora-logo-symbolic", pixel_size=18))
        logo.append(Gtk.Label(label=_("Apps")))
        launcher_btn.set_child(logo)
        launcher_btn.connect("clicked", lambda *_: shell.launcher.toggle())
        left.append(launcher_btn)
        self.window_title = Gtk.Label(css_classes=["panel-title"], ellipsize=3,
                                      max_width_chars=48, margin_start=8)
        left.append(self.window_title)
        bar.set_start_widget(left)

        bar.set_center_widget(Clock(shell))

        right = Gtk.Box(spacing=4)
        self.status = StatusArea(shell)
        right.append(self.status)
        bar.set_end_widget(right)

        self.set_child(bar)
        shell.toplevels.connect("changed", lambda *a: self._update_title())
        self._update_title()

    def _update_title(self):
        active = self.shell.toplevels.active()
        self.window_title.set_label(active.title if active else "")

    def open_quick_settings(self):
        self.status.popup()
