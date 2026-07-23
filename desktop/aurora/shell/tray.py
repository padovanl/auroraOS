"""System tray: a StatusNotifierItem host in the top bar.

Apps such as Discord, Slack, Steam, Dropbox, Nextcloud or KeePassXC show an
icon here. Aurora owns org.kde.StatusNotifierWatcher (the registry apps
talk to) and draws each item with its icon; left click activates the app,
right click shows its menu (com.canonical.dbusmenu).
"""

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

WATCHER_XML = """
<node>
  <interface name="org.kde.StatusNotifierWatcher">
    <method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
    <method name="RegisterStatusNotifierHost"><arg type="s" direction="in"/></method>
    <property name="RegisteredStatusNotifierItems" type="as" access="read"/>
    <property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
    <property name="ProtocolVersion" type="i" access="read"/>
    <signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
    <signal name="StatusNotifierItemUnregistered"><arg type="s"/></signal>
    <signal name="StatusNotifierHostRegistered"/>
  </interface>
</node>
"""
ITEM_IFACE = "org.kde.StatusNotifierItem"
MENU_IFACE = "com.canonical.dbusmenu"


class Watcher:
    """Registry of tray items; notifies the tray widget of changes."""

    def __init__(self, on_added, on_removed):
        self.items = {}           # key "busname/path" → (bus_name, path)
        self._watches = {}
        self._on_added, self._on_removed = on_added, on_removed
        self.conn = None
        node = Gio.DBusNodeInfo.new_for_xml(WATCHER_XML)
        self._iface = node.interfaces[0]
        Gio.bus_own_name(Gio.BusType.SESSION, "org.kde.StatusNotifierWatcher",
                         Gio.BusNameOwnerFlags.REPLACE | Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT,
                         self._on_bus, None, lambda *a: print("aurora: tray watcher name lost"))

    def _on_bus(self, conn, _name):
        self.conn = conn
        conn.register_object("/StatusNotifierWatcher", self._iface, self._on_call,
                             self._on_get, None)

    def _on_get(self, _conn, _sender, _path, _iface, prop):
        if prop == "RegisteredStatusNotifierItems":
            return GLib.Variant("as", [f"{b}{p}" for b, p in self.items.values()])
        if prop == "IsStatusNotifierHostRegistered":
            return GLib.Variant("b", True)
        if prop == "ProtocolVersion":
            return GLib.Variant("i", 0)
        return None

    def _on_call(self, conn, sender, _path, _iface, method, params, invocation):
        if method == "RegisterStatusNotifierItem":
            service = params.unpack()[0]
            # Either a bus name (path defaults) or an object path on the sender.
            if service.startswith("/"):
                bus_name, path = sender, service
            else:
                bus_name, path = service, "/StatusNotifierItem"
            key = bus_name + path
            if key not in self.items:
                self.items[key] = (bus_name, path)
                self._watch(bus_name)
                conn.emit_signal(None, "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
                                 "StatusNotifierItemRegistered", GLib.Variant("(s)", (key,)))
                self._on_added(key, bus_name, path)
        invocation.return_value(None)

    def _watch(self, bus_name):
        if bus_name in self._watches:
            return
        self._watches[bus_name] = Gio.bus_watch_name_on_connection(
            self.conn, bus_name, Gio.BusNameWatcherFlags.NONE, None,
            lambda _c, name: self._vanished(name))

    def _vanished(self, bus_name):
        for key, (b, _p) in list(self.items.items()):
            if b == bus_name:
                del self.items[key]
                self.conn.emit_signal(None, "/StatusNotifierWatcher",
                                      "org.kde.StatusNotifierWatcher",
                                      "StatusNotifierItemUnregistered", GLib.Variant("(s)", (key,)))
                self._on_removed(key)
        watch = self._watches.pop(bus_name, None)
        if watch:
            Gio.bus_unwatch_name(watch)


def _pixmap_texture(pixmaps, size=22):
    """Pick the best ARGB32 (network byte order) pixmap and make a texture."""
    if not pixmaps:
        return None
    w, h, data = min(pixmaps, key=lambda p: abs(p[0] - size))
    data = bytearray(data)
    for i in range(0, len(data), 4):   # ARGB → RGBA
        a, r, g, b = data[i:i + 4]
        data[i:i + 4] = bytes((r, g, b, a))
    pix = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(data)), GdkPixbuf.Colorspace.RGB,
                                          True, 8, w, h, w * 4)
    return Gdk.Texture.new_for_pixbuf(pix)


