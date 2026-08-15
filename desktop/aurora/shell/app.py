"""Aurora Shell application: owns every desktop surface and handles commands.

Running `aurora-shell` starts the shell. Running it again with a command
forwards the command to the running instance, e.g.:

    aurora-shell launcher [spotlight|grid]
    aurora-shell search TEXT
    aurora-shell clipboard | emoji | overview | assistant
    aurora-shell dictate | read-aloud | writing
    aurora-shell volume up|down|mute
    aurora-shell brightness up|down
    aurora-shell screenshot [area|text]
"""

import os
import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk  # noqa: E402

from aurora import apps, data_path, settings  # noqa: E402
from aurora.i18n import _  # noqa: E402
from aurora.shell import layer  # noqa: E402
from aurora.shell.dock import Dock  # noqa: E402
from aurora.shell.launcher import Launcher  # noqa: E402
from aurora.shell.monitors import PerMonitor  # noqa: E402
from aurora.shell.notifications import NotificationServer  # noqa: E402
from aurora.shell.osd import OSD  # noqa: E402
from aurora.shell.panel import Panel  # noqa: E402
from aurora.shell.services import (  # noqa: E402
    Audio, Battery, Bluetooth, Brightness, Media, Microphone, Network, Power, PowerProfiles,
    Recorder,
)
from aurora.shell.toplevels import ToplevelTracker  # noqa: E402
from aurora.shell.wallpaper import Wallpaper  # noqa: E402

VOLUME_STEP = 0.05


def search_prefix_clipboard():
    from aurora.shell.search import CLIPBOARD_PREFIX
    return CLIPBOARD_PREFIX + " "
BRIGHTNESS_STEP = 0.05



def _service(cls):
    """Create a hardware service; if it fails, log why and return an unavailable one
    (its class-level defaults: nothing present, nothing to control)."""
    try:
        return cls()
    except Exception:  # noqa: BLE001 - the desktop matters more than one indicator
        import traceback
        print(f"aurora-shell: {cls.__name__} unavailable:", file=sys.stderr)
        traceback.print_exc()
        obj = cls.__new__(cls)
        GObject.Object.__init__(obj)
        return obj

