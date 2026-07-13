"""Aurora Shell application: owns every desktop surface and handles commands.

Running `aurora-shell` starts the shell. Running it again with a command
forwards the command to the running instance, e.g.:

    aurora-shell launcher
    aurora-shell volume up|down|mute
    aurora-shell brightness up|down
    aurora-shell screenshot [area]
"""

import os
import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from aurora import apps, data_path, settings  # noqa: E402
from aurora.i18n import _  # noqa: E402
from aurora.shell import layer  # noqa: E402
from aurora.shell.dock import Dock  # noqa: E402
from aurora.shell.launcher import Launcher  # noqa: E402
from aurora.shell.monitors import PerMonitor  # noqa: E402
from aurora.shell.notifications import NotificationServer  # noqa: E402
from aurora.shell.osd import OSD  # noqa: E402
from aurora.shell.panel import Panel  # noqa: E402
from aurora.shell.services import Audio, Battery, Brightness, Network, Power  # noqa: E402
from aurora.shell.toplevels import ToplevelTracker  # noqa: E402
from aurora.shell.wallpaper import Wallpaper  # noqa: E402

VOLUME_STEP = 0.05
BRIGHTNESS_STEP = 0.05


class Shell(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Shell",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.started = False
        self._night_light = None

    # --- lifecycle ---

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()
        for name, cb, ptype in (
            ("open-terminal", lambda *_: apps.spawn(["x-terminal-emulator"]), None),
            ("open-files", lambda *_: self._open_files(), None),
            ("settings", lambda _a, p: self.open_settings(p.get_string()), "s"),
            ("launcher", lambda *_: self.launcher.toggle(), None),
        ):
            action = Gio.SimpleAction.new(name, GLib.VariantType(ptype) if ptype else None)
            action.connect("activate", cb)
            self.add_action(action)

    def _start(self):
        if not layer.supported():
            print("aurora-shell: the compositor does not support wlr-layer-shell", file=sys.stderr)
            self.quit()
            return
        self.started = True
        self.hold()
        self.audio = Audio()
        self.brightness = Brightness()
        self.battery = Battery()
        self.network = Network()
        self.power = Power()
        self.toplevels = ToplevelTracker()
        self.notifications = NotificationServer(self)
        self.launcher = Launcher(self)
        self.osd = OSD(self)
        self.wallpapers = PerMonitor(lambda m: Wallpaper(self, m))
        self.panels = PerMonitor(lambda m: Panel(self, m))
        self.docks = PerMonitor(lambda m: Dock(self, m))

        s = settings.get()
        if s:
            s.connect("changed::night-light", lambda *a: self._sync_night_light())
        self._sync_night_light()

    def _load_css(self):
        provider = Gtk.CssProvider()
        path = data_path("style", "shell.css")
        if os.path.exists(path):
            provider.load_from_path(path)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    # --- command line ---

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        if not self.started:
            if args and not cmdline.get_is_remote():
                # A command with no shell running: there is nothing to talk to.
                print("aurora-shell: shell is not running", file=sys.stderr)
                return 1
            self._start()
        if args:
            self.handle(args)
        return 0

    def handle(self, args):
        cmd, rest = args[0], args[1:]
        arg = rest[0] if rest else ""
        if cmd == "launcher":
            self.launcher.toggle()
        elif cmd == "volume":
            if arg == "mute":
                self.audio.toggle_mute()
            else:
                self.audio.step(VOLUME_STEP if arg == "up" else -VOLUME_STEP)
            level = 0 if self.audio.muted else self.audio.volume
            self.osd.show_level(self.audio.icon_name, level)
        elif cmd == "brightness":
            self.brightness.step(BRIGHTNESS_STEP if arg == "up" else -BRIGHTNESS_STEP)
            self.osd.show_level("display-brightness-symbolic", self.brightness.level)
        elif cmd == "screenshot":
            self.screenshot(area=(arg == "area"))
        elif cmd == "quick-settings":
            for panel in self.panels.windows()[:1]:
                panel.open_quick_settings()
        else:
            print(f"aurora-shell: unknown command {cmd}", file=sys.stderr)

    # --- helpers used by components ---

    def open_settings(self, page=""):
        argv = ["aurora-settings"]
        if page:
            argv += ["--page", page]
        apps.spawn(argv)

    def _open_files(self):
        app = apps.app_by_id("org.aurora.Files.desktop")
        if app:
            apps.launch(app)
        else:
            Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(GLib.get_home_dir()), None)

    def screenshot(self, area=False):
        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) \
            or os.path.expanduser("~/Pictures")
        folder = os.path.join(pictures, "Screenshots")
        os.makedirs(folder, exist_ok=True)
        stamp = GLib.DateTime.new_now_local().format("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(folder, f"Screenshot_{stamp}.png")
        argv = ["grim"]
        if area:
            geometry = subprocess.run(["slurp"], capture_output=True, text=True).stdout.strip()
            if not geometry:
                return
            argv += ["-g", geometry]
        if subprocess.run(argv + [path]).returncode != 0:
            return
        if shutil.which("wl-copy"):
            with open(path, "rb") as f:
                subprocess.Popen(["wl-copy", "--type", "image/png"], stdin=f)
        self.notifications.notify(
            _("Screenshots"), 0, path, _("Screenshot captured"),
            _("Saved to {path} and copied to the clipboard.").format(
                path=GLib.markup_escape_text(path.replace(GLib.get_home_dir(), "~"))),
            [], {"transient": False}, -1)

    def _sync_night_light(self):
        s = settings.get()
        want = s is not None and s.get_boolean("night-light")
        if want and self._night_light is None and shutil.which("wlsunset"):
            temp = s.get_int("night-light-temperature")
            # Same low/high temperature keeps the filter on regardless of time of day.
            self._night_light = subprocess.Popen(
                ["wlsunset", "-t", str(temp), "-T", str(temp + 1)])
        elif not want and self._night_light is not None:
            self._night_light.terminate()
            self._night_light = None


def main():
    return Shell().run(sys.argv)