class TrayItem(Gtk.Button):
    def __init__(self, conn, bus_name, path):
        super().__init__(css_classes=["flat", "panel-button", "tray-item"])
        self.conn, self.bus_name, self.path = conn, bus_name, path
        self.image = Gtk.Image(pixel_size=16)
        self.set_child(self.image)
        self.props_ = {}
        self.connect("clicked", lambda *_: self._activate())
        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("pressed", lambda *_: self._show_menu())
        self.add_controller(right)
        middle = Gtk.GestureClick(button=Gdk.BUTTON_MIDDLE)
        middle.connect("pressed", lambda *_: self._call(ITEM_IFACE, "SecondaryActivate",
                                                        GLib.Variant("(ii)", (0, 0))))
        self.add_controller(middle)
        self._subs = [conn.signal_subscribe(bus_name, ITEM_IFACE, sig, path, None,
                                            Gio.DBusSignalFlags.NONE, lambda *a: self.refresh())
                      for sig in ("NewIcon", "NewStatus", "NewTitle", "NewToolTip",
                                  "NewAttentionIcon")]
        self.refresh()

    def destroy_item(self):
        for s in self._subs:
            self.conn.signal_unsubscribe(s)

    def _call(self, iface, method, params, path=None, callback=None):
        self.conn.call(self.bus_name, path or self.path, iface, method, params, None,
                       Gio.DBusCallFlags.NONE, 3000, None, callback)

    def refresh(self, *_a):
        def done(conn, res):
            try:
                self.props_ = conn.call_finish(res).unpack()[0]
            except GLib.Error:
                return
            self._render()
        self.conn.call(self.bus_name, self.path, "org.freedesktop.DBus.Properties", "GetAll",
                       GLib.Variant("(s)", (ITEM_IFACE,)), None, Gio.DBusCallFlags.NONE, 3000,
                       None, done)

    def _render(self):
        p = self.props_
        self.set_visible(p.get("Status", "Active") != "Passive")
        tooltip = p.get("ToolTip")
        title = (tooltip[2] if tooltip and len(tooltip) > 2 and tooltip[2] else None) \
            or p.get("Title") or ""
        self.set_tooltip_text(title)
        attention = p.get("Status") == "NeedsAttention"
        icon_name = (attention and p.get("AttentionIconName")) or p.get("IconName")
        theme_path = p.get("IconThemePath")
        if icon_name:
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            if theme_path and theme_path not in theme.get_search_path():
                theme.add_search_path(theme_path)
            if theme.has_icon(icon_name) or icon_name.startswith("/"):
                if icon_name.startswith("/"):
                    self.image.set_from_file(icon_name)
                else:
                    self.image.set_from_icon_name(icon_name)
                return
        texture = _pixmap_texture((attention and p.get("AttentionIconPixmap")) or
                                  p.get("IconPixmap"))
        if texture is not None:
            self.image.set_from_paintable(texture)
        else:
            self.image.set_from_icon_name("application-x-executable-symbolic")

    def _activate(self):
        if self.props_.get("ItemIsMenu") and self.props_.get("Menu"):
            self._show_menu()
        else:
            self._call(ITEM_IFACE, "Activate", GLib.Variant("(ii)", (0, 0)))

    # --- dbusmenu ---

    def _show_menu(self):
        menu_path = self.props_.get("Menu")
        if not menu_path:
            self._call(ITEM_IFACE, "ContextMenu", GLib.Variant("(ii)", (0, 0)))
            return
        self._call(MENU_IFACE, "AboutToShow", GLib.Variant("(i)", (0,)), menu_path)

        def done(conn, res):
            try:
                _rev, layout = conn.call_finish(res).unpack()
            except GLib.Error:
                return
            self._popup(layout, menu_path)
        self.conn.call(self.bus_name, menu_path, MENU_IFACE, "GetLayout",
                       GLib.Variant("(iias)", (0, -1, [])), None, Gio.DBusCallFlags.NONE, 3000,
                       None, done)

    def _popup(self, layout, menu_path):
        pop = Gtk.Popover(has_arrow=False, position=Gtk.PositionType.BOTTOM)
        pop.set_parent(self)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self._fill(box, layout, menu_path, pop, depth=0)
        pop.set_child(box)
        pop.popup()

    def _fill(self, box, node, menu_path, pop, depth):
        _id, _props, children = node
        for child in children:
            cid, props, sub = child
            if not props.get("visible", True):
                continue
            if props.get("type") == "separator":
                box.append(Gtk.Separator(margin_top=3, margin_bottom=3))
                continue
            label = (props.get("label") or "").replace("__", "\0").replace("_", "").replace("\0", "_")
            if sub:
                header = Gtk.Label(label=label, xalign=0, css_classes=["dim-label", "caption"],
                                   margin_top=6, margin_start=8 + 12 * depth)
                box.append(header)
                self._fill(box, child, menu_path, pop, depth + 1)
                continue
            text = label
            if props.get("toggle-type") in ("checkmark", "radio") and props.get("toggle-state") == 1:
                text = "✓  " + label
            b = Gtk.Button(label=text, css_classes=["flat"], sensitive=props.get("enabled", True))
            b.get_child().set_xalign(0)
            b.set_margin_start(12 * depth)

            def clicked(_b, cid=cid):
                pop.popdown()
                self.conn.call(self.bus_name, menu_path, MENU_IFACE, "Event",
                               GLib.Variant("(isvu)", (cid, "clicked", GLib.Variant("i", 0), 0)),
                               None, Gio.DBusCallFlags.NONE, 3000, None, None)
            b.connect("clicked", clicked)
            box.append(b)


class Tray(Gtk.Box):
    """The row of tray icons in the top bar (one watcher shared by all panels)."""

    _watcher = None
    _instances = []

    def __init__(self):
        super().__init__(spacing=0, css_classes=["tray"])
        self.items = {}
        Tray._instances.append(self)
        self.connect("destroy", lambda *a: Tray._instances.remove(self)
                     if self in Tray._instances else None)
        if Tray._watcher is None:
            Tray._watcher = Watcher(Tray._added, Tray._removed)
        else:
            for key, (bus_name, path) in Tray._watcher.items.items():
                self._add(key, bus_name, path)

    @classmethod
    def _added(cls, key, bus_name, path):
        for tray in cls._instances:
            tray._add(key, bus_name, path)

    @classmethod
    def _removed(cls, key):
        for tray in cls._instances:
            item = tray.items.pop(key, None)
            if item is not None:
                item.destroy_item()
                tray.remove(item)

    def _add(self, key, bus_name, path):
        if key in self.items or Tray._watcher.conn is None:
            return
        item = TrayItem(Tray._watcher.conn, bus_name, path)
        self.items[key] = item
        self.append(item)
