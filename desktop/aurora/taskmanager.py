"""Task Manager (Ctrl+Shift+Esc), like Windows': what's running and how hard the
computer is working.

Processes: your apps, each with its processes folded underneath, then background
processes and, when asked, the system's; CPU, memory and disk for each, sorted
by any column; End Task asks an app to quit, and Kill stops it at once.
Performance: processor, memory, disk and network over the last minute.
Startup apps: what starts when you log in, each with a switch. Services: the
system's and your own, with start, stop and restart.
"""

import os
import subprocess
import sys
import threading
from collections import deque

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from aurora import plaintext  # noqa: E402,F401  (rows and toasts: plain text)

from aurora import procinfo  # noqa: E402
from aurora.i18n import _  # noqa: E402

INTERVAL_S = 1.5
HISTORY = 60
USER_AUTOSTART = os.path.join(GLib.get_user_config_dir(), "autostart")
SYSTEM_AUTOSTART = [os.path.join(d, "autostart") for d in GLib.get_system_config_dirs()]


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def human_rate(n):
    return human_size(n) + "/s" if n >= 1 else "0 MB/s"


def app_info(app_id):
    from aurora import apps
    app = apps.find_app(app_id.removesuffix(".desktop"))
    if app is not None:
        return app
    try:
        return Gio.DesktopAppInfo.new(app_id if app_id.endswith(".desktop")
                                      else app_id + ".desktop")
    except TypeError:
        return None


def aurora_accent():
    """The accent color chosen in Settings → Appearance."""
    from aurora import settings
    from aurora.look import ACCENT_HEX
    iface = settings.interface()
    rgba = Gdk.RGBA()
    rgba.parse(ACCENT_HEX.get(iface.get_string("accent-color"), "#a970ff") if iface
               else "#a970ff")
    return rgba


def open_apps():
    """[(desktop id, executable)] of the apps with an open window, from the
    shell (labwc doesn't say which process owns a window), or None."""
    import json
    import shutil
    import subprocess
    from aurora import apps
    try:
        out = subprocess.run(["aurora-shell", "windows"], capture_output=True, text=True,
                             timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = []
    for line in out.splitlines():
        try:
            app_id = json.loads(line).get("app_id") or ""
        except ValueError:
            continue
        info = apps.find_app(app_id)
        if info is not None:
            exe = os.path.basename(shutil.which(info.get_executable() or "") or
                                   info.get_executable() or "")
            found.append((info.get_id(), exe))
        else:
            found.append(("", app_id))
    return found


def window_pids():
    """{process id: app id} of the open windows (Wayfire), or None elsewhere."""
    from aurora import wayfirelayout
    try:
        return {v["pid"]: v.get("app-id") or "" for v in wayfirelayout.views()
                if v.get("role") == "toplevel" and v.get("pid")}
    except (OSError, ValueError, ConnectionError, KeyError):
        return None


# --- the rows of the Processes list -------------------------------------------------

class Row(GObject.Object):
    """One line: a group header, an app, or a process (under an app or alone)."""
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, key, kind):
        super().__init__()
        self.key, self.kind = key, kind
        self.name, self.icon, self.detail = "", None, ""
        self.cpu, self.mem, self.disk = 0.0, 0, 0.0
        self.pids, self.depth, self.count, self.expanded = [], 0, 0, False
        self.exe = ""


