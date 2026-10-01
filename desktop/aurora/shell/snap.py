"""Snap Layouts and Snap Assist, as in Windows 11 (Wayfire).

Super+Z shows six layouts at the top of the screen: halves, two thirds and a
third, thirds, a half and two quarters, quarters, a wide middle. Pointing at a
zone shows where the window will go; clicking puts the focused window there.
Then Snap Assist fills the rest: each empty zone offers the other open windows,
and one click places each. Snapping a window to half the screen with
Super+←/→ (or by dragging it to the edge) offers the other half the same way.

Windows are placed through Wayfire's IPC (window-rules/configure-view); labwc
has no such interface, so there the layouts aren't offered.
"""

import json
import os
import socket
import struct
import threading
import time

from gi.repository import Gdk, GLib, Gtk, Pango

from aurora import apps, compositor, settings, wayfirelayout
from aurora.i18n import _
from aurora.shell.layer import LS, Keyboard, Layer, LayerWindow

from aurora.shell.snapzones import (  # noqa: F401 - re-exported for callers
    EDGE_BOTTOM, EDGE_LEFT, EDGE_RIGHT, EDGE_TOP, LAYOUTS, LEFT_HALF, RIGHT_HALF,
    candidates, other_half, with_gaps, zone_geometry)

PICKER_WIDTH = 96   # one layout in the picker
PICKER_HEIGHT = 60


def available():
    return compositor.is_wayfire() and bool(os.environ.get("WAYFIRE_SOCKET"))


def _ipc(method, data=None):
    try:
        return wayfirelayout.request(method, data)
    except (OSError, ValueError, ConnectionError) as err:
        print(f"aurora: snap: {method}: {err}")
        return None


def gap():
    """Settings → Desktop & Dock → Gaps around snapped windows, in pixels."""
    s = settings.get()
    return s.get_int("window-gaps") if s is not None else 0


def place(view_id, geometry):
    """Put a window at a geometry, bring it back if minimized, and raise it."""
    _ipc("wm-actions/set-minimized", {"view_id": view_id, "state": False})
    _ipc("window-rules/configure-view", {"id": view_id, "geometry": geometry})
    _ipc("window-rules/focus-view", {"id": view_id})


