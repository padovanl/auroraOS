"""The dock: pinned and running apps, Launchpad and Trash.

The layer surface spans the whole screen edge and is tall enough for fully
magnified icons, so magnifying never resizes the surface. Only the visible
bar receives input (see _update_input_region), and the exclusive zone covers
just the resting bar.
"""

import math

import cairo
from gi.repository import Gdk, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.shell.layer import EDGES, Layer, LayerWindow, LS
from aurora.shell.toplevels import window_labels

MAX_DOTS = 3           # running-window dots under an icon
PEEK_DELAY_MS = 500    # rest on an icon this long to see its windows
MAX_SCALE = 1.7        # magnified icon size relative to the resting size
SPREAD = 2.6           # how many icon widths the magnification reaches
BAR_PADDING = 28       # bar padding + item padding + running dot around an icon
EDGE_MARGIN = 6        # gap between a floating dock and the screen edge
HOT_EDGE = 3           # thickness of the reveal strip when autohidden
TRASH_URI = "trash:///"


def _is_live():
    try:
        with open("/proc/cmdline") as f:
            return "boot=live" in f.read().split()
    except OSError:
        return False


LIVE = _is_live()


def dock_settings():
    s = settings.get()
    if s is None:
        return {"position": "bottom", "style": "floating", "size": 48, "magnify": True,
                "autohide": False, "trash": True}
    return {"position": s.get_string("dock-position"), "style": s.get_string("dock-style"),
            "size": s.get_int("dock-icon-size"), "magnify": s.get_boolean("dock-magnification"),
            "autohide": s.get_boolean("dock-autohide"), "trash": s.get_boolean("dock-show-trash")}