class Processes(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.sampler = procinfo.Sampler()
        self.rows = {}
        self.expanded = set()
        self.show_system = False
        self.sort_key, self.sort_desc = "cpu", True
        self.store = Gio.ListStore.new(Row)
        self.selection = Gtk.SingleSelection(model=self.store, autoselect=False,
                                             can_unselect=True)
        self.selection.connect("notify::selected", lambda *_a: self._sync_buttons())

        self.view = Gtk.ColumnView(model=self.selection, show_row_separators=False,
                                   css_classes=["taskmanager-list"], vexpand=True,
                                   reorderable=False)
        for key, title, expand, render in (
                ("name", _("Name"), True, self._render_name),
                ("cpu", _("CPU"), False, lambda r: f"{r.cpu:.1f}%" if r.kind != "header" else ""),
                ("mem", _("Memory"), False,
                 lambda r: human_size(r.mem) if r.kind != "header" else ""),
                ("disk", _("Disk"), False,
                 lambda r: human_rate(r.disk) if r.kind != "header" else "")):
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._setup, key)
            factory.connect("bind", self._bind, key, render)
            factory.connect("unbind", self._unbind)
            column = Gtk.ColumnViewColumn(title=title, factory=factory, expand=expand,
                                          resizable=True)
            column.set_sorter(Gtk.CustomSorter.new(lambda *_a: 0))
            column.key = key
            if not expand:
                column.set_fixed_width(110)
            self.view.append_column(column)
        self.view.get_sorter().connect("changed", self._sort_changed)
        self.view.connect("activate", lambda _v, pos: self._toggle(self.store.get_item(pos)))
        menu = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        menu.connect("pressed", self._context_menu)
        self.view.add_controller(menu)
        scroller = Gtk.ScrolledWindow(child=self.view, vexpand=True)
        self.append(scroller)

        bar = Gtk.Box(spacing=8, margin_top=8, margin_bottom=8, margin_start=12,
                      margin_end=12)
        self.summary = Gtk.Label(xalign=0, hexpand=True, css_classes=["dim-label"])
        bar.append(self.summary)
        system = Gtk.CheckButton(label=_("Show system processes"))
        system.connect("toggled", lambda b: (setattr(self, "show_system", b.get_active()),
                                             self.refresh()))
        bar.append(system)
        self.kill_button = Gtk.Button(label=_("Kill"), sensitive=False,
                                      tooltip_text=_("Stop at once, without saving"))
        self.kill_button.connect("clicked", lambda *_a: self._end(force=True))
        self.end_button = Gtk.Button(label=_("End Task"), sensitive=False,
                                     css_classes=["destructive-action"])
        self.end_button.connect("clicked", lambda *_a: self._end(force=False))
        bar.append(self.kill_button)
        bar.append(self.end_button)
        self.append(bar)
        self._last = None

    # cells
    @staticmethod
    def _setup(_factory, item, key):
        if key == "name":
            box = Gtk.Box(spacing=8)
            arrow = Gtk.Image(icon_name="pan-end-symbolic", pixel_size=12)
            icon = Gtk.Image(pixel_size=20)
            label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, hexpand=True)
            for w in (arrow, icon, label):
                box.append(w)
            item.set_child(box)
        else:
            item.set_child(Gtk.Label(xalign=1, css_classes=["numeric"]))

    def _bind(self, _factory, item, key, render):
        row = item.get_item()
        child = item.get_child()

        def update(*_a):
            if key == "name":
                arrow = child.get_first_child()
                icon = arrow.get_next_sibling()
                label = icon.get_next_sibling()
                self._render_name(row, arrow, icon, label)
                (child.add_css_class if row.kind == "header" else
                 child.remove_css_class)("taskmanager-header")
            else:
                child.set_label(render(row))
                heat = min(row.cpu / 50, 1.0) if key == "cpu" else \
                    min(row.mem / (2 << 30), 1.0) if key == "mem" else 0
                for level in ("hot1", "hot2", "hot3"):
                    child.remove_css_class(level)
                if row.kind != "header" and heat > 0.05:
                    child.add_css_class("hot3" if heat > 0.66 else "hot2" if heat > 0.33
                                        else "hot1")
        item.handler = row.connect("changed", update)
        item.row = row
        update()

    @staticmethod
    def _unbind(_factory, item):
        if getattr(item, "row", None) is not None:
            item.row.disconnect(item.handler)
            item.row = None

    @staticmethod
    def _render_name(row, arrow=None, icon=None, label=None):
        if arrow is None:
            return row.name
        arrow.set_opacity(1 if row.kind == "app" and row.count > 1 else 0)
        arrow.set_from_icon_name("pan-down-symbolic" if row.expanded else "pan-end-symbolic")
        arrow.set_margin_start(row.depth * 22)
        icon.set_visible(row.kind != "header")
        if row.icon is not None:
            icon.set_from_gicon(row.icon)
        else:
            icon.set_from_icon_name("application-x-executable-symbolic")
        text = row.name + (f" ({row.count})" if row.kind == "app" and row.count > 1 else "")
        label.set_label(text)

    # data
    def refresh(self):
        if self._last is not None:
            return
        self._last = True

        def work():
            procs = self.sampler.sample(INTERVAL_S)
            windows = window_pids()
            GLib.idle_add(self._show, procs, windows,
                          open_apps() if windows is None else None)
        threading.Thread(target=work, daemon=True).start()

    def _row(self, key, kind):
        row = self.rows.get(key)
        if row is None or row.kind != kind:
            row = Row(key, kind)
            self.rows[key] = row
        return row

    def _metric(self, row):
        return {"name": row.name.lower(), "cpu": row.cpu, "mem": row.mem,
                "disk": row.disk}[self.sort_key]

    def _show(self, procs, windows, open_apps=None):
        self._last = None
        groups = procinfo.group(procs, windows=windows, open_apps=open_apps)
        ordered = []

        def fill(row, members):
            row.cpu = sum(p.cpu for p in members)
            row.mem = sum(p.rss for p in members)
            row.disk = sum(p.disk for p in members)
            row.pids = [p.pid for p in members]

        def section(title, key, rows):
            if not rows:
                return
            header = self._row(key, "header")
            header.name = f"{title} ({len(rows)})"
            ordered.append(header)
            rows.sort(key=self._metric, reverse=self.sort_desc)
            for r in rows:
                ordered.append(r)
                if r.kind == "app" and r.expanded and r.count > 1:
                    kids = []
                    for pid in r.pids:
                        p = procs[pid]
                        kid = self._row(f"pid:{pid}", "proc")
                        kid.name, kid.icon, kid.depth = procinfo.display_name(p), None, 1
                        kid.cpu, kid.mem, kid.disk, kid.pids = p.cpu, p.rss, p.disk, [pid]
                        kid.exe = p.exe
                        kids.append(kid)
                    kids.sort(key=self._metric, reverse=self.sort_desc)
                    ordered.extend(kids)

        app_rows = []
        for app_id, members in groups["apps"].items():
            row = self._row(f"app:{app_id}", "app")
            info = app_info(app_id)
            row.name = info.get_display_name() if info else app_id.removesuffix(".desktop")
            row.icon = info.get_icon() if info else None
            row.count = len(members)
            row.expanded = row.key in self.expanded
            row.exe = next((p.exe for p in members if p.exe), "")
            fill(row, members)
            app_rows.append(row)

        def singles(members, prefix):
            out = []
            for p in members:
                if p.rss == 0:          # kernel threads
                    continue
                row = self._row(f"{prefix}{p.pid}", "proc")
                info = app_info(p.app) if p.app else None
                row.name = info.get_display_name() if info else procinfo.display_name(p)
                row.icon = info.get_icon() if info else None
                row.depth, row.count, row.exe = 0, 1, p.exe
                fill(row, [p])
                out.append(row)
            return out
        section(_("Apps"), "h:apps", app_rows)
        section(_("Background processes"), "h:bg", singles(groups["background"], "bg:"))
        if self.show_system:
            section(_("System processes"), "h:sys", singles(groups["system"], "sys:"))

        # Replace the list only when its lines change; otherwise update in place
        # (keeps the selection and scroll position).
        current = [self.store.get_item(i) for i in range(self.store.get_n_items())]
        if [r.key for r in current] != [r.key for r in ordered]:
            selected = self.selection.get_selected_item()
            self.store.splice(0, len(current), ordered)
            if selected is not None and selected in ordered:
                self.selection.set_selected(ordered.index(selected))
            else:
                self.selection.set_selected(Gtk.INVALID_LIST_POSITION)
        for r in ordered:
            r.emit("changed")
        total_cpu = sum(p.cpu for p in procs.values())
        self.summary.set_label(_("{n} processes · CPU {cpu:.0f}%").format(
            n=len(procs), cpu=min(total_cpu, 100)))
        self._sync_buttons()
        return False

    def _sort_changed(self, sorter, _change):
        column = sorter.get_primary_sort_column()
        if column is None:
            return
        self.sort_key = column.key
        self.sort_desc = sorter.get_primary_sort_order() == Gtk.SortType.DESCENDING
        if column.key == "name":
            self.sort_desc = not self.sort_desc
        self.refresh()

    def _toggle(self, row):
        if row is None or row.kind != "app" or row.count < 2:
            return
        (self.expanded.discard if row.key in self.expanded else self.expanded.add)(row.key)
        self.refresh()

    # actions
    def _selected(self):
        row = self.selection.get_selected_item()
        return row if row is not None and row.kind != "header" else None

    def _sync_buttons(self):
        row = self._selected()
        for b in (self.end_button, self.kill_button):
            b.set_sensitive(row is not None)

    def _end(self, force):
        row = self._selected()
        if row is None:
            return
        failed = procinfo.end(row.pids, force=force)
        if failed:
            self.window.toast(_("Only the administrator can stop {name}").format(name=row.name))
        GLib.timeout_add(400, lambda: self.refresh() or False)

    def _context_menu(self, gesture, _n, x, y):
        row = self._selected()
        if row is None:
            return
        pop = Gtk.Popover(has_arrow=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entries = [(_("End Task"), lambda: self._end(False)), (_("Kill"), lambda: self._end(True))]
        if row.exe:
            entries.append((_("Open File Location"), lambda: subprocess.Popen(
                ["aurora-files", os.path.dirname(row.exe)])))
        if row.kind == "app" and row.count > 1:
            entries.insert(0, (_("Collapse") if row.expanded else _("Expand"),
                               lambda: self._toggle(row)))
        for label, cb in entries:
            b = Gtk.Button(label=label, css_classes=["flat"])
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), cb()))
            box.append(b)
        pop.set_child(box)
        pop.set_parent(self.view)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()


