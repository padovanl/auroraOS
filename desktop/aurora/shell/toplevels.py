"""Track and control application windows via wlr-foreign-toplevel-management.

GTK does not expose other clients' windows, so this opens a second Wayland
connection with pywayland and feeds its events into the GLib main loop.
"""

import struct

from gi.repository import GLib, GObject

try:
    from pywayland.client import Display
    from aurora.protocols.wayland import WlSeat
    from aurora.protocols.wlr_foreign_toplevel_management_unstable_v1 import (
        ZwlrForeignToplevelManagerV1,
    )
    HAVE_BINDINGS = True
except ImportError as err:  # dev hosts without generated bindings
    print(f"aurora: window tracking disabled ({err})")
    HAVE_BINDINGS = False

STATE_MAXIMIZED = 0
STATE_MINIMIZED = 1
STATE_ACTIVATED = 2
STATE_FULLSCREEN = 3


def _decode_states(raw):
    if raw is None:
        return set()
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw)
        return set(struct.unpack(f"={len(raw) // 4}I", raw))
    return set(raw)


def window_labels(windows, fallback="Window"):
    """{window: label}: its title, numbered when several share it (oldest is 1),
    so three "Terminal" windows read Terminal 1, 2 and 3."""
    titles = {w: w.title or fallback for w in windows}
    labels = {}
    for w, title in titles.items():
        same = sorted((x for x in windows if titles[x] == title), key=lambda x: x.serial)
        labels[w] = f"{title} {same.index(w) + 1}" if len(same) > 1 else title
    return labels


class Toplevel(GObject.Object):
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, tracker, handle):
        super().__init__()
        self._tracker = tracker
        self.handle = handle
        self.title = ""
        self.app_id = ""
        self.states = set()
        self.ready = False
        self.serial = 0
        self.focus_serial = 0
        handle.dispatcher["title"] = self._on_title
        handle.dispatcher["app_id"] = self._on_app_id
        handle.dispatcher["state"] = self._on_state
        handle.dispatcher["done"] = self._on_done
        handle.dispatcher["closed"] = self._on_closed

    @property
    def activated(self):
        return STATE_ACTIVATED in self.states

    @property
    def minimized(self):
        return STATE_MINIMIZED in self.states

    @property
    def fullscreen(self):
        return STATE_FULLSCREEN in self.states

    @property
    def maximized(self):
        return STATE_MAXIMIZED in self.states

    def _on_title(self, _h, title):
        self.title = title or ""

    def _on_app_id(self, _h, app_id):
        self.app_id = app_id or ""

    def _on_state(self, _h, states):
        self.states = _decode_states(states)
        if self.activated:
            self._tracker.bump(self)

    def _on_done(self, _h):
        first = not self.ready
        self.ready = True
        # The shell's own windows (pinned screenshots) stay out of the window
        # lists, the dock and the overview.
        if self.app_id == "org.aurora.Shell":
            return
        if first:
            self._tracker.added(self)
        self.emit("changed")
        self._tracker.emit("changed")

    def _on_closed(self, _h):
        self._tracker.removed(self)
        self.handle.destroy()
        self._tracker.flush()

    # Requests

    def activate(self):
        if self._tracker.seat is not None:
            if self.minimized:
                self.handle.unset_minimized()
            self.handle.activate(self._tracker.seat)
            self._tracker.flush()

    def minimize(self):
        self.handle.set_minimized()
        self._tracker.flush()

    def close(self):
        self.handle.close()
        self._tracker.flush()

    def toggle(self):
        """Taskbar click: focus the window, or minimize it if already focused."""
        if self.activated and not self.minimized:
            self.minimize()
        else:
            self.activate()


class ToplevelTracker(GObject.Object):
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self.toplevels = []
        self._alive = set()
        self.seat = None
        self.manager = None
        self._serial = 0
        self._focus_serial = 0
        self._display = None
        if not HAVE_BINDINGS:
            return
        try:
            self._display = Display()
            self._display.connect()
        except Exception as err:  # noqa: BLE001 - any connect failure disables tracking
            print(f"aurora: cannot open Wayland connection: {err}")
            self._display = None
            return
        # Must stay referenced: pywayland finds the display for new objects
        # (every new window) through live registries only.
        self._registry = registry = self._display.get_registry()
        registry.dispatcher["global"] = self._on_global
        self._display.roundtrip()
        self._display.roundtrip()
        if self.manager is None:
            print("aurora: compositor lacks wlr-foreign-toplevel-management")
        GLib.io_add_watch(self._display.get_fd(), GLib.PRIORITY_DEFAULT,
                          GLib.IOCondition.IN | GLib.IOCondition.HUP, self._on_io)

    @property
    def available(self):
        return self.manager is not None

    def _on_global(self, registry, name, interface, version):
        if interface == "zwlr_foreign_toplevel_manager_v1":
            self.manager = registry.bind(name, ZwlrForeignToplevelManagerV1, min(version, 3))
            self.manager.dispatcher["toplevel"] = self._on_toplevel
        elif interface == "wl_seat" and self.seat is None:
            self.seat = registry.bind(name, WlSeat, 1)

    def _on_toplevel(self, _manager, handle):
        # Keep a strong reference until "closed": before its first "done" the
        # Toplevel is only reachable through a reference cycle, and if the
        # garbage collector freed it, pywayland would fail on its next event.
        self._alive.add(Toplevel(self, handle))

    def _on_io(self, _fd, cond):
        if cond & GLib.IOCondition.HUP:
            return False
        try:
            self._display.dispatch(block=True)
        except Exception as err:  # noqa: BLE001
            print(f"aurora: wayland dispatch failed: {err}")
            return False
        return True

    def flush(self):
        if self._display is not None:
            self._display.flush()

    def added(self, toplevel):
        self._serial += 1
        toplevel.serial = self._serial
        self.toplevels.append(toplevel)

    def removed(self, toplevel):
        self._alive.discard(toplevel)
        if toplevel in self.toplevels:
            self.toplevels.remove(toplevel)
        self.emit("changed")

    def bump(self, toplevel):
        self._focus_serial += 1
        toplevel.focus_serial = self._focus_serial

    def active(self):
        for t in self.toplevels:
            if t.activated:
                return t
        return None

    def for_app(self, app_id):
        return sorted((t for t in self.toplevels if t.app_id == app_id),
                      key=lambda t: t.focus_serial, reverse=True)
