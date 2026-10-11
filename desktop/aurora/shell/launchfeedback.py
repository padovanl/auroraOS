"""Visible startup feedback until a window appears, with bounded click deduplication."""
import time

from gi.repository import GLib
from aurora import apps
from aurora.i18n import _


class LaunchFeedback:
    TIMEOUT = 15

    def __init__(self, shell):
        self.shell = shell
        self.pending = {}
        self.cursors = {}
        self.timer = 0

    def launch(self, app, files=None, action=None):
        # Explicit desktop actions (e.g. New Window) and different documents
        # remain independent requests.
        key = (app.get_id() or app.get_commandline() or app.get_executable(), tuple(files or ()))
        if action is None and key in self.pending:
            return True
        if action is not None:
            key += (object(),)
        before = {id(w) for w in self.shell.toplevels.toplevels}
        self.pending[key] = (app, before, time.monotonic() + self.TIMEOUT, False)
        self._cursors()
        self.shell.osd.show_message("content-loading-symbolic",
                                    _("Opening {app}…").format(app=app.get_display_name()),
                                    timeout_ms=2500)
        if not self.timer:
            self.timer = GLib.timeout_add(100, self._poll)

        def start():
            if key not in self.pending:
                return GLib.SOURCE_REMOVE
            if not apps.launch_direct(app, files=files, action=action):
                self.pending.pop(key, None)
                self.shell.osd.show_message("dialog-error-symbolic",
                    _("Could not open {app}").format(app=app.get_display_name()), timeout_ms=5000)
            else:
                self.pending[key] = (app, before, time.monotonic() + self.TIMEOUT, True)
            self._cursors()
            return GLib.SOURCE_REMOVE
        # Give GTK a frame to show the cursor before launching through GIO.
        GLib.timeout_add(45, start)
        return True

    def _matches(self, app, window):
        desktop_id = app.get_id() or ""
        names = {desktop_id.removesuffix(".desktop").casefold(),
                 (getattr(app, "get_startup_wm_class", lambda: "")() or "").casefold()}
        names.discard("")
        if (window.app_id or "").casefold() in names:
            return True
        found = apps.find_app(window.app_id)
        return found is not None and (found.get_id() == desktop_id or
            (app.get_commandline() and found.get_commandline() == app.get_commandline()))

    def _poll(self):
        now = time.monotonic()
        for key, (app, before, deadline, started) in list(self.pending.items()):
            ready = started and any(self._matches(app, w) and
                (id(w) not in before or (len(key) == 2 and w.activated))
                for w in self.shell.toplevels.toplevels)
            if ready or now >= deadline:
                self.pending.pop(key, None)
        self._cursors()
        if not self.pending:
            self.timer = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _cursors(self):
        if self.pending:
            surfaces = (self.shell.wallpapers.windows() + self.shell.panels.windows() +
                        self.shell.docks.windows() + [self.shell.launcher])
            for surface in surfaces:
                if surface not in self.cursors:
                    self.cursors[surface] = surface.get_cursor()
                surface.set_cursor_from_name("progress")
        else:
            for surface, cursor in self.cursors.items():
                surface.set_cursor(cursor)
            self.cursors.clear()
