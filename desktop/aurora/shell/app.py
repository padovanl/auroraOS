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

from aurora import plaintext  # noqa: E402,F401  (rows and toasts: plain text)

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
    Recorder, unique_capture_path,
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
        self._selecting = False

    # --- lifecycle ---

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._sync_style()
        self._enable_terminal_opacity()
        self._load_css()
        for name, cb, ptype in (
            ("open-terminal", lambda *_: self._open_desktop_terminal(), None),
            ("open-files", lambda *_: self._open_files(), None),
            ("edit-widgets", lambda *_: self.handle(["edit-widgets"]), None),
            ("settings", lambda _a, p: self.open_settings(p.get_string()), "s"),
            ("launcher", lambda *_: self.launcher.toggle(), None),
            ("software", lambda *_a: self.open_app(["gnome-software"], "org.gnome.Software",
                                                   _("Opening App Center…")), None),
            ("devhub", lambda *_: self.open_app(["aurora-devhub"], "org.aurora.DevHub"), None),
            ("force-quit", lambda *_: self.open_app(["aurora-taskmanager"],
                                                    "org.aurora.TaskManager"), None),
            ("suspend", lambda *_: self.power.suspend(), None),
            ("reboot", lambda *_: self.power.reboot(), None),
            ("poweroff", lambda *_: self.power.poweroff(), None),
            ("lock", lambda *_: self.lock(), None),
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
        self.power = Power(on_logout=self.quit, on_refused=self._power_refused)
        self.microphone = _service(Microphone)
        self.bluetooth = Bluetooth()
        self.power_profiles = _service(PowerProfiles)
        self.recorder = Recorder(self)
        self.recorder.connect("saved", self._on_recording_saved)
        self.media = Media()
        self.toplevels = ToplevelTracker()
        from aurora.shell.daycycle import DayCycle
        self.daycycle = DayCycle()
        self.notifications = NotificationServer(self)
        from aurora.shell.sysnotify import SystemNotifications
        self.sysnotify = SystemNotifications(self)
        self._night_light_warned = False
        self.daycycle.connect("night-light-unsupported", self._on_night_light_unsupported)
        GLib.idle_add(self._notify_compositor_fallback)
        from aurora.shell.keepawake import KeepAwake
        self.keep_awake = KeepAwake()
        from aurora.shell.refit import WindowRefit
        self.window_refit = WindowRefit(self)
        # Storage Sense: old Trash items, temporary files and Downloads, as
        # Settings → Storage asks; soon after login, then every four hours.
        GLib.timeout_add_seconds(120, self._storage_sense)
        if settings.get() is not None and settings.get().get_boolean("screen-keyboard"):
            GLib.timeout_add_seconds(2, lambda: self.osk.show_keyboard() or False)
        from aurora.shell.lockkeys import LockKeys
        self.lock_keys = LockKeys(self)
        from aurora.shell.screentrack import ScreenTimeTracker
        self.screen_time = ScreenTimeTracker(self)
        self.launcher = Launcher(self)
        self.osd = OSD(self)
        self.wallpapers = PerMonitor(lambda m: Wallpaper(self, m))
        self.panels = PerMonitor(lambda m: Panel(self, m))
        self.docks = PerMonitor(lambda m: Dock(self, m))
        self._startup_cursor_source = 0
        from aurora.shell.hotcorners import HotCorners
        from aurora.shell.overview import Overview
        self.overview = Overview(self)
        from aurora.shell.snap import SnapOverlay
        self.snap = SnapOverlay(self)
        self.hotcorners = PerMonitor(lambda m: HotCorners(self, m))

        s = settings.get()
        if s:
            for key in ("panel-position", "clock-position", "panel-style"):
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
        self._image_clip_watch = None
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
            iface.connect("changed::color-scheme", lambda *a: self._sync_style())
            iface.connect("changed::accent-color", lambda *a: self._load_css())
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

    def _on_night_light_unsupported(self, _daycycle):
        if self._night_light_warned:
            return
        self._night_light_warned = True
        self.sysnotify.notify(
            _("Night Light can't change this screen's colors"),
            _("The graphics driver doesn't allow it. This is usual in a virtual machine; "
              "on a computer, install the graphics driver from Settings → Updates → Additional Drivers."),
            "night-light-symbolic")

    def _notify_compositor_fallback(self):
        if os.environ.get("AURORA_COMPOSITOR") != "labwc":
            return GLib.SOURCE_REMOVE
        log = os.path.join(os.environ.get("XDG_STATE_HOME") or
                           os.path.expanduser("~/.local/state"),
                           "aurora", "compositor-failure.log")
        if not os.path.isfile(log):
            return GLib.SOURCE_REMOVE
        self.sysnotify.notify(
            _("Graphics fallback started"),
            _("Wayfire could not start. Aurora opened the safe desktop instead. "
              "Select this notification to review the startup report."),
            "dialog-warning-symbolic", [("default", _("Open System Health"))],
            lambda key: self.open_settings("health") if key == "default" else None,
            urgency=2)
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
        css = (f".aurora-panel.panel-bar-style .panel-bar, "
               f".aurora-panel.panel-floating .panel-island "
               f"{{ background-color: rgba(20, 16, 30, {opacity:.2f}); }}")
        if not hasattr(self, "_dyn_css"):
            self._dyn_css = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), self._dyn_css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._dyn_css.load_from_string(css)

    def launch_app(self, app, action=None):
        surfaces = (self.wallpapers.windows() + self.panels.windows() +
                    self.docks.windows() + [self.launcher])
        for surface in surfaces:
            surface.set_cursor_from_name("progress")
        if self._startup_cursor_source:
            GLib.source_remove(self._startup_cursor_source)

        def clear():
            self._startup_cursor_source = 0
            for surface in surfaces:
                if surface.get_native() is not None:
                    surface.set_cursor(None)
            return GLib.SOURCE_REMOVE

        self._startup_cursor_source = GLib.timeout_add(2200, clear)
        return apps.launch(app, action=action)

    def _load_css(self):
        path = data_path("style", "shell.css")
        if os.path.exists(path):
            from aurora.look import ACCENT_HEX
            iface = settings.interface()
            accent = (ACCENT_HEX.get(iface.get_string("accent-color"), "#a970ff")
                      if iface else "#a970ff")
            with open(path, encoding="utf-8") as f:
                css = f.read().replace("@define-color aurora_violet #a970ff;",
                                       f"@define-color aurora_violet {accent};")
            if not hasattr(self, "_shell_css"):
                self._shell_css = Gtk.CssProvider()
                Gtk.StyleContext.add_provider_for_display(
                    Gdk.Display.get_default(), self._shell_css,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self._shell_css.load_from_string(css)

    @staticmethod
    def _sync_style():
        iface = settings.interface()
        dark = iface is not None and iface.get_string("color-scheme") == "prefer-dark"
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT)

    @staticmethod
    def _enable_terminal_opacity():
        """Expose Ptyxis' built-in opacity slider in its profile menu."""
        defaults = settings.get("org.gnome.Ptyxis")
        if defaults is None:
            return

        def seed(*_args):
            uuid = defaults.get_string("default-profile-uuid")
            if not uuid or "/" in uuid or len(uuid) > 64:
                return
            source = Gio.SettingsSchemaSource.get_default()
            if source.lookup("org.gnome.Ptyxis.Profile", True) is None:
                return
            profile = Gio.Settings.new_with_path(
                "org.gnome.Ptyxis.Profile", f"/org/gnome/Ptyxis/Profiles/{uuid}/")
            if profile.get_user_value("opacity") is None:
                profile.set_double("opacity", 0.99)

        defaults.connect("changed::default-profile-uuid", seed)
        seed()

    def _open_desktop_terminal(self):
        from aurora.shell.desktopicons import desktop_dir
        path = desktop_dir()
        os.makedirs(path, exist_ok=True)
        return apps.spawn(["ptyxis", "--new-window", f"--working-directory={path}"])

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
            if args[0] == "windows":
                # For tests and scripts: the open windows as JSON, one per line.
                import json
                for t in self.toplevels.toplevels:
                    cmdline.print_literal(json.dumps({
                        "app_id": t.app_id, "title": t.title, "activated": t.activated,
                        "minimized": t.minimized, "maximized": getattr(t, "maximized", False),
                        "fullscreen": getattr(t, "fullscreen", False)}) + "\n")
                return 0
            return self.handle(args) or 0
        return 0

    def close_overlays(self, keep=None):
        """Close keyboard-grabbing shell surfaces except the one being opened.

        Without this, a surface can remain hidden under a newer one and consume
        the next shortcut after the top surface closes.
        """
        launcher = getattr(self, "launcher", None)
        if launcher is not None and launcher is not keep and launcher.get_visible():
            launcher.hide_launcher()
        overview = getattr(self, "overview", None)
        if overview is not None and overview is not keep and overview.get_visible():
            overview.hide_overview()
        shortcuts = getattr(self, "shortcuts_overlay", None)
        if shortcuts is not None and shortcuts is not keep and shortcuts.get_visible():
            shortcuts.set_visible(False)
        panels = getattr(self, "panels", None)
        if panels is not None:
            for panel in panels.windows():
                if panel is not keep:
                    panel.close_menus()

    def begin_selection(self):
        if self._selecting:
            return False
        self._selecting = True
        return True

    def end_selection(self):
        self._selecting = False

    def lock(self):
        self.close_overlays()
        self.power.lock()

    def handle(self, args):
        cmd, rest = args[0], args[1:]
        arg = rest[0] if rest else ""
        # Area selection owns the keyboard.  Commands triggered while slurp is
        # active must not appear later, after the user cancels with Escape.
        if self._selecting:
            return 0
        if cmd == "launcher":
            self.launcher.toggle(arg or None)
        elif cmd == "search":
            self.launcher.search_for(" ".join(rest))
        elif cmd == "dictate":
            self.toggle_dictation()
        elif cmd == "read-aloud":
            self.read_aloud()
        elif cmd == "assistant":
            # From the keyboard shortcut: typing should go to the Assistant.
            apps.spawn(["aurora-assistant", "--focus"])
        elif cmd == "writing":
            from aurora import ai
            if ai.feature("writing-tools"):
                apps.spawn(["aurora-assistant", "--writing"])
            else:
                self._ai_hint(_("Writing tools are off"))
        elif cmd == "overview":
            self.overview.toggle()
        elif cmd == "osk":
            # aurora-shell osk [show|hide|toggle]
            {"show": self.osk.show_keyboard, "hide": self.osk.hide_keyboard}.get(
                arg, self.osk.toggle)()
        elif cmd == "show-desktop":
            self.toggle_desktop()
        elif cmd == "snap-layouts":
            self.snap.show_layouts()
        elif cmd == "always-on-top":
            self.toggle_always_on_top()
        elif cmd == "snap":
            # aurora-shell snap left-third|center-third|right-third|left|right…
            self.snap.snap_focused(arg)
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
            elif arg == "pin":
                self.pin_screenshot()
            else:
                self.screenshot(area=(arg == "area"))
        elif cmd == "record":
            # aurora-shell record [area] [sound]
            from aurora import settings as st
            s = st.get()
            sound = "sound" in rest or (s is not None and s.get_boolean("record-sound"))
            self.recorder.toggle(area="area" in rest, sound=sound)
        elif cmd == "colorpick":
            from aurora.shell.colorpicker import pick
            pick(self)
        elif cmd == "shortcuts":
            from aurora.shell.shortcuts import ShortcutsOverlay
            if getattr(self, "shortcuts_overlay", None) is None:
                self.shortcuts_overlay = ShortcutsOverlay(self)
            self.shortcuts_overlay.toggle()
        elif cmd == "edit-widgets":
            layer = getattr(self, "widget_layer", None)
            if layer is not None:
                layer.set_editing(True)
        elif cmd == "keep-awake":
            self.keep_awake.set_active(not self.keep_awake.active)
        elif cmd == "lock":
            self.lock()
        elif cmd == "quick-settings":
            for panel in self.panels.windows()[:1]:
                if arg == "hide":
                    panel.close_menus()
                else:
                    panel.open_quick_settings()
        elif cmd == "logout":
            self.power.logout()
        elif cmd == "focus":
            # Bring an app's windows forward, newest (a dialog) on top; exit
            # status 1 if it has none.
            windows = self.toplevels.for_app(arg)
            if not windows:
                return 1
            for window in windows:
                window.activate()
        elif cmd == "minimize":
            # Minimize an app's windows (the installer's own button uses it).
            windows = self.toplevels.for_app(arg)
            if not windows:
                return 1
            for window in windows:
                window.minimize()
        else:
            print(f"aurora-shell: unknown command {cmd}", file=sys.stderr)

    # --- helpers used by components ---

    def get_primary_monitor(self):
        model = Gdk.Display.get_default().get_monitors()
        return model.get_item(0) if model.get_n_items() else None

    def _power_refused(self, method, reason):
        titles = {"Reboot": _("Restart didn't happen"), "PowerOff": _("Shut down didn't happen"),
                  "Suspend": _("Sleep didn't happen")}
        anyway = {"Reboot": _("Restart Anyway"), "PowerOff": _("Shut Down Anyway"),
                  "Suspend": _("Sleep Anyway")}
        self.sysnotify.notify(titles.get(method, method), reason, "system-shutdown-symbolic",
                              [("force", anyway.get(method, method)), ("later", _("Cancel"))],
                              lambda key: key == "force" and self.power.force(method),
                              urgency=2)

    def open_settings(self, page=""):
        argv = ["aurora-settings"]
        if page:
            argv += ["--page", page]
        self.open_app(argv, "org.aurora.Settings")

    def open_app(self, argv, app_id, starting=None):
        """Run an app's command and make sure its window comes forward.

        An app that is already open gets the command (a Settings page, say)
        but can't raise itself on Wayland without an activation token: the
        shell activates its window instead. A slow first start (App Center
        loads its catalog) shows that something is happening."""
        running = self.toplevels.for_app(app_id)
        apps.spawn(argv)
        if running:
            GLib.timeout_add(350, lambda: (running[0].activate(), False)[1])
        elif starting:
            self.osd.show_message("content-loading-symbolic", starting, timeout_ms=2500)

    def _open_files(self):
        app = apps.app_by_id("org.aurora.Files.desktop")
        if app:
            apps.launch(app)
        else:
            Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(GLib.get_home_dir()), None)

    # --- Aurora AI: dictation and read-aloud ---

    def _storage_sense(self):
        import threading

        def work():
            from aurora import housekeeping
            try:
                done = housekeeping.run_storage_sense(settings.get("org.gnome.desktop.privacy"),
                                                      settings.get())
                if any(done.values()):
                    print(f"aurora: storage sense: {done}")
            except Exception as err:  # noqa: BLE001 - never take the shell down
                print(f"aurora: storage sense failed: {err}")
        threading.Thread(target=work, daemon=True).start()
        GLib.timeout_add_seconds(4 * 3600, lambda: self._storage_sense() and False)
        return False

    @property
    def osk(self):
        """The on-screen keyboard, made the first time it's needed."""
        if getattr(self, "_osk", None) is None:
            from aurora.shell.osk import ScreenKeyboard
            self._osk = ScreenKeyboard(self)
        return self._osk

    def osk_changed(self):
        for panel in self.panels.windows():
            qs = getattr(panel, "status", None)
            pop = qs.get_popover() if qs is not None else None
            if pop is not None and pop.get_visible():
                pop.refresh()

    def toggle_desktop(self):
        """Show the desktop, or bring back the windows it hid (a second click),
        like the corner of Windows' taskbar."""
        hidden = [t for t in getattr(self, "_desktop_hidden", [])
                  if t in self.toplevels.toplevels and t.minimized]
        if hidden:
            for t in sorted(hidden, key=lambda t: getattr(t, "focus_serial", 0)):
                t.activate()
            self._desktop_hidden = []
        else:
            self._desktop_hidden = [t for t in self.toplevels.toplevels if not t.minimized]
            for t in self._desktop_hidden:
                t.minimize()
        self.toplevels.flush()

    def toggle_always_on_top(self):
        """Keep the focused window above the others, or stop (Super+T)."""
        from aurora import wayfirelayout
        try:
            view = wayfirelayout.request("window-rules/get-focused-view").get("info") or {}
            if view.get("role") != "toplevel":
                return
            # Wayfire doesn't report the state: remember which windows we pinned.
            pinned = self.__dict__.setdefault("_pinned_views", set())
            on = view["id"] not in pinned
            (pinned.add if on else pinned.discard)(view["id"])
            wayfirelayout.request("wm-actions/set-always-on-top",
                                  {"view_id": view["id"], "state": on})
        except (OSError, ValueError, ConnectionError, KeyError, AttributeError):
            return
        self.osd.show_message("view-pin-symbolic" if on else "view-restore-symbolic",
                              _("Always on Top") if on else _("Always on Top Off"), 1500)

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
            self.lock()
        elif action == "screen-off":
            apps.spawn(["sh", "-c", "sleep 0.5; wlopm --off '*'"])

    def _grab(self, area, folder=None):
        """Take a screenshot (whole screen or a selected area); returns its path."""
        if folder is None:
            pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) \
                or os.path.expanduser("~/Pictures")
            folder = os.path.join(pictures, "Screenshots")
        os.makedirs(folder, exist_ok=True)
        path = unique_capture_path(folder, "Screenshot", ".png")
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
        if area:
            self._grab_area_async(self._finish_screenshot)
            return
        self._finish_screenshot(self._grab(False))

    def _finish_screenshot(self, path):
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
            elif key == "pin":
                self.pin_screenshot(path)
            else:
                Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(path), None)

        self.sysnotify.notify(
            _("Screenshot captured"),
            _("Saved to {path} and copied to the clipboard.").format(
                path=GLib.markup_escape_text(path.replace(GLib.get_home_dir(), "~"))),
            path, actions=self._screenshot_actions(), on_action=on_action)

    def _grab_area_async(self, callback, folder=None):
        """Run slurp/grim without blocking shell commands; ignore them meanwhile."""
        if not self.begin_selection():
            return
        import threading

        def work():
            try:
                path = self._grab(True, folder=folder)
            except (OSError, subprocess.SubprocessError):
                path = None

            def finish():
                self.end_selection()
                callback(path)
                return False
            GLib.idle_add(finish)

        threading.Thread(target=work, daemon=True).start()

    def _screenshot_actions(self):
        actions = [("default", _("Open")), ("pin", _("Pin to Screen")), ("edit", _("Annotate")),
                   ("text", _("Copy Text"))]
        from aurora import ai
        if ai.feature("screenshots"):
            actions.append(("ask", _("Ask Aurora")))
        return actions

    def pin_screenshot(self, path=None):
        """Keep a screenshot floating above the windows (an area is taken first
        when no file is given)."""
        if path is None:
            self._grab_area_async(self._finish_pin_screenshot,
                                  folder=GLib.get_user_runtime_dir())
            return

        self._finish_pin_screenshot(path)

    def _finish_pin_screenshot(self, path):
        if not path:
            return
        from aurora.shell.pinshot import pin
        try:
            pin(self, path)
        except GLib.Error as err:
            print(f"aurora: cannot pin {path}: {err.message}")

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
        self._grab_area_async(
            lambda path: self.copy_text_from(path, remove=True) if path is not None else None,
            folder=GLib.get_user_runtime_dir())

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
            try:
                self._vnc = subprocess.Popen(apps.tied(screenshare.command()))
            except (OSError, subprocess.SubprocessError) as err:
                # A broken key/config or an executable that disappeared must
                # not make the desktop restart forever at every shell launch.
                print(f"aurora: screen sharing could not start ({err})")
                self._vnc = None
                s.set_boolean("screen-sharing", False)
        elif not want and self._vnc is not None:
            self._vnc.terminate()
            self._vnc = None

    def _sync_clipboard(self):
        """Clipboard history: wl-paste hands every copied text to aurora-clipboard."""
        s = settings.get()
        want = s is None or s.get_boolean("clipboard-history")
        if want and self._clip_watch is None and shutil.which("wl-paste"):
            try:
                self._clip_watch = subprocess.Popen(apps.tied(
                    ["wl-paste", "--type", "text", "--watch", "aurora-clipboard", "store"]))
                self._image_clip_watch = subprocess.Popen(apps.tied(
                    ["wl-paste", "--type", "image/png", "--watch",
                     "aurora-clipboard", "store-image"]))
            except OSError as err:
                print(f"aurora: clipboard history could not start ({err})")
                if self._clip_watch is not None:
                    self._clip_watch.terminate()
                self._clip_watch = self._image_clip_watch = None
                if s is not None:
                    s.set_boolean("clipboard-history", False)
        elif not want and self._clip_watch is not None:
            self._clip_watch.terminate()
            self._clip_watch = None
            if self._image_clip_watch is not None:
                self._image_clip_watch.terminate()
                self._image_clip_watch = None

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
