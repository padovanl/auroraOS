"""Desktop widgets for developers and gamers: Git projects, containers, GPU and
games. Anything that runs a program (git, podman, docker, nvidia-smi) runs in a
thread, so the desktop never waits for it."""

import glob
import os
import re
import shutil
import subprocess
import threading

from gi.repository import GLib, Gtk, Pango

from aurora import apps
from aurora.i18n import N_, _, ngettext
from aurora.shell.widgets import DesktopWidget, _ring, accent_rgba


def _run(argv, timeout=8):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _in_thread(work, done):
    def run():
        result = work()
        GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=run, daemon=True).start()


# --- parsers (pure, tested) ----------------------------------------------------

def parse_git_status(text):
    """(branch, ahead, behind, changed files) from `git status --porcelain=v2 --branch`."""
    branch, ahead, behind, changes = "", 0, 0, 0
    for line in (text or "").splitlines():
        if line.startswith("# branch.head "):
            branch = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            m = re.match(r"# branch\.ab \+(\d+) -(\d+)", line)
            if m:
                ahead, behind = int(m.group(1)), int(m.group(2))
        elif line and not line.startswith("#"):
            changes += 1
    return branch, ahead, behind, changes


def parse_acf(text):
    """Flat key → value pairs of a Steam appmanifest (.acf)."""
    return dict(re.findall(r'^\s*"(\w+)"\s+"([^"]*)"', text or "", re.M))


def parse_nvidia(line):
    """name, utilization %, temperature °C, memory used MiB, total MiB from nvidia-smi CSV."""
    parts = [p.strip() for p in (line or "").split(",")]
    if len(parts) < 5:
        return None
    try:
        return parts[0], float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
    except ValueError:
        return None


def parse_listening(text):
    """[(port, program)] of TCP servers on this computer from `ss -ltnpH`,
    user ports only (1024 and up), sorted, one entry per port."""
    found = {}
    for line in (text or "").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        address = fields[3]
        host, _sep, port = address.rpartition(":")
        if not port.isdigit() or int(port) < 1024:
            continue
        if host.strip("[]").split("%")[0] not in ("127.0.0.1", "0.0.0.0", "::", "::1", "*",
                                                   "localhost"):
            continue
        m = re.search(r'users:\(\("([^"]+)"', line)
        found.setdefault(int(port), m.group(1) if m else "")
    return sorted(found.items())


# --- Git projects ----------------------------------------------------------------

class ProjectsWidget(DesktopWidget):
    kind = "projects"
    wide = True
    interval = 60

    def build(self):
        self.body.append(Gtk.Label(label=_("Projects"), xalign=0, css_classes=["widget-title"]))
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, vexpand=True)
        self.body.append(self.list)
        self._busy = False

    def update(self):
        if self._busy:
            return
        self._busy = True
        _in_thread(self._collect, self._show)

    def _collect(self):
        from aurora.shell.search import find_projects

        def recency(path):
            try:
                return os.path.getmtime(os.path.join(path, ".git", "index"))
            except OSError:
                return 0
        rows = []
        for path in sorted(find_projects(), key=recency, reverse=True)[:4]:
            status = _run(["git", "-C", path, "status", "--porcelain=v2", "--branch"])
            rows.append((path, *parse_git_status(status)))
        return rows

    def _show(self, rows):
        self._busy = False
        while (child := self.list.get_first_child()) is not None:
            self.list.remove(child)
        if not rows:
            self.list.append(Gtk.Label(
                label=_("Git repositories in ~/Projects, ~/src or ~/code appear here"),
                wrap=True, xalign=0, css_classes=["widget-caption"]))
            return
        for path, branch, ahead, behind, changes in rows:
            button = Gtk.Button(css_classes=["flat", "widget-row"])
            row = Gtk.Box(spacing=8)
            row.append(Gtk.Image(icon_name="folder-code-symbolic" if changes == 0
                                 else "document-edit-symbolic"))
            name = Gtk.Label(label=os.path.basename(path), xalign=0, hexpand=True,
                             ellipsize=Pango.EllipsizeMode.END)
            row.append(name)
            badges = [branch] if branch else []
            if changes:
                badges.append(ngettext("{n} change", "{n} changes", changes).format(n=changes))
            if ahead:
                badges.append(f"↑{ahead}")
            if behind:
                badges.append(f"↓{behind}")
            row.append(Gtk.Label(label="  ·  ".join(badges), css_classes=["widget-caption"],
                                 ellipsize=Pango.EllipsizeMode.START, max_width_chars=26))
            button.set_child(row)
            button.set_tooltip_text(path)
            button.connect("clicked", lambda _b, p=path: self._open(p))
            self.list.append(button)

    def _open(self, path):
        if not self.layer.editing:
            from aurora.shell.search import open_project
            open_project(path)