# --- Performance ------------------------------------------------------------------

class Graph(Gtk.DrawingArea):
    """The last minute of one measure, filled under the line in the accent color."""

    def __init__(self, maximum=100.0, height=110):
        super().__init__(content_height=height, hexpand=True, css_classes=["taskmanager-graph"])
        self.values = deque([0.0] * HISTORY, maxlen=HISTORY)
        self.maximum = maximum
        self.set_draw_func(self._draw)

    def push(self, value):
        self.values.append(value)
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        color = self.get_color()
        accent = aurora_accent()
        top = max(self.maximum, max(self.values) * 1.15, 1e-9)
        cr.set_source_rgba(color.red, color.green, color.blue, 0.08)
        for i in range(1, 4):
            cr.rectangle(0, height * i / 4, width, 1)
        cr.fill()
        step = width / (HISTORY - 1)
        cr.move_to(0, height)
        for i, v in enumerate(self.values):
            cr.line_to(i * step, height - height * min(v / top, 1))
        cr.line_to(width, height)
        cr.close_path()
        cr.set_source_rgba(accent.red, accent.green, accent.blue, 0.25)
        cr.fill_preserve()
        cr.new_path()
        for i, v in enumerate(self.values):
            cr.line_to(i * step, height - height * min(v / top, 1))
        cr.set_source_rgba(accent.red, accent.green, accent.blue, 1)
        cr.set_line_width(2)
        cr.stroke()