class DockItem(Gtk.Button):
    def __init__(self, dock, key, app=None, pinned=False, icon=None, tooltip=None):
        super().__init__(css_classes=["flat", "dock-item"])
        self.dock = dock
        if dock.position == "bottom":
            self.set_valign(Gtk.Align.END)
        else:
            self.set_halign(Gtk.Align.START if dock.position == "left" else Gtk.Align.END)
        self.key = key
        self.app = app
        self.pinned = pinned
        self.windows = []
        self.target = self.current = float(dock.icon_size)

        self.icon = Gtk.Image(pixel_size=dock.icon_size)
        if icon is not None:
            self.set_icon(icon)
        elif app and app.get_icon():
            self.icon.set_from_gicon(app.get_icon())
        else:
            self.icon.set_from_icon_name("application-x-executable")
        # Running indicator sits between the icon and the screen edge.
        # One dot per open window (at most MAX_DOTS), side by side along the dock.
        self.dots = Gtk.Box(css_classes=["dock-dots"], halign=Gtk.Align.CENTER,
                            valign=Gtk.Align.CENTER, spacing=3,
                            orientation=Gtk.Orientation.VERTICAL if dock.vertical
                            else Gtk.Orientation.HORIZONTAL)
        content = Gtk.Box(spacing=2, orientation=Gtk.Orientation.HORIZONTAL if dock.vertical
                          else Gtk.Orientation.VERTICAL)
        parts = [self.dots, self.icon] if dock.position == "left" else [self.icon, self.dots]
        for w in parts:
            content.append(w)
        self.set_child(content)
        self.set_tooltip_text(tooltip or (app.get_display_name() if app else key))

        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", lambda *_: self.show_menu())
        self.add_controller(right)
        # Resting on an app with several windows shows them, to pick one.
        self._peek = None
        self._peek_source = 0
        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *_: self._peek_later())
        hover.connect("leave", lambda *_: self._peek_cancel(close=True))
        self.add_controller(hover)
        if app is not None:
            self.connect("clicked", self._on_click)
            middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
            middle.connect("pressed", lambda *_: self.launch())
            self.add_controller(middle)

    def set_icon(self, icon):
        if isinstance(icon, Gio.Icon):
            self.icon.set_from_gicon(icon)
        else:
            self.icon.set_from_icon_name(icon)

    def set_windows(self, windows):
        self.windows = windows
        while (c := self.dots.get_first_child()) is not None:
            self.dots.remove(c)
        for w in windows[:MAX_DOTS]:
            self.dots.append(Gtk.Box(css_classes=["dock-dot", "active"] if w.activated
                                     else ["dock-dot"]))
        if any(w.activated for w in windows):
            self.add_css_class("focused")
        else:
            self.remove_css_class("focused")

    # --- window picker on hover ---

    def _peek_later(self):
        self._peek_cancel()
        if len(self.windows) > 1 and self._peek is None:
            self._peek_source = GLib.timeout_add(PEEK_DELAY_MS, self._show_peek)

    def _peek_cancel(self, close=False):
        if self._peek_source:
            GLib.source_remove(self._peek_source)
            self._peek_source = 0
        if close and self._peek is not None:
            # Time to move the pointer from the icon onto the card.
            self._peek_source = GLib.timeout_add(350, self._close_peek)

    def _close_peek(self):
        self._peek_source = 0
        if self._peek is not None:
            self._peek.popdown()
        return GLib.SOURCE_REMOVE

    def _show_peek(self):
        self._peek_source = 0
        if len(self.windows) < 2:
            return GLib.SOURCE_REMOVE
        pop = Gtk.Popover(has_arrow=True, autohide=False, position=self.dock.popover_side,
                          css_classes=["dock-peek"])
        pop.set_parent(self)
        box = Gtk.Box(spacing=8, orientation=Gtk.Orientation.VERTICAL if self.dock.vertical
                      else Gtk.Orientation.HORIZONTAL)
        labels = window_labels(self.windows, _("Window"))
        for w in self.windows:
            title = labels[w]
            card = Gtk.Button(css_classes=["flat", "dock-peek-card"], tooltip_text=w.title)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            icon = Gtk.Image(pixel_size=48)
            if self.app and self.app.get_icon():
                icon.set_from_gicon(self.app.get_icon())
            else:
                icon.set_from_icon_name("application-x-executable")
            inner.append(icon)
            inner.append(Gtk.Label(label=title, ellipsize=3,
                                   max_width_chars=18, width_chars=12))
            if w.minimized:
                inner.append(Gtk.Label(label=_("Minimized"), css_classes=["dim-label", "caption"]))
            if w.activated:
                card.add_css_class("active")
            card.set_child(inner)
            card.connect("clicked", lambda _b, w=w: (pop.popdown(), w.activate()))
            box.append(card)
        pop.set_child(box)
        # Staying on the card keeps it open; leaving it closes it.
        hover = Gtk.EventControllerMotion()
        hover.connect("enter", lambda *_: self._peek_cancel())
        hover.connect("leave", lambda *_: self._peek_cancel(close=True))
        pop.add_controller(hover)

        def closed(p):
            self._peek = None
            self.set_has_tooltip(True)
            GLib.idle_add(p.unparent)
        pop.connect("closed", closed)
        self._peek = pop
        self.set_has_tooltip(False)  # the card already names the windows
        self.dock.hold(pop)
        pop.popup()
        return GLib.SOURCE_REMOVE

    def launch(self):
        if self.app:
            self.add_css_class("launching")
            GLib.timeout_add(1200, lambda: self.remove_css_class("launching"))
            apps.launch(self.app)

    def _on_click(self, *_a):
        if not self.windows:
            self.launch()
            return
        active = [w for w in self.windows if w.activated and not w.minimized]
        if active and len(self.windows) > 1:
            idx = self.windows.index(active[0])
            self.windows[(idx + 1) % len(self.windows)].activate()
        else:
            self.windows[0].toggle()

    def menu_entries(self):
        entries = [(w.title or _("Window"), w.activate) for w in self.windows]
        if self.windows:
            entries.append(None)
        if self.app:
            actions = list(self.app.list_actions())
            # Single-instance apps (Ptyxis, Files, Text Editor…) only raise their
            # window when launched again: use their own "new window" action.
            new_window = next((a for a in actions if a.replace("_", "-").lower()
                               in ("new-window", "new-window-action", "window")), None)
            if new_window:
                entries.append((_("New Window"),
                                lambda a=new_window: apps.launch(self.app, action=a)))
            else:
                entries.append((_("New Window"), self.launch))
            for action in actions:
                if action == new_window:
                    continue
                entries.append((self.app.get_action_name(action),
                                lambda a=action: apps.launch(self.app, action=a)))
            entries.append(None)
            if self.pinned:
                entries.append((_("Remove from Dock"), lambda: self.dock.unpin(self.key)))
            else:
                entries.append((_("Keep in Dock"), lambda: self.dock.pin(self.key)))
        if self.windows:
            label = _("Quit") if len(self.windows) == 1 else \
                _("Quit {n} Windows").format(n=len(self.windows))
            entries.append((label, lambda: [w.close() for w in self.windows]))
        return entries

    def show_menu(self):
        self._peek_cancel()
        self._close_peek()
        entries = self.menu_entries()
        if not entries:
            return
        pop = Gtk.Popover(has_arrow=True, position=self.dock.popover_side)
        pop.set_parent(self)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for entry in entries:
            if entry is None:
                box.append(Gtk.Separator())
                continue
            label, cb = entry
            b = Gtk.Button(label=label, css_classes=["flat"])
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), cb()))
            box.append(b)
        pop.set_child(box)
        self.dock.hold(pop)
        pop.popup()