# --- local servers ---------------------------------------------------------------

class PortsWidget(DesktopWidget):
    """Dev servers listening on this computer (Vite, Django, Jupyter…); a click
    opens one in the browser."""
    kind = "ports"
    interval = 5
    # System services that listen but aren't something to open in a browser.
    IGNORE = {"kdeconnectd", "systemd-resolve", "cupsd", "avahi-daemon", "sshd", "ollama"}

    def build(self):
        self.body.append(Gtk.Label(label=_("Local Servers"), xalign=0,
                                   css_classes=["widget-title"]))
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, vexpand=True)
        self.body.append(self.list)
        self._shown = None
        self._busy = False

    def update(self):
        if self._busy:
            return
        self._busy = True
        _in_thread(lambda: parse_listening(_run(["ss", "-ltnpH"])), self._show)

    def _show(self, servers):
        self._busy = False
        servers = [(p, n) for p, n in servers if n not in self.IGNORE][:4]
        if servers == self._shown:
            return
        self._shown = servers
        while (child := self.list.get_first_child()) is not None:
            self.list.remove(child)
        if not servers:
            self.list.append(Gtk.Label(label=_("Start a dev server and it appears here"),
                                       wrap=True, xalign=0, vexpand=True,
                                       css_classes=["widget-caption"]))
            return
        for port, name in servers:
            button = Gtk.Button(css_classes=["flat", "widget-row"],
                                tooltip_text=f"http://localhost:{port}")
            row = Gtk.Box(spacing=8)
            row.append(Gtk.Label(label=f":{port}", css_classes=["widget-port", "numeric"]))
            row.append(Gtk.Label(label=name or _("server"), xalign=0, hexpand=True,
                                 ellipsize=Pango.EllipsizeMode.END,
                                 css_classes=["widget-caption"]))
            button.set_child(row)
            button.connect("clicked", lambda _b, p=port: self.layer.editing or apps.spawn(
                ["xdg-open", f"http://localhost:{p}"]))
            self.list.append(button)


# --- performance --------------------------------------------------------------------

class PerformanceWidget(DesktopWidget):
    """The power profile, one click away before a game: Performance, Balanced or
    Power Saver (the same setting as in the Control Center)."""
    kind = "performance"

    LABELS = {"performance": ("power-profile-performance-symbolic", N_("Performance")),
              "balanced": ("power-profile-balanced-symbolic", N_("Balanced")),
              "power-saver": ("power-profile-power-saver-symbolic", N_("Power Saver"))}

    def build(self):
        self.body.append(Gtk.Label(label=_("Performance"), xalign=0,
                                   css_classes=["widget-title"]))
        self.buttons = {}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, vexpand=True,
                      valign=Gtk.Align.CENTER)
        profiles = self.layer.shell.power_profiles
        for profile in PowerProfilesOrder:
            icon, label = self.LABELS[profile]
            button = Gtk.ToggleButton(css_classes=["flat", "widget-profile"])
            row = Gtk.Box(spacing=8)
            row.append(Gtk.Image(icon_name=icon))
            row.append(Gtk.Label(label=_(label), xalign=0))
            button.set_child(row)
            button.connect("clicked", lambda b, p=profile: self._choose(b, p))
            box.append(button)
            self.buttons[profile] = button
        self.body.append(box)
        self.note = Gtk.Label(label=_("Power profiles aren't available here"), wrap=True,
                              xalign=0, css_classes=["widget-caption"], visible=False)
        self.body.append(self.note)
        self._handler = profiles.connect("changed", lambda *_a: self.update())
        self.connect("destroy", lambda *_a: profiles.disconnect(self._handler))
        self._syncing = False

    def _choose(self, button, profile):
        if self._syncing:
            return
        if self.layer.editing:
            self.update()
            return
        self.layer.shell.power_profiles.set(profile)   # emits "changed": GTK thread only

    def update(self):
        profiles = self.layer.shell.power_profiles
        self._syncing = True
        for profile, button in self.buttons.items():
            button.set_active(profiles.available and profile == profiles.current)
            button.set_sensitive(profiles.available)
        self._syncing = False
        self.note.set_visible(not profiles.available)


PowerProfilesOrder = ("performance", "balanced", "power-saver")


# --- containers ------------------------------------------------------------------

