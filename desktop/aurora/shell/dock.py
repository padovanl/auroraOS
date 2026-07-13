"""Bottom dock: pinned apps plus running windows."""

from gi.repository import Gdk, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.shell.layer import Layer, LayerWindow

ICON_SIZE = 44


class DockItem(Gtk.Button):
    def __init__(self, dock, key, app, pinned):
        super().__init__(css_classes=["flat", "dock-item"])
        self.dock = dock
        self.key = key          # desktop id, or app_id for unknown apps
        self.app = app
        self.pinned = pinned
        self.windows = []

        overlay = Gtk.Overlay()
        icon = Gtk.Image(pixel_size=ICON_SIZE)
        if app and app.get_icon():
            icon.set_from_gicon(app.get_icon())
        else:
            icon.set_from_icon_name("application-x-executable")
        overlay.set_child(icon)
        self.dots = Gtk.Box(spacing=3, halign=Gtk.Align.CENTER, valign=Gtk.Align.END,
                            css_classes=["dock-dots"])
        overlay.add_overlay(self.dots)
        self.set_child(overlay)
        self.set_tooltip_text(app.get_display_name() if app else key)

        self.connect("clicked", self._on_click)
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", lambda *_: self._menu().popup())
        self.add_controller(right)
        middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle.connect("pressed", lambda *_: self.launch())
        self.add_controller(middle)

    def set_windows(self, windows):
        self.windows = windows
        while (c := self.dots.get_first_child()) is not None:
            self.dots.remove(c)
        for _i in range(min(len(windows), 3)):
            self.dots.append(Gtk.Box(css_classes=["dock-dot"]))
        if any(w.activated for w in windows):
            self.add_css_class("focused")
        else:
            self.remove_css_class("focused")

    def launch(self):
        if self.app:
            self.add_css_class("launching")
            GLib.timeout_add(1500, lambda: self.remove_css_class("launching"))
            apps.launch(self.app)

    def _on_click(self, *_a):
        if not self.windows:
            self.launch()
            return
        active = [w for w in self.windows if w.activated and not w.minimized]
        if active and len(self.windows) > 1:
            # Cycle through this app's windows.
            idx = self.windows.index(active[0])
            self.windows[(idx + 1) % len(self.windows)].activate()
        else:
            self.windows[0].toggle()

    def _menu(self):
        pop = Gtk.Popover(has_arrow=True, position=Gtk.PositionType.TOP)
        pop.set_parent(self)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        def add(label, cb):
            b = Gtk.Button(label=label, css_classes=["flat"])
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda *_: (pop.popdown(), cb()))
            box.append(b)

        for w in self.windows:
            add(w.title or _("Window"), w.activate)
        if self.windows:
            box.append(Gtk.Separator())
        if self.app:
            add(_("New Window"), self.launch)
            for action in self.app.list_actions():
                add(self.app.get_action_name(action),
                    lambda a=action: apps.launch(self.app, action=a))
            if self.pinned:
                add(_("Unpin from Dock"), lambda: self.dock.unpin(self.key))
            else:
                add(_("Pin to Dock"), lambda: self.dock.pin(self.key))
        if self.windows:
            label = _("Quit") if len(self.windows) == 1 else \
                _("Quit {n} Windows").format(n=len(self.windows))
            add(label, lambda: [w.close() for w in self.windows])
        pop.set_child(box)
        return pop


class Dock(LayerWindow):
    def __init__(self, shell, monitor):
        super().__init__(shell, "aurora-dock", layer=Layer.TOP, anchors=("bottom",),
                         monitor=monitor, exclusive=True, margins={"bottom": 6})
        self.add_css_class("aurora-dock")
        self.shell = shell
        self.box = Gtk.Box(spacing=4, css_classes=["dock-box"])
        self.set_child(self.box)
        self._items = {}

        s = settings.get()
        if s:
            s.connect("changed::dock-favorites", lambda *a: self.rebuild())
        shell.toplevels.connect("changed", lambda *a: self.rebuild())
        monitor_ = Gio.AppInfoMonitor.get()
        monitor_.connect("changed", lambda *a: (apps.invalidate(), self.rebuild()))
        self.rebuild()

    def favorites(self):
        s = settings.get()
        if s:
            return list(s.get_strv("dock-favorites"))
        return ["firefox-esr.desktop", "org.aurora.Files.desktop", "foot.desktop",
                "org.aurora.Settings.desktop"]

    def pin(self, key):
        s = settings.get()
        favs = self.favorites()
        if s and key not in favs:
            s.set_strv("dock-favorites", favs + [key])

    def unpin(self, key):
        s = settings.get()
        if s:
            s.set_strv("dock-favorites", [f for f in self.favorites() if f != key])

    def rebuild(self):
        order = []
        entries = {}
        for fav in self.favorites():
            app = apps.app_by_id(fav)
            if app:
                entries[fav] = (app, True, [])
                order.append(fav)

        separator_at = len(order)
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
        for i, key in enumerate(order):
            if i == separator_at and separator_at > 0:
                self.box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL,
                                              css_classes=["dock-separator"]))
            app, pinned, windows = entries[key]
            item = old.get(key)
            if item is None or item.pinned != pinned:
                item = DockItem(self, key, app, pinned)
            item.set_windows(sorted(windows, key=lambda w: w.serial, reverse=True))
            self._items[key] = item
            self.box.append(item)

        self.box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL,
                                      css_classes=["dock-separator"]))
        grid = Gtk.Button(icon_name="view-app-grid-symbolic", tooltip_text=_("Applications"),
                          css_classes=["flat", "dock-item", "dock-apps"])
        grid.connect("clicked", lambda *_: self.shell.launcher.toggle())
        self.box.append(grid)