class MinimizedItem(DockItem):
    """A minimized window, kept at the end of the dock like on a Mac: one click
    brings it back."""

    def __init__(self, dock, window, app):
        super().__init__(dock, f"min:{id(window)}", icon=(app.get_icon() if app and app.get_icon()
                                                        else "application-x-executable"),
                         tooltip=window.title or (app.get_display_name() if app else _("Window")))
        self.window = window
        self.add_css_class("dock-minimized")
        badge = Gtk.Image(icon_name="go-down-symbolic", pixel_size=12, css_classes=["dock-badge"],
                          halign=Gtk.Align.END, valign=Gtk.Align.END)
        overlay = Gtk.Overlay()
        content = self.get_child()
        self.set_child(overlay)
        overlay.set_child(content)
        overlay.add_overlay(badge)
        self.connect("clicked", lambda *_: self.window.activate())

    def menu_entries(self):
        return [(_("Restore"), self.window.activate), None, (_("Close"), self.window.close)]


class TrashItem(DockItem):
    def __init__(self, dock):
        super().__init__(dock, "trash", icon="user-trash", tooltip=_("Trash"))
        self._file = Gio.File.new_for_uri(TRASH_URI)
        self.connect("clicked", lambda *_: apps.spawn(["aurora-files", TRASH_URI]))
        try:
            self._monitor = self._file.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            self._monitor.connect("changed", lambda *a: self._refresh())
        except GLib.Error:
            self._monitor = None
        self._refresh()

    def _count(self):
        try:
            info = self._file.query_info("trash::item-count", Gio.FileQueryInfoFlags.NONE, None)
            return info.get_attribute_uint32("trash::item-count")
        except GLib.Error:
            return 0

    def _refresh(self):
        self.set_icon("user-trash-full" if self._count() else "user-trash")

    def menu_entries(self):
        return [(_("Open"), lambda: apps.spawn(["aurora-files", TRASH_URI])),
                (_("Empty Trash"), self._empty)]

    def _empty(self):
        try:
            for child in self._file.enumerate_children("standard::name",
                                                       Gio.FileQueryInfoFlags.NONE, None):
                self._file.get_child(child.get_name()).delete(None)
        except GLib.Error as err:
            print(f"aurora: empty trash failed: {err.message}")
        self._refresh()