class ContainersWidget(DesktopWidget):
    kind = "containers"
    interval = 10

    def build(self):
        self.count = Gtk.Label(css_classes=["widget-big", "numeric"], xalign=0)
        self.caption = Gtk.Label(xalign=0, css_classes=["widget-caption"], wrap=True,
                                 lines=2, ellipsize=Pango.EllipsizeMode.END)
        self.names = Gtk.Label(xalign=0, css_classes=["widget-caption"], wrap=True,
                               lines=3, ellipsize=Pango.EllipsizeMode.END, vexpand=True,
                               valign=Gtk.Align.START)
        self.body.append(Gtk.Label(label=_("Containers"), xalign=0,
                                   css_classes=["widget-title"]))
        for w in (self.count, self.caption, self.names):
            self.body.append(w)
        self._busy = False

    def update(self):
        if self._busy:
            return
        self._busy = True
        _in_thread(self._collect, self._show)

    @staticmethod
    def _collect():
        names = []
        engines = []
        if shutil.which("podman"):
            out = _run(["podman", "ps", "--format", "{{.Names}}"])
            if out is not None:
                engines.append("Podman")
                names += out.split()
        # Docker starts on demand through its socket: only ask a daemon that is
        # already running, or the widget would start Docker at every login.
        if shutil.which("docker") and subprocess.run(
                ["systemctl", "is-active", "--quiet", "docker.service"]).returncode == 0:
            out = _run(["docker", "ps", "--format", "{{.Names}}"])
            if out is not None:
                engines.append("Docker")
                names += out.split()
        return engines, names

    def _show(self, result):
        self._busy = False
        engines, names = result
        self.count.set_label(str(len(names)))
        if not engines:
            self.caption.set_label(_("No container engine running"))
        else:
            self.caption.set_label(ngettext("{n} running", "{n} running", len(names)).format(
                n=len(names)) + " · " + " + ".join(engines))
        self.names.set_label("\n".join(names[:4]))


# --- GPU -----------------------------------------------------------------------

class GpuWidget(DesktopWidget):
    kind = "gpu"
    interval = 3

    def build(self):
        self.ring = Gtk.DrawingArea(content_width=64, content_height=64, vexpand=True)
        self.ring.set_draw_func(self._draw)
        self.name = Gtk.Label(css_classes=["widget-caption"], ellipsize=Pango.EllipsizeMode.END)
        self.details = Gtk.Label(css_classes=["widget-caption", "numeric"], wrap=True,
                                 lines=2, ellipsize=Pango.EllipsizeMode.END, justify=Gtk.Justification.CENTER)
        for w in (self.ring, self.name, self.details):
            self.body.append(w)
        self.usage = None
        self._busy = False

    def update(self):
        if self._busy:
            return
        self._busy = True
        _in_thread(self.read, self._show)

    @staticmethod
    def read():
        """{name, usage %, temp °C or None, vram (used, total) bytes or None}, or None."""
        if shutil.which("nvidia-smi"):
            out = _run(["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu,"
                        "memory.used,memory.total", "--format=csv,noheader,nounits"])
            parsed = parse_nvidia(out.splitlines()[0]) if out else None
            if parsed:
                name, usage, temp, used, total = parsed
                return {"name": name, "usage": usage, "temp": temp,
                        "vram": (used * 2 ** 20, total * 2 ** 20)}
        for device in sorted(glob.glob("/sys/class/drm/card[0-9]/device")):
            busy = os.path.join(device, "gpu_busy_percent")   # amdgpu
            if not os.path.exists(busy):
                continue
            try:
                with open(busy) as f:
                    usage = float(f.read())
            except (OSError, ValueError):
                continue
            info = {"name": _("Graphics card"), "usage": usage, "temp": None, "vram": None}
            try:
                with open(os.path.join(device, "mem_info_vram_used")) as f:
                    used = int(f.read())
                with open(os.path.join(device, "mem_info_vram_total")) as f:
                    info["vram"] = (used, int(f.read()))
            except (OSError, ValueError):
                pass
            for temp in glob.glob(os.path.join(device, "hwmon", "hwmon*", "temp1_input")):
                try:
                    with open(temp) as f:
                        info["temp"] = int(f.read()) / 1000
                except (OSError, ValueError):
                    pass
            return info
        return None

    def _show(self, info):
        self._busy = False
        if info is None:
            self.usage = None
            self.name.set_label(_("GPU"))
            self.details.set_label(_("No statistics from this graphics driver"))
        else:
            self.usage = info["usage"]
            self.name.set_label(info["name"])
            parts = []
            if info["temp"] is not None:
                parts.append(f"{info['temp']:.0f} °C")
            if info["vram"]:
                parts.append(_("{used} of {total}").format(
                    used=GLib.format_size(int(info["vram"][0])),
                    total=GLib.format_size(int(info["vram"][1]))))
            self.details.set_label("  ·  ".join(parts))
        self.ring.queue_draw()

    def _draw(self, _area, cr, width, height):
        fg = self.ring.get_color()
        value = (self.usage or 0) / 100
        _ring(cr, width / 2, height / 2, min(width, height) / 2 - 8, value, accent_rgba(),
              (fg.red, fg.green, fg.blue, 0.12))
        from gi.repository import PangoCairo
        layout = self.ring.create_pango_layout("")
        layout.set_markup(f"<b>{self.usage:.0f}%</b>" if self.usage is not None else "—", -1)
        w, h = layout.get_pixel_size()
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 1)
        cr.move_to(width / 2 - w / 2, height / 2 - h / 2)
        PangoCairo.show_layout(cr, layout)