class Card(Gtk.Box):
    def __init__(self, title, maximum=100.0):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                         css_classes=["card", "taskmanager-card"])
        head = Gtk.Box()
        head.append(Gtk.Label(label=title, xalign=0, hexpand=True, css_classes=["title-4"]))
        self.big = Gtk.Label(xalign=1, css_classes=["title-3", "numeric"])
        head.append(self.big)
        self.append(head)
        self.graph = Graph(maximum)
        self.append(self.graph)
        self.facts = Gtk.Grid(column_spacing=18, row_spacing=4)
        self.append(self.facts)
        self._labels = {}

    def fact(self, name, value):
        if name not in self._labels:
            n = len(self._labels)
            self.facts.attach(Gtk.Label(label=name, xalign=0, css_classes=["dim-label"]),
                              (n % 2) * 2, n // 2, 1, 1)
            label = Gtk.Label(xalign=0, css_classes=["numeric"])
            self.facts.attach(label, (n % 2) * 2 + 1, n // 2, 1, 1)
            self._labels[name] = label
        self._labels[name].set_label(value)


class Performance(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER)
        grid = Gtk.Grid(column_spacing=14, row_spacing=14, column_homogeneous=True,
                        margin_top=14, margin_bottom=14, margin_start=14, margin_end=14)
        self.cpu, self.mem = Card(_("Processor")), Card(_("Memory"))
        self.disk, self.net = Card(_("Disk"), maximum=1 << 20), Card(_("Network"), maximum=1 << 17)
        for i, card in enumerate((self.cpu, self.mem, self.disk, self.net)):
            grid.attach(card, i % 2, i // 2, 1, 1)
        self.set_child(grid)
        from aurora.shell import sysmon
        self.sysmon = sysmon
        self._cpu = None
        self._disk = None
        self._net = None
        self.cpu.fact(_("Cores"), str(os.cpu_count() or 1))

    @staticmethod
    def _disk_bytes():
        """Bytes read and written by the whole disks (not partitions) so far."""
        total = 0
        try:
            names = os.listdir("/sys/block")
        except OSError:
            return 0
        for name in names:
            if name.startswith(("loop", "ram", "zram", "dm-", "sr", "fd")):
                continue
            try:
                with open(f"/sys/block/{name}/stat") as f:
                    fields = f.read().split()
                total += (int(fields[2]) + int(fields[6])) * 512
            except (OSError, IndexError, ValueError):
                continue
        return total

    def refresh(self):
        s = self.sysmon
        now = GLib.get_monotonic_time() / 1e6
        with open("/proc/stat") as f:
            times = s.cpu_times(f.read())
        if self._cpu is not None:
            value = s.cpu_percent(self._cpu, times)
            self.cpu.graph.push(value)
            self.cpu.big.set_label(f"{value:.0f}%")
        self._cpu = times
        try:
            freq = [int(open(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq").read())
                    for i in range(os.cpu_count() or 1)]
            self.cpu.fact(_("Speed"), f"{sum(freq) / len(freq) / 1e6:.2f} GHz")
        except (OSError, ValueError):
            pass
        with open("/proc/uptime") as f:
            up = int(float(f.read().split()[0]))
        self.cpu.fact(_("Up time"), f"{up // 86400}:{up % 86400 // 3600:02d}:"
                                    f"{up % 3600 // 60:02d}:{up % 60:02d}")
        with open("/proc/meminfo") as f:
            meminfo = f.read()
        used, total = s.memory(meminfo)
        self.mem.graph.push(100 * used / total if total else 0)
        self.mem.big.set_label(f"{human_size(used)} / {human_size(total)}")
        fields = {line.split(":")[0]: int(line.split()[1]) * 1024
                  for line in meminfo.splitlines() if line.split()[1:2]}
        self.mem.fact(_("Available"), human_size(fields.get("MemAvailable", 0)))
        self.mem.fact(_("Cached"), human_size(fields.get("Cached", 0)))
        swap = fields.get("SwapTotal", 0) - fields.get("SwapFree", 0)
        self.mem.fact(_("Swap in use"), human_size(swap))
        disk = self._disk_bytes()
        if self._disk is not None:
            rate = (disk - self._disk[1]) / max(now - self._disk[0], 0.1)
            self.disk.graph.push(rate)
            self.disk.big.set_label(human_rate(rate))
        self._disk = (now, disk)
        import shutil
        usage = shutil.disk_usage("/")
        self.disk.fact(_("Free space"), human_size(usage.free))
        self.disk.fact(_("Capacity"), human_size(usage.total))
        rx, tx = s.network_bytes()
        if self._net is not None:
            dt = max(now - self._net[0], 0.1)
            down, up_ = (rx - self._net[1]) / dt, (tx - self._net[2]) / dt
            self.net.graph.push(down + up_)
            self.net.big.set_label(human_rate(down + up_))
            self.net.fact(_("Receive"), human_rate(down))
            self.net.fact(_("Send"), human_rate(up_))
        self._net = (now, rx, tx)


# --- Startup apps ---------------------------------------------------------------------

class Startup(Adw.PreferencesPage):
    def __init__(self):
        super().__init__()
        self.group = Adw.PreferencesGroup(
            title=_("Startup Apps"),
            description=_("These start when you log in. Fewer of them means a quicker start."))
        self.add(self.group)
        self._rows = []
        self.refresh()

    def refresh(self):
        for row in self._rows:
            self.group.remove(row)
        self._rows = []
        for entry in procinfo.startup_entries(USER_AUTOSTART, SYSTEM_AUTOSTART):
            row = Adw.SwitchRow(title=entry["name"],
                                subtitle=entry["exec"],
                                active=entry["enabled"])
            icon = Gtk.Image(icon_name=entry["icon"] or "application-x-executable",
                             pixel_size=32)
            row.add_prefix(icon)
            row.connect("notify::active", lambda r, _p, e=entry: procinfo.set_startup(
                e, r.get_active(), USER_AUTOSTART, SYSTEM_AUTOSTART))
            self.group.add(row)
            self._rows.append(row)


# --- Services -------------------------------------------------------------------------

def list_services(user):
    cmd = ["systemctl"] + (["--user"] if user else []) + [
        "list-units", "--type=service", "--all", "--no-legend", "--plain", "--no-pager"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    services = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4 and parts[0].endswith(".service"):
            services.append({"name": parts[0], "active": parts[2], "sub": parts[3],
                             "description": parts[4] if len(parts) > 4 else "",
                             "user": user})
    return services


class Services(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        top = Gtk.Box(spacing=8, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
        self.search = Gtk.SearchEntry(placeholder_text=_("Search services"), hexpand=True)
        self.search.connect("search-changed", lambda *_a: self._fill())
        top.append(self.search)
        self.append(top)
        self.list = Gtk.ListBox(css_classes=["boxed-list"], margin_start=12, margin_end=12,
                                margin_bottom=12, selection_mode=Gtk.SelectionMode.NONE)
        self.append(Gtk.ScrolledWindow(child=self.list, vexpand=True))
        self.services = []
        self.refresh()

    def refresh(self):
        def work():
            found = list_services(True) + list_services(False)
            GLib.idle_add(lambda: (setattr(self, "services", found), self._fill(), False)[2])
        threading.Thread(target=work, daemon=True).start()

    def _fill(self):
        while (row := self.list.get_first_child()) is not None:
            self.list.remove(row)
        q = self.search.get_text().strip().lower()
        for svc in self.services:
            if q and q not in (svc["name"] + svc["description"]).lower():
                continue
            row = Adw.ActionRow(title=svc["description"] or svc["name"],
                                subtitle=(
                                    f"{svc['name']} · {svc['sub']}"
                                    + ("  · " + _("yours") if svc["user"] else "")))
            running = svc["active"] == "active"
            dot = Gtk.Box(css_classes=["taskmanager-dot", "on" if running else "off"],
                          valign=Gtk.Align.CENTER)
            row.add_prefix(dot)
            for label, verb, show in ((_("Stop"), "stop", running), (_("Start"), "start", not running),
                                      (_("Restart"), "restart", running)):
                if not show:
                    continue
                b = Gtk.Button(label=label, valign=Gtk.Align.CENTER, css_classes=["flat"])
                b.connect("clicked", lambda _b, s=svc, v=verb: self._act(s, v))
                row.add_suffix(b)
            self.list.append(row)

    def _act(self, svc, verb):
        cmd = ["systemctl", "--user", verb, svc["name"]] if svc["user"] else \
            ["pkexec", "systemctl", verb, svc["name"]]

        def work():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                ok = result.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
            GLib.idle_add(lambda: (self.window.toast(
                _("Done") if ok else _("Couldn't change {name}").format(name=svc["name"])),
                self.refresh(), False)[2])
        threading.Thread(target=work, daemon=True).start()


# --- the window -----------------------------------------------------------------------

CSS = """
.taskmanager-list { background: transparent; }
.taskmanager-header label { font-weight: 800; opacity: 0.7; font-size: 0.9em; }
label.hot1 { background-color: alpha(@accent_bg_color, 0.14); border-radius: 6px; padding: 0 6px; }
label.hot2 { background-color: alpha(@accent_bg_color, 0.30); border-radius: 6px; padding: 0 6px; }
label.hot3 { background-color: alpha(#e5484d, 0.45); border-radius: 6px; padding: 0 6px; }
.taskmanager-card { padding: 16px; }
.taskmanager-dot { min-width: 10px; min-height: 10px; border-radius: 999px; }
.taskmanager-dot.on { background-color: #3ecf8e; }
.taskmanager-dot.off { background-color: alpha(currentColor, 0.25); }
"""


class TaskManager(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Task Manager"), default_width=900,
                         default_height=640)
        self.toasts = Adw.ToastOverlay()
        stack = Adw.ViewStack()
        self.processes = Processes(self)
        self.performance = Performance()
        self.startup = Startup()
        self.services = Services(self)
        stack.add_titled_with_icon(self.processes, "processes", _("Processes"),
                                   "view-list-symbolic")
        stack.add_titled_with_icon(self.performance, "performance", _("Performance"),
                                   "utilities-system-monitor-symbolic")
        stack.add_titled_with_icon(self.startup, "startup", _("Startup Apps"),
                                   "system-run-symbolic")
        stack.add_titled_with_icon(self.services, "services", _("Services"),
                                   "applications-system-symbolic")
        self.stack = stack
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.ViewSwitcher(stack=stack,
                                                 policy=Adw.ViewSwitcherPolicy.WIDE))
        toolbar = Adw.ToolbarView(content=stack)
        toolbar.add_top_bar(header)
        self.toasts.set_child(toolbar)
        self.set_content(self.toasts)
        stack.connect("notify::visible-child-name", lambda *_a: self._tick())
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self._tick()
        self._source = GLib.timeout_add(int(INTERVAL_S * 1000), self._tick)
        self.connect("close-request", lambda *_a: (GLib.source_remove(self._source), False)[1])

    def _tick(self):
        page = self.stack.get_visible_child_name()
        # The list is always sampled, so CPU numbers are ready when you come back.
        self.processes.refresh()
        self.performance.refresh()
        if page == "startup" and not getattr(self, "_startup_seen", False):
            self._startup_seen = True
            self.startup.refresh()
        return GLib.SOURCE_CONTINUE

    def _on_key(self, _ctrl, keyval, _code, state):
        if keyval == Gdk.KEY_Delete and self.stack.get_visible_child_name() == "processes":
            self.processes._end(force=bool(state & Gdk.ModifierType.SHIFT_MASK))
            return True
        return False

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.TaskManager")

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        window = self.get_active_window() or TaskManager(self)
        window.present()


def main():
    return App().run(sys.argv)