class Shell(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Shell",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.started = False

    # --- lifecycle ---

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()
        for name, cb, ptype in (
            ("open-terminal", lambda *_: apps.spawn(["ptyxis", "--new-window"]), None),
            ("open-files", lambda *_: self._open_files(), None),
            ("settings", lambda _a, p: self.open_settings(p.get_string()), "s"),
            ("launcher", lambda *_: self.launcher.toggle(), None),
            ("software", lambda *_: apps.spawn(["gnome-software"]), None),
            ("devhub", lambda *_: apps.spawn(["aurora-devhub"]), None),
            ("force-quit", lambda *_: apps.spawn(["gnome-system-monitor", "-p"]), None),
            ("suspend", lambda *_: self.power.suspend(), None),
            ("reboot", lambda *_: self.power.reboot(), None),
            ("poweroff", lambda *_: self.power.poweroff(), None),
            ("lock", lambda *_: self.power.lock(), None),
            ("logout", lambda *_: self.power.logout(), None),
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
        import time
        t0 = time.monotonic()
        # Hardware services: on unusual (virtual) hardware one may fail; the shell
        # must start anyway, with that service shown as unavailable.
        self.audio = _service(Audio)
        self.brightness = _service(Brightness)
        self.battery = _service(Battery)
        self.network = Network()
        self.power = Power()
        self.microphone = _service(Microphone)
        self.bluetooth = Bluetooth()
        self.power_profiles = _service(PowerProfiles)
        self.recorder = Recorder()
        self.recorder.connect("saved", self._on_recording_saved)
        self.media = Media()
        self.toplevels = ToplevelTracker()
        from aurora.shell.daycycle import DayCycle
        self.daycycle = DayCycle()
        self.notifications = NotificationServer(self)
        from aurora.shell.sysnotify import SystemNotifications
        self.sysnotify = SystemNotifications(self)
        self.launcher = Launcher(self)
        self.osd = OSD(self)
        self.wallpapers = PerMonitor(lambda m: Wallpaper(self, m))
        self.panels = PerMonitor(lambda m: Panel(self, m))
        self.docks = PerMonitor(lambda m: Dock(self, m))
        from aurora.shell.hotcorners import HotCorners
        from aurora.shell.overview import Overview
        self.overview = Overview(self)
        self.hotcorners = PerMonitor(lambda m: HotCorners(self, m))

        s = settings.get()
        if s:
            for key in ("panel-position", "clock-position"):
                s.connect(f"changed::{key}", lambda *a: self._later(self.panels.rebuild))
            for key in ("dock-position", "dock-style", "dock-icon-size", "dock-magnification",
                        "dock-autohide", "dock-show-trash"):
                s.connect(f"changed::{key}", lambda *a: self._later(self.docks.rebuild))
            s.connect("changed::panel-opacity", lambda *a: self._update_dynamic_css())
            for corner in ("top-left", "top-right", "bottom-left", "bottom-right"):
                s.connect(f"changed::hot-corner-{corner}",
                          lambda *a: self._later(self.hotcorners.rebuild))
        self._update_dynamic_css()
        self._clip_watch = None
        self._vnc = None
        if s:
            s.connect("changed::clipboard-history", lambda *a: self._sync_clipboard())
            s.connect("changed::screen-sharing", lambda *a: self._sync_screen_sharing())
        self._sync_clipboard()
        self._sync_screen_sharing()
        from aurora.shell.gestures import Gestures
        self.gestures = Gestures(self)
        if s:
            s.connect("changed::gestures", lambda *a: self._sync_gestures())
        self._sync_gestures()
        self.power.play_session_sound("startup")
        iface = settings.interface()
        if iface is not None:
            from aurora import look
            for key in ("color-scheme", "accent-color"):
                iface.connect(f"changed::{key}", lambda *a: self._later(look.apply))
            look.apply()
        # Tell tests (and anyone curious) when the desktop is up, once it has drawn.
        GLib.idle_add(self._ready, t0)

    def _ready(self, t0):
        import time
        print(f"aurora-shell: ready in {time.monotonic() - t0:.1f} s", flush=True)
        try:
            with open(os.path.join(GLib.get_user_runtime_dir(), "aurora-shell.ready"), "w") as f:
                f.write(f"{time.monotonic() - t0:.1f}\n")
        except OSError:
            pass
        return GLib.SOURCE_REMOVE

    def _later(self, fn):
        """Coalesce bursts of setting changes (layout presets change several keys)."""
        pending = getattr(self, "_pending", {})
        self._pending = pending
        if fn in pending.values():
            return
        key = id(fn)

        def run():
            pending.pop(key, None)
            fn()
            return GLib.SOURCE_REMOVE
        pending[key] = fn
        GLib.timeout_add(150, run)

    def _update_dynamic_css(self):
        s = settings.get()
        opacity = s.get_double("panel-opacity") if s else 0.78
        css = f".aurora-panel .panel-bar {{ background-color: rgba(20, 16, 30, {opacity:.2f}); }}"
        if not hasattr(self, "_dyn_css"):
            self._dyn_css = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), self._dyn_css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._dyn_css.load_from_string(css)

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
            self.launcher.toggle(arg or None)
        elif cmd == "search":
            self.launcher.search_for(" ".join(rest))
        elif cmd == "dictate":
            self.toggle_dictation()
        elif cmd == "read-aloud":
            self.read_aloud()
        elif cmd == "assistant":
            apps.spawn(["aurora-assistant"])
        elif cmd == "writing":
            from aurora import ai
            if ai.feature("writing-tools"):
                apps.spawn(["aurora-assistant", "--writing"])
            else:
                self._ai_hint(_("Writing tools are off"))
        elif cmd == "overview":
            self.overview.toggle()
        elif cmd == "clipboard":
            self.launcher.search_for(search_prefix_clipboard())
        elif cmd == "emoji":
            self.launcher.search_for(":")
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
            if arg == "text":
                self.screenshot_text()
            else:
                self.screenshot(area=(arg == "area"))
        elif cmd == "record":
            self.recorder.toggle()
        elif cmd == "quick-settings":
            for panel in self.panels.windows()[:1]:
                panel.open_quick_settings()
        else:
            print(f"aurora-shell: unknown command {cmd}", file=sys.stderr)

    # --- helpers used by components ---

    def get_primary_monitor(self):
        model = Gdk.Display.get_default().get_monitors()
        return model.get_item(0) if model.get_n_items() else None

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

    # --- Aurora AI: dictation and read-aloud ---

    def _ai_hint(self, text):
        self.notifications.notify(_("Aurora AI"), 0, "aurora-assistant-symbolic", text,
                                  _("Set it up in Settings → AI."), [], {"transient": True}, -1)

    def toggle_dictation(self):
        from aurora import ai
        from aurora.ai import speech
        if not ai.feature("dictation"):
            self._ai_hint(_("Dictation is off"))
            return
        if not hasattr(self, "_dictation"):
            self._dictation = speech.Dictation()
        d = self._dictation
        if not d.recording:
            if not d.ready():
                self._ai_hint(_("Dictation isn't installed yet"))
                return
            d.start()
            self.osd.show_message("audio-input-microphone-symbolic",
                                  _("Listening… press Super+H to stop"))
            return
        self.osd.show_message("content-loading-symbolic", _("Writing it down…"))
        import threading

        def work():
            try:
                text, error = d.stop(), None
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
                text, error = "", str(e)
            GLib.idle_add(lambda: (self._dictated(text, error), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _dictated(self, text, error):
        self.osd.hide()
        if error or not text:
            self._ai_hint(error or _("Nothing was heard"))
            return
        from aurora.ai import speech
        speech.type_text(text)

    def read_aloud(self):
        from aurora import ai
        from aurora.ai import speech
        if not ai.feature("read-aloud"):
            self._ai_hint(_("Read aloud is off"))
            return
        if speech.speaking():
            speech.stop_speaking()
            return
        text = speech.selected_text()
        if not text.strip():
            self._ai_hint(_("Select some text first"))
            return
        import threading

        def work():
            try:
                speech.speak(text)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
                GLib.idle_add(lambda: (self._ai_hint(str(e)), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def run_corner_action(self, action):
        """What a hot corner does (Settings → Multitasking)."""
        if action == "overview":
            self.overview.toggle()
        elif action == "launchpad":
            self.launcher.toggle("grid")
        elif action == "desktop":
            self.overview.show_desktop()
        elif action == "quick-settings":
            self.handle(["quick-settings"])
        elif action == "notifications":
            for panel in self.panels.windows()[:1]:
                panel.open_notifications()
        elif action == "lock":
            self.power.lock()
        elif action == "screen-off":
            apps.spawn(["sh", "-c", "sleep 0.5; wlopm --off '*'"])

    def _grab(self, area, folder=None):
        """Take a screenshot (whole screen or a selected area); returns its path."""
        if folder is None:
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
                return None
            argv += ["-g", geometry]
        if subprocess.run(argv + [path]).returncode != 0:
            return None
        return path

    def screenshot(self, area=False):
        path = self._grab(area)
        if path is None:
            return
        if shutil.which("wl-copy"):
            with open(path, "rb") as f:
                subprocess.Popen(["wl-copy", "--type", "image/png"], stdin=f)

        def on_action(key):
            if key == "edit":
                # Arrows, text, highlighter and blur; saves next to the original.
                apps.spawn(["swappy", "-f", path, "-o", path.replace(".png", "-edited.png")])
            elif key == "text":
                self.copy_text_from(path)
            elif key == "ask":
                self.ask_about_screenshot(path)
            else:
                Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(path), None)

        self.sysnotify.notify(
            _("Screenshot captured"),
            _("Saved to {path} and copied to the clipboard.").format(
                path=GLib.markup_escape_text(path.replace(GLib.get_home_dir(), "~"))),
            path, actions=self._screenshot_actions(), on_action=on_action)

    def _screenshot_actions(self):
        actions = [("default", _("Open")), ("edit", _("Annotate")), ("text", _("Copy Text"))]
        from aurora import ai
        if ai.feature("screenshots"):
            actions.append(("ask", _("Ask Aurora")))
        return actions

    def ask_about_screenshot(self, path):
        """Read the text in the screenshot (OCR) and ask the assistant about it."""
        import threading

        def work():
            from aurora import ocr
            try:
                text = ocr.recognize(path)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                text = ""
            prompt = (("Explain what this screenshot shows and what I might do next. Its text "
                       "(read with OCR):\n\n" + text[:8000]) if text else
                      "I took a screenshot with no readable text. Tell me you can only read "
                      "text in screenshots, briefly.")
            apps.spawn(["aurora-assistant", "--ask", prompt])
        threading.Thread(target=work, daemon=True).start()

    def screenshot_text(self):
        """Select an area and copy the text in it (OCR), like Live Text."""
        path = self._grab(True, folder=GLib.get_user_runtime_dir())
        if path is not None:
            self.copy_text_from(path, remove=True)

    def copy_text_from(self, path, remove=False):
        import threading

        def work():
            from aurora import ocr
            try:
                text, error = ocr.recognize(path), None
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
                text, error = "", str(e)
            if remove:
                try:
                    os.remove(path)
                except OSError:
                    pass
            GLib.idle_add(lambda: (self._text_found(text, error), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _text_found(self, text, error):
        if error or not text:
            self.notifications.notify(
                _("Text Recognition"), 0, "edit-find-symbolic", _("No text found"),
                GLib.markup_escape_text(error or _("Try a larger or sharper area.")),
                [], {"transient": True}, -1)
            return
        Gdk.Display.get_default().get_clipboard().set(text)
        preview = text if len(text) < 160 else text[:157] + "…"
        self.notifications.notify(
            _("Text Recognition"), 0, "edit-copy-symbolic", _("Text copied"),
            GLib.markup_escape_text(preview), [], {"transient": True}, -1)

    def _sync_gestures(self):
        s = settings.get()
        if s is None or s.get_boolean("gestures"):
            self.gestures.start()
        else:
            self.gestures.stop()

    def _sync_screen_sharing(self):
        """wayvnc runs while Settings → Sharing → Screen Sharing is on."""
        s = settings.get()
        want = s is not None and s.get_boolean("screen-sharing")
        if want and self._vnc is None and shutil.which("wayvnc"):
            from aurora import screenshare
            self._vnc = subprocess.Popen(screenshare.command())
        elif not want and self._vnc is not None:
            self._vnc.terminate()
            self._vnc = None

    def _sync_clipboard(self):
        """Clipboard history: wl-paste hands every copied text to aurora-clipboard."""
        s = settings.get()
        want = s is None or s.get_boolean("clipboard-history")
        if want and self._clip_watch is None and shutil.which("wl-paste"):
            self._clip_watch = subprocess.Popen(
                ["wl-paste", "--type", "text", "--watch", "aurora-clipboard", "store"])
        elif not want and self._clip_watch is not None:
            self._clip_watch.terminate()
            self._clip_watch = None

    def _on_recording_saved(self, _rec, path):
        self.notifications.notify(
            _("Screen Recording"), 0, "media-record", _("Screen recording saved"),
            _("Saved to {path}.").format(
                path=GLib.markup_escape_text(path.replace(GLib.get_home_dir(), "~"))),
            [], {"desktop-entry": "org.aurora.Files"}, -1)


def main():
    # Logs go to a file; write them line by line so nothing is lost on logout.
    sys.stdout.reconfigure(line_buffering=True)
    return Shell().run(sys.argv)