class Dock(LayerWindow):
    def __init__(self, shell, monitor):
        cfg = dock_settings()
        self.position = cfg["position"] if cfg["position"] in ("bottom", "left", "right") \
            else "bottom"
        self.vertical = self.position in ("left", "right")
        self.floating = cfg["style"] == "floating"
        self.icon_size = cfg["size"]
        self.magnify = cfg["magnify"] and self.floating
        self.autohide = cfg["autohide"]
        self.show_trash = cfg["trash"]
        self.popover_side = {"bottom": Gtk.PositionType.TOP, "left": Gtk.PositionType.RIGHT,
                             "right": Gtk.PositionType.LEFT}[self.position]

        across = ("left", "right") if not self.vertical else ("top", "bottom")
        super().__init__(shell, "aurora-dock", layer=Layer.TOP,
                         anchors=(self.position,) + across, monitor=monitor, exclusive=False)
        self.add_css_class("aurora-dock")
        self.add_css_class("dock-floating" if self.floating else "dock-panel")
        self.add_css_class(f"dock-{self.position}")
        self.shell = shell
        self._items = {}
        self._held = 0
        self._hidden = False
        self._hide_source = 0
        self._tick_id = 0
        self._pointer = None

        # The shelf (background) keeps its resting size; the icon row sits on
        # top of it and may grow past it while magnified.
        orient = Gtk.Orientation.VERTICAL if self.vertical else Gtk.Orientation.HORIZONTAL
        self.box = Gtk.Box(orientation=orient, spacing=4, css_classes=["dock-row"])
        self.bar_thickness = self.icon_size + BAR_PADDING
        self.shelf = Gtk.Box(css_classes=["dock-box"])
        self.body = Gtk.Overlay(child=self.shelf)
        self.body.add_overlay(self.box)
        self.body.set_measure_overlay(self.box, True)
        if self.position == "bottom":
            self.shelf.set_size_request(-1, self.bar_thickness)
            self.shelf.set_valign(Gtk.Align.END)
            self.box.set_valign(Gtk.Align.END)
            self.box.set_halign(Gtk.Align.CENTER if self.floating else Gtk.Align.START)
        else:
            self.shelf.set_size_request(self.bar_thickness, -1)
            edge = Gtk.Align.START if self.position == "left" else Gtk.Align.END
            self.shelf.set_halign(edge)
            self.box.set_halign(edge)
            self.box.set_valign(Gtk.Align.CENTER if self.floating else Gtk.Align.START)
        if self.floating:
            if self.vertical:
                self.body.set_valign(Gtk.Align.CENTER)
                self.body.set_halign(Gtk.Align.START if self.position == "left" else Gtk.Align.END)
            else:
                self.body.set_halign(Gtk.Align.CENTER)
                self.body.set_valign(Gtk.Align.END)
        else:
            self.body.set_hexpand(True)
            self.body.set_vexpand(True)

        margin = EDGE_MARGIN if self.floating else 0
        {"bottom": self.body.set_margin_bottom, "left": self.body.set_margin_start,
         "right": self.body.set_margin_end}[self.position](margin)
        grow = int(self.icon_size * (MAX_SCALE - 1)) + 4 if self.magnify else 0
        self.thickness = self.bar_thickness + margin + grow

        self.revealer = Gtk.Revealer(child=self.body, reveal_child=True,
                                     transition_duration=220,
                                     transition_type={
                                         "bottom": Gtk.RevealerTransitionType.SLIDE_UP,
                                         "left": Gtk.RevealerTransitionType.SLIDE_RIGHT,
                                         "right": Gtk.RevealerTransitionType.SLIDE_LEFT,
                                     }[self.position])
        self.revealer.connect("notify::child-revealed", lambda *a: self._update_geometry())
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL if not self.vertical
                        else Gtk.Orientation.HORIZONTAL)
        frame.set_halign(Gtk.Align.FILL)
        frame.set_valign(Gtk.Align.FILL)
        if self.position == "bottom":
            frame.set_valign(Gtk.Align.END)
        elif self.position == "right":
            frame.set_halign(Gtk.Align.END)
        frame.append(self.revealer)
        self.set_child(frame)
        if self.vertical:
            self.set_default_size(self.thickness, -1)
        else:
            self.set_default_size(-1, self.thickness)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._on_enter)
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

        s = settings.get()
        if s:
            s.connect("changed::dock-favorites", lambda *a: self.rebuild())
        shell.toplevels.connect("changed", lambda *a: self.rebuild())
        Gio.AppInfoMonitor.get().connect("changed", lambda *a: (apps.invalidate(), self.rebuild()))
        self.connect("map", lambda *a: GLib.idle_add(self._update_geometry))
        self.rebuild()
        if self.autohide:
            GLib.timeout_add(1500, self._auto_hide)

    # --- favorites ---

    def favorites(self):
        s = settings.get()
        favs = list(s.get_strv("dock-favorites")) if s else [
            "firefox-esr.desktop", "org.aurora.Files.desktop", "org.gnome.Ptyxis.desktop",
            "org.aurora.Settings.desktop"]
        if LIVE and "aurora-installer.desktop" not in favs:
            favs.insert(0, "aurora-installer.desktop")
        return favs

    def pin(self, key):
        s = settings.get()
        favs = [f for f in self.favorites() if f != "aurora-installer.desktop"]
        if s and key not in favs:
            s.set_strv("dock-favorites", favs + [key])

    def unpin(self, key):
        s = settings.get()
        if s:
            s.set_strv("dock-favorites", [f for f in self.favorites()
                                          if f not in (key, "aurora-installer.desktop")])

    # --- content ---

    def _separator(self):
        return Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL if self.vertical
                             else Gtk.Orientation.VERTICAL, css_classes=["dock-separator"])

    def rebuild(self):
        order, entries = [], {}
        for fav in self.favorites():
            app = apps.app_by_id(fav)
            if app:
                entries[fav] = (app, True, [])
                order.append(fav)
        pinned_count = len(order)
        for t in self.shell.toplevels.toplevels:
            app = apps.find_app(t.app_id)
            key = app.get_id() if app else (t.app_id or "unknown")
            if key not in entries:
                entries[key] = (app, False, [])
                order.append(key)
            entries[key][2].append(t)

        while (c := self.box.get_first_child()) is not None:
            self.box.remove(c)
        old, self._items = self._items, {}

        launchpad = old.get("launchpad") or DockItem(self, "launchpad",
                                                     icon="view-app-grid-symbolic",
                                                     tooltip=_("Launchpad"))
        if "launchpad" not in old:
            launchpad.add_css_class("dock-launchpad")
            launchpad.connect("clicked", lambda *_: self.shell.launcher.toggle("grid"))
        self._items["launchpad"] = launchpad
        self.box.append(launchpad)

        for i, key in enumerate(order):
            if i == pinned_count and pinned_count:
                self.box.append(self._separator())
            app, pinned, windows = entries[key]
            item = old.get(key)
            if item is None or item.pinned != pinned or isinstance(item, TrashItem):
                item = DockItem(self, key, app, pinned)
            item.set_windows(sorted(windows, key=lambda w: w.serial, reverse=True))
            self._items[key] = item
            self.box.append(item)

        # Minimized windows, each with its own icon, before the Trash.
        minimized = [t for t in self.shell.toplevels.toplevels if t.minimized]
        if minimized:
            self.box.append(self._separator())
            for t in sorted(minimized, key=lambda w: w.serial):
                key = f"min:{id(t)}"
                item = old.get(key) or MinimizedItem(self, t, apps.find_app(t.app_id))
                self._items[key] = item
                self.box.append(item)

        if self.show_trash:
            self.box.append(self._separator())
            trash = old.get("trash") or TrashItem(self)
            self._items["trash"] = trash
            self.box.append(trash)
        # The dock changed under the pointer: magnify from where the pointer is
        # now, or not at all (the leave event may never come).
        GLib.idle_add(self._refresh_magnification)
        GLib.idle_add(self._update_geometry)

    def _refresh_magnification(self):
        if self._pointer is not None:
            ok, box = self.box.compute_bounds(self)
            x, y = self._pointer
            if not ok or not (box.get_x() <= x <= box.get_x() + box.get_width()
                              and box.get_y() <= y <= box.get_y() + box.get_height()):
                self._pointer = None
        if self._pointer is not None and self.magnify and not self._hidden:
            self._magnify_at(*self._pointer)
        else:
            for item in self._items.values():
                item.target = float(self.icon_size)
            self._animate()
        return GLib.SOURCE_REMOVE

    # --- magnification ---

    def _on_motion(self, _ctrl, x, y):
        # Resizing icons makes GTK report the pointer again where it already
        # was; reacting to that would animate forever under a still pointer.
        if self._pointer == (x, y):
            return
        self._pointer = (x, y)
        if not self.magnify or self._hidden:
            return
        self._magnify_at(x, y)

    def _magnify_at(self, x, y):
        pos = y if self.vertical else x
        for item in self._items.values():
            ok, bounds = item.compute_bounds(self)
            if not ok:
                continue
            center = (bounds.get_y() + bounds.get_height() / 2) if self.vertical else \
                (bounds.get_x() + bounds.get_width() / 2)
            d = abs(pos - center) / (self.icon_size * SPREAD)
            f = math.cos(min(d, 1.0) * math.pi / 2) ** 2 if d < 1 else 0.0
            item.target = self.icon_size * (1 + (MAX_SCALE - 1) * f)
        self._animate()

    def _on_enter(self, ctrl, x, y):
        if self._hide_source:
            GLib.source_remove(self._hide_source)
            self._hide_source = 0
        if self._hidden:
            self._show()
        self._on_motion(ctrl, x, y)

    def _on_leave(self, *_a):
        self._pointer = None
        for item in self._items.values():
            item.target = float(self.icon_size)
        self._animate()
        if self.autohide and not self._held:
            self._schedule_hide()

    def _animate(self):
        if not self._tick_id:
            self._tick_id = self.add_tick_callback(self._tick)

    def _tick(self, *_a):
        moving = False
        for item in self._items.values():
            delta = item.target - item.current
            if abs(delta) > 0.5:
                item.current += delta * 0.35
                moving = True
            else:
                item.current = item.target
            item.icon.set_pixel_size(int(round(item.current)))
        if not moving:
            self._tick_id = 0
            GLib.idle_add(self._update_geometry)
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # --- autohide ---

    def hold(self, popover):
        """Keep the dock visible while one of its menus is open."""
        self._held += 1

        def closed(*_a):
            self._held -= 1
            if self.autohide and self._pointer is None:
                self._schedule_hide()
        popover.connect("closed", closed)

    def _schedule_hide(self):
        if self._hide_source:
            GLib.source_remove(self._hide_source)
        self._hide_source = GLib.timeout_add(600, self._auto_hide)

    def _auto_hide(self):
        self._hide_source = 0
        if self.autohide and not self._held and self._pointer is None:
            self._hidden = True
            self.revealer.set_reveal_child(False)
        return GLib.SOURCE_REMOVE

    def _show(self):
        self._hidden = False
        self.revealer.set_reveal_child(True)

    # --- geometry ---

    def _update_geometry(self):
        """Exclusive zone for the resting bar; input only where the dock is drawn."""
        margin = EDGE_MARGIN if self.floating else 0
        if self.autohide:
            LS.set_exclusive_zone(self, 0)
        else:
            LS.set_exclusive_zone(self, self.bar_thickness + margin)
        surface = self.get_surface()
        if surface is None:
            return GLib.SOURCE_REMOVE
        w, h = self.get_width(), self.get_height()
        if self._hidden or not self.revealer.get_child_revealed():
            if self.position == "bottom":
                rect = (0, h - HOT_EDGE, w, HOT_EDGE)
            elif self.position == "left":
                rect = (0, 0, HOT_EDGE, h)
            else:
                rect = (w - HOT_EDGE, 0, HOT_EDGE, h)
        else:
            ok, b = self.body.compute_bounds(self)
            if not ok:
                return GLib.SOURCE_REMOVE
            x, y, bw, bh = b.get_x(), b.get_y(), b.get_width(), b.get_height()
            # Include the gap to the screen edge so the pointer can't slip through.
            if self.position == "bottom":
                rect = (x, y, bw, h - y)
            elif self.position == "left":
                rect = (0, y, x + bw, bh)
            else:
                rect = (x, y, w - x, bh)
            if self.magnify:
                grow = int(self.icon_size * (MAX_SCALE - 1))
                if self.position == "bottom":
                    rect = (rect[0], max(0, rect[1] - grow), rect[2], rect[3] + grow)
                elif self.position == "left":
                    rect = (rect[0], rect[1], rect[2] + grow, rect[3])
                else:
                    rect = (max(0, rect[0] - grow), rect[1], rect[2] + grow, rect[3])
        region = cairo.Region(cairo.RectangleInt(*[int(v) for v in rect]))
        surface.set_input_region(region)
        return GLib.SOURCE_REMOVE