class SnapOverlay(LayerWindow):
    def __init__(self, shell):
        super().__init__(shell, "aurora-snap", layer=Layer.OVERLAY,
                         anchors=("top", "bottom", "left", "right"),
                         keyboard=Keyboard.EXCLUSIVE, exclusive=-1)
        self.add_css_class("aurora-snap")
        self.shell = shell
        self.area = {"x": 0, "y": 0, "width": 1, "height": 1}
        self.output = ""
        self.target = None      # the window being placed first
        self.zones = []         # zones still to fill (Snap Assist)
        self.placed = set()

        self.fixed = Gtk.Fixed()
        self.dim = Gtk.Box(css_classes=["snap-dim"])
        overlay = Gtk.Overlay(child=self.dim)
        overlay.add_overlay(self.fixed)
        self.set_child(overlay)

        self.preview = Gtk.Box(css_classes=["snap-preview"], can_target=False)
        self.picker = self._build_picker()

        click = Gtk.GestureClick()
        click.connect("released", self._on_background_click)
        self.dim.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        self._watch = None
        if available():
            self._watch = threading.Thread(target=self._watch_events, daemon=True)
            self._watch.start()

    # --- the layouts --------------------------------------------------------------

    def _build_picker(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                       css_classes=["snap-picker"])
        card.append(Gtk.Label(label=_("Snap Layouts"), xalign=0,
                              css_classes=["snap-picker-title"]))
        grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3,
                           min_children_per_line=3, column_spacing=12, row_spacing=12,
                           homogeneous=True)
        for layout in LAYOUTS:
            mini = Gtk.Fixed(css_classes=["snap-mini"])
            mini.set_size_request(PICKER_WIDTH, PICKER_HEIGHT)
            for zone in layout:
                g = zone_geometry(zone, {"x": 0, "y": 0, "width": PICKER_WIDTH,
                                         "height": PICKER_HEIGHT})
                button = Gtk.Button(css_classes=["snap-zone"], focusable=False)
                button.set_size_request(g["width"] - 4, g["height"] - 4)
                button.connect("clicked", lambda _b, lo=layout, z=zone: self._chose(lo, z))
                hover = Gtk.EventControllerMotion()
                hover.connect("enter", lambda *_a, z=zone: self._show_preview(z))
                hover.connect("leave", lambda *_a: self.preview.set_visible(False))
                button.add_controller(hover)
                mini.put(button, g["x"] + 2, g["y"] + 2)
            grid.append(mini)
        child = grid.get_first_child()
        while child is not None:
            child.set_focusable(False)
            child = child.get_next_sibling()
        card.append(grid)
        card.append(Gtk.Label(label=_("Pick where this window goes, then fill the rest"),
                              xalign=0, css_classes=["snap-picker-hint"]))
        return card

    def _show_preview(self, zone):
        g = zone_geometry(zone, self.area)
        self._put(self.preview, g)
        self.preview.set_visible(True)

    def _put(self, widget, g, inset=6):
        widget.set_size_request(max(1, g["width"] - 2 * inset), max(1, g["height"] - 2 * inset))
        if widget.get_parent() is None:
            self.fixed.put(widget, g["x"] + inset, g["y"] + inset)
        else:
            self.fixed.move(widget, g["x"] + inset, g["y"] + inset)

    def _clear(self):
        while (child := self.fixed.get_first_child()) is not None:
            self.fixed.remove(child)

    # --- opening -----------------------------------------------------------------

    def _where(self, output=None):
        """The work area and output to use: the given one, else the focused one."""
        outputs = _ipc("window-rules/list-outputs") or []
        if output is None:
            focused = _ipc("window-rules/get-focused-output") or {}
            output = (focused.get("info") or {}).get("name")
        for o in outputs:
            if isinstance(o, dict) and (output is None or o.get("name") == output):
                return o
        return None

    def _on_monitor(self, name):
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        for i in range(monitors.get_n_items()):
            monitor = monitors.get_item(i)
            if monitor.get_connector() == name:
                LS.set_monitor(self, monitor)
                return

    NAMED_ZONES = {
        "left": (0, 0, 1 / 2, 1), "right": (1 / 2, 0, 1 / 2, 1),
        "left-third": (0, 0, 1 / 3, 1), "center-third": (1 / 3, 0, 1 / 3, 1),
        "right-third": (2 / 3, 0, 1 / 3, 1),
        "top-left": (0, 0, 1 / 2, 1 / 2), "top-right": (1 / 2, 0, 1 / 2, 1 / 2),
        "bottom-left": (0, 1 / 2, 1 / 2, 1 / 2), "bottom-right": (1 / 2, 1 / 2, 1 / 2, 1 / 2),
    }

    def snap_focused(self, name):
        """Put the focused window in a named zone (Super+Ctrl+D/F/G: thirds)."""
        zone = self.NAMED_ZONES.get(name)
        if zone is None or not available():
            return
        focused = (_ipc("window-rules/get-focused-view") or {}).get("info") or {}
        if focused.get("role") != "toplevel":
            return
        where = self._where(focused.get("output-name"))
        if where is None:
            return
        area = where.get("workarea") or where.get("geometry")
        place(focused["id"], with_gaps(zone_geometry(zone, area), area, gap()))

    def show_layouts(self):
        if not available():
            self.shell.notifications.notify(
                _("Snap Layouts"), 0, "view-grid-symbolic",
                _("Snap Layouts need the Aurora (Wayfire) session"), "", [],
                {"transient": True}, -1)
            return
        if self.get_visible():
            self.close_overlay()
            return
        focused = (_ipc("window-rules/get-focused-view") or {}).get("info") or {}
        self.target = focused.get("id") if focused.get("role") == "toplevel" else None
        where = self._where(focused.get("output-name") if self.target else None)
        if where is None:
            return
        self._open(where)
        # The preview under the picker, so the picker stays readable.
        self.fixed.put(self.preview, 0, 0)
        self.preview.set_visible(False)
        _w, natural = self.picker.get_preferred_size()
        self.fixed.put(self.picker, self.area["x"] + (self.area["width"] - natural.width) // 2,
                       self.area["y"] + 16)

    def _open(self, where):
        self._clear()
        self.output = where.get("name", "")
        self.area = where.get("workarea") or where.get("geometry")
        # The surface covers the whole output; the work area is inside it.
        origin = where.get("geometry", {"x": 0, "y": 0})
        self.area = dict(self.area, x=self.area["x"] - origin["x"],
                         y=self.area["y"] - origin["y"])
        self._origin = origin
        self.placed = set()
        self._on_monitor(self.output)
        self.present()

    def close_overlay(self):
        self.set_visible(False)
        self._clear()
        self.zones = []

    def _screen(self, g):
        """Surface coordinates → compositor (global) coordinates."""
        return dict(g, x=g["x"] + self._origin["x"], y=g["y"] + self._origin["y"])

    # --- placing -----------------------------------------------------------------

    def _chose(self, layout, zone):
        rest = [z for z in layout if z != zone]
        if self.target is not None:
            place(self.target, self._screen(with_gaps(zone_geometry(zone, self.area),
                                                      self.area, gap())))
            self.placed.add(self.target)
            self._assist(rest)
        else:
            # No window was focused: every zone, this one first, gets a window.
            self._assist([zone] + rest)

    def _assist(self, zones):
        """Offer the other windows in each empty zone, one zone at a time."""
        self._clear()
        views = _ipc("window-rules/list-views") or []
        offer = candidates(views, self.output, self.placed)
        self.zones = list(zones)
        if not self.zones or not offer:
            self.close_overlay()
            return
        zone = self.zones[0]
        for other in self.zones[1:]:
            ghost = Gtk.Box(css_classes=["snap-ghost"], can_target=False)
            self._put(ghost, zone_geometry(other, self.area))
        g = zone_geometry(zone, self.area)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                        css_classes=["snap-assist"])
        panel.append(Gtk.Label(label=_("Choose a window for this space"),
                               css_classes=["snap-assist-title"]))
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=max(1, (g["width"] - 60) // 170),
                           min_children_per_line=1, column_spacing=10, row_spacing=10,
                           valign=Gtk.Align.START, halign=Gtk.Align.CENTER)
        for view in offer:
            flow.append(self._window_card(view, g))
        scroller = Gtk.ScrolledWindow(child=flow, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        panel.append(scroller)
        skip = Gtk.Button(label=_("Leave Empty"), css_classes=["pill", "snap-skip"],
                          halign=Gtk.Align.CENTER)
        skip.connect("clicked", lambda *_a: self._assist(self.zones[1:]))
        panel.append(skip)
        self._put(panel, g)

    def _window_card(self, view, g):
        app = apps.find_app(view.get("app-id") or "")
        button = Gtk.Button(css_classes=["snap-window"], focusable=True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        icon = Gtk.Image(pixel_size=48)
        if app is not None and app.get_icon() is not None:
            icon.set_from_gicon(app.get_icon())
        else:
            icon.set_from_icon_name("application-x-executable")
        box.append(icon)
        box.append(Gtk.Label(label=view.get("title") or (app.get_display_name() if app else ""),
                             ellipsize=Pango.EllipsizeMode.END, max_width_chars=18,
                             css_classes=["caption"]))
        button.set_child(box)
        button.connect("clicked", lambda *_a: self._fill(view["id"], g))
        return button

    def _fill(self, view_id, g):
        place(view_id, self._screen(with_gaps(g, self.area, gap())))
        self.placed.add(view_id)
        self._assist(self.zones[1:])

    # --- closing ------------------------------------------------------------------

    def _on_background_click(self, *_a):
        self.close_overlay()

    def _on_key(self, _ctrl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.close_overlay()
            return True
        return False

    def _gap_tiled(self, view, edges):
        """Wayfire snapped a window (Super+arrows, or dragged to an edge):
        leave the gap from Settings around it. Not when maximized."""
        size = gap()
        full = EDGE_TOP | EDGE_BOTTOM | EDGE_LEFT | EDGE_RIGHT
        if size <= 0 or not edges or edges == full or view.get("id") is None:
            return
        where = self._where(view.get("output-name"))
        g = view.get("geometry")
        if where is None or not g:
            return
        area = where.get("workarea") or where.get("geometry")
        _ipc("window-rules/configure-view",
             {"id": view["id"], "geometry": with_gaps(g, area, size)})

    # --- Snap Assist after Super+←/→ ------------------------------------------------

    def _watch_events(self):
        """Listen to Wayfire for windows snapped to a half, on its own
        connection; reconnect if Wayfire restarts."""
        while True:
            try:
                with socket.socket(socket.AF_UNIX) as connection:
                    connection.connect(os.environ["WAYFIRE_SOCKET"])
                    payload = json.dumps({"method": "window-rules/events/watch",
                                          "data": {"events": ["view-tiled"]}}).encode()
                    connection.sendall(struct.pack("<I", len(payload)) + payload)
                    while True:
                        size = struct.unpack("<I", wayfirelayout._read(connection, 4))[0]
                        message = json.loads(wayfirelayout._read(connection, size))
                        if message.get("event") == "view-tiled":
                            GLib.idle_add(self._on_tiled, message)
            except (OSError, ValueError, ConnectionError, KeyError, struct.error):
                time.sleep(5)

    def _on_tiled(self, message):
        view = message.get("view") or {}
        self._gap_tiled(view, message.get("new-edges"))
        zone = other_half(message.get("new-edges"))
        if zone is None or message.get("old-edges") == message.get("new-edges") \
                or self.get_visible():
            return False
        views = _ipc("window-rules/list-views") or []
        output = view.get("output-name")
        # The other half already holds a snapped window: nothing to offer.
        if any(v.get("output-name") == output and v.get("id") != view.get("id")
               and not v.get("minimized") and v.get("tiled-edges") in (LEFT_HALF, RIGHT_HALF)
               and v.get("tiled-edges") != view.get("tiled-edges") for v in views):
            return False
        if not candidates(views, output, {view.get("id")}):
            return False
        where = self._where(output)
        if where is None:
            return False
        self.target = view.get("id")
        self._open(where)
        self.placed = {view.get("id")}
        self._assist([zone])
        return False
