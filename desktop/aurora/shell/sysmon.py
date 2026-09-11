"""System monitor in the top bar: processor and memory at a glance, and a popover
with temperature, network speed and disk space (Settings → Desktop & Dock →
Top Bar → System monitor)."""

import os
import shutil

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from aurora import apps  # noqa: E402
from aurora.i18n import _  # noqa: E402

INTERVAL_S = 2


def cpu_times(stat_text):
    """(busy, total) jiffies from /proc/stat's aggregate "cpu" line."""
    for line in stat_text.splitlines():
        if line.startswith("cpu "):
            values = [int(v) for v in line.split()[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)  # idle + iowait
            total = sum(values[:8])  # guest time is already counted in user/nice
            return total - idle, total
    return 0, 0


def cpu_percent(previous, current):
    busy = current[0] - previous[0]
    total = current[1] - previous[1]
    return max(0.0, min(100.0, 100.0 * busy / total)) if total > 0 else 0.0


def memory(meminfo_text):
    """(used, total) bytes, used as the kernel counts it (total - available)."""
    fields = {}
    for line in meminfo_text.splitlines():
        name, _sep, rest = line.partition(":")
        parts = rest.split()
        if parts:
            fields[name] = int(parts[0]) * 1024
    total = fields.get("MemTotal", 0)
    available = fields.get("MemAvailable", fields.get("MemFree", 0))
    return max(0, total - available), total


def network_bytes(net_dir="/sys/class/net"):
    """(received, sent) bytes over all interfaces except loopback."""
    rx = tx = 0
    try:
        names = os.listdir(net_dir)
    except OSError:
        return 0, 0
    for name in names:
        if name == "lo":
            continue
        try:
            with open(os.path.join(net_dir, name, "statistics/rx_bytes")) as f:
                rx += int(f.read())
            with open(os.path.join(net_dir, name, "statistics/tx_bytes")) as f:
                tx += int(f.read())
        except (OSError, ValueError):
            continue
    return rx, tx


def temperature(hwmon_dir="/sys/class/hwmon"):
    """The processor's temperature in °C, or None (virtual machines have none)."""
    preferred = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz")
    found = {}
    try:
        entries = os.listdir(hwmon_dir)
    except OSError:
        return None
    for entry in entries:
        base = os.path.join(hwmon_dir, entry)
        try:
            with open(os.path.join(base, "name")) as f:
                name = f.read().strip()
            with open(os.path.join(base, "temp1_input")) as f:
                found[name] = int(f.read()) / 1000
        except (OSError, ValueError):
            continue
    for name in preferred:
        if name in found:
            return found[name]
    return None


def human_rate(bytes_per_s):
    for unit, size in (("GB/s", 1e9), ("MB/s", 1e6), ("kB/s", 1e3)):
        if bytes_per_s >= size:
            return f"{bytes_per_s / size:.1f} {unit}"
    return f"{bytes_per_s:.0f} B/s"


def human_size(n):
    return GLib.format_size(int(n))


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


class SystemMonitor(Gtk.MenuButton):
    def __init__(self):
        super().__init__(css_classes=["flat", "panel-button", "panel-sysmon"],
                         tooltip_text=_("System monitor"), always_show_arrow=False)
        box = Gtk.Box(spacing=6)
        box.append(Gtk.Image(icon_name="utilities-system-monitor-symbolic"))
        self.label = Gtk.Label(css_classes=["panel-sysmon-label", "numeric"])
        box.append(self.label)
        self.set_child(box)

        grid = Gtk.Grid(column_spacing=18, row_spacing=8, margin_top=10, margin_bottom=10,
                        margin_start=12, margin_end=12)
        self.rows = {}
        for i, (key, title) in enumerate((("cpu", _("Processor")), ("mem", _("Memory")),
                                          ("temp", _("Temperature")), ("down", _("Download")),
                                          ("up", _("Upload")), ("disk", _("Disk")))):
            name = Gtk.Label(label=title, xalign=0, css_classes=["dim-label"])
            value = Gtk.Label(xalign=1, hexpand=True, css_classes=["numeric"])
            grid.attach(name, 0, i, 1, 1)
            grid.attach(value, 1, i, 1, 1)
            self.rows[key] = (name, value)
        self.cpu_bar = Gtk.LevelBar(min_value=0, max_value=100)
        self.mem_bar = Gtk.LevelBar(min_value=0, max_value=1)
        grid.attach(self.cpu_bar, 0, 6, 2, 1)
        grid.attach(self.mem_bar, 0, 7, 2, 1)
        health = Gtk.Button(label=_("System Health…"), css_classes=["flat"], margin_top=4)
        health.connect("clicked", lambda *_: (self.popdown(),
                                              apps.spawn(["aurora-settings", "--page", "health"])))
        grid.attach(health, 0, 8, 2, 1)
        self.set_popover(Gtk.Popover(child=grid))

        self._cpu = cpu_times(_read("/proc/stat"))
        self._net = network_bytes()
        self._source = 0
        self.connect("map", lambda *_: self._start())
        self.connect("unmap", lambda *_: self._stop())

    def _start(self):
        if not self._source:
            self._update()
            self._source = GLib.timeout_add_seconds(INTERVAL_S, self._update)

    def _stop(self):
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0

    def _update(self):
        cpu = cpu_times(_read("/proc/stat"))
        percent = cpu_percent(self._cpu, cpu)
        self._cpu = cpu
        used, total = memory(_read("/proc/meminfo"))
        net = network_bytes()
        down = max(0, net[0] - self._net[0]) / INTERVAL_S
        up = max(0, net[1] - self._net[1]) / INTERVAL_S
        self._net = net
        mem_fraction = used / total if total else 0.0
        self.label.set_label(f"{percent:.0f}%  {mem_fraction * 100:.0f}%")
        self.set_tooltip_text(_("Processor {cpu}% · Memory {mem}%").format(
            cpu=f"{percent:.0f}", mem=f"{mem_fraction * 100:.0f}"))
        self.rows["cpu"][1].set_label(f"{percent:.0f}%")
        self.rows["mem"][1].set_label(f"{human_size(used)} / {human_size(total)}")
        temp = temperature()
        for widget in self.rows["temp"]:
            widget.set_visible(temp is not None)
        if temp is not None:
            self.rows["temp"][1].set_label(f"{temp:.0f} °C")
        self.rows["down"][1].set_label(human_rate(down))
        self.rows["up"][1].set_label(human_rate(up))
        disk = shutil.disk_usage("/")
        self.rows["disk"][1].set_label(_("{free} free of {total}").format(
            free=human_size(disk.free), total=human_size(disk.total)))
        self.cpu_bar.set_value(percent)
        self.mem_bar.set_value(mem_fraction)
        return GLib.SOURCE_CONTINUE