# --- games ------------------------------------------------------------------------

STEAM_ROOTS = ("~/.var/app/com.valvesoftware.Steam/.local/share/Steam",
               "~/.local/share/Steam", "~/.steam/steam")
# Steam's own tools, not games.
STEAM_TOOLS = re.compile(r"Proton|Steam Linux Runtime|Steamworks|Redistributable", re.I)


def steam_games(roots=STEAM_ROOTS):
    """[(appid, name, last played, cover path or None)], most recently played first."""
    games, seen = [], set()
    for root in roots:
        root = os.path.expanduser(root)
        libraries = {os.path.join(root, "steamapps")}
        try:
            with open(os.path.join(root, "steamapps", "libraryfolders.vdf")) as f:
                for path in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                    libraries.add(os.path.join(path, "steamapps"))
        except OSError:
            pass
        for library in libraries:
            for manifest in glob.glob(os.path.join(library, "appmanifest_*.acf")):
                try:
                    with open(manifest, encoding="utf-8", errors="replace") as f:
                        acf = parse_acf(f.read())
                except OSError:
                    continue
                appid, name = acf.get("appid"), acf.get("name", "")
                if not appid or appid in seen or STEAM_TOOLS.search(name):
                    continue
                seen.add(appid)
                cover = None
                for pattern in (f"appcache/librarycache/{appid}_library_600x900.jpg",
                                f"appcache/librarycache/{appid}/library_600x900.jpg",
                                f"appcache/librarycache/{appid}_header.jpg",
                                f"appcache/librarycache/{appid}/header.jpg"):
                    candidate = os.path.join(root, pattern)
                    if os.path.exists(candidate):
                        cover = candidate
                        break
                games.append((appid, name, int(acf.get("LastPlayed", "0") or 0), cover))
    games.sort(key=lambda g: g[2], reverse=True)
    return games


class GamesWidget(DesktopWidget):
    kind = "games"
    wide = True
    interval = 15 * 60

    def build(self):
        head = Gtk.Box()
        head.append(Gtk.Label(label=_("Games"), xalign=0, hexpand=True,
                              css_classes=["widget-title"]))
        hub = Gtk.Button(icon_name="go-next-symbolic", css_classes=["flat", "circular"],
                         tooltip_text=_("Open Game Hub"))
        hub.connect("clicked", lambda *_: self.layer.editing or apps.spawn(["aurora-gamehub"]))
        head.append(hub)
        self.body.append(head)
        self.row = Gtk.Box(spacing=8, vexpand=True, homogeneous=True)
        self.body.append(self.row)
        self._busy = False

    def update(self):
        if self._busy:
            return
        self._busy = True
        _in_thread(lambda: steam_games()[:4], self._show)

    def _show(self, games):
        self._busy = False
        while (child := self.row.get_first_child()) is not None:
            self.row.remove(child)
        if not games:
            self.row.append(Gtk.Label(label=_("Install Steam from Game Hub and your games "
                                              "appear here"),
                                      wrap=True, xalign=0, css_classes=["widget-caption"]))
            return
        for appid, name, _played, cover in games:
            button = Gtk.Button(css_classes=["flat", "widget-game"], tooltip_text=name)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            if cover:
                picture = Gtk.Picture.new_for_filename(cover)
                picture.set_content_fit(Gtk.ContentFit.COVER)
                picture.set_size_request(58, 80)
                picture.add_css_class("widget-cover")
                inner.append(picture)
            else:
                inner.append(Gtk.Image(icon_name="applications-games-symbolic", pixel_size=40,
                                       vexpand=True))
            inner.append(Gtk.Label(label=name, css_classes=["widget-caption"],
                                   ellipsize=Pango.EllipsizeMode.END, max_width_chars=10))
            button.set_child(inner)
            button.connect("clicked", lambda _b, a=appid: self._play(a))
            self.row.append(button)

    def _play(self, appid):
        if not self.layer.editing:
            apps.spawn(["xdg-open", f"steam://rungameid/{appid}"])

