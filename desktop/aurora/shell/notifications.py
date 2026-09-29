"""org.freedesktop.Notifications server with popups and a history list."""

import html
import re
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from aurora import VERSION, apps, settings
from aurora.otp import verification_code
from aurora.i18n import _
from aurora.shell.layer import Layer, LayerWindow

IFACE_XML = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="GetCapabilities"><arg type="as" direction="out"/></method>
    <method name="Notify">
      <arg type="s" name="app_name" direction="in"/>
      <arg type="u" name="replaces_id" direction="in"/>
      <arg type="s" name="app_icon" direction="in"/>
      <arg type="s" name="summary" direction="in"/>
      <arg type="s" name="body" direction="in"/>
      <arg type="as" name="actions" direction="in"/>
      <arg type="a{sv}" name="hints" direction="in"/>
      <arg type="i" name="expire_timeout" direction="in"/>
      <arg type="u" name="id" direction="out"/>
    </method>
    <method name="CloseNotification"><arg type="u" name="id" direction="in"/></method>
    <method name="GetServerInformation">
      <arg type="s" name="name" direction="out"/>
      <arg type="s" name="vendor" direction="out"/>
      <arg type="s" name="version" direction="out"/>
      <arg type="s" name="spec_version" direction="out"/>
    </method>
    <signal name="NotificationClosed">
      <arg type="u" name="id"/><arg type="u" name="reason"/>
    </signal>
    <signal name="ActionInvoked">
      <arg type="u" name="id"/><arg type="s" name="action_key"/>
    </signal>
  </interface>
</node>
"""

REASON_EXPIRED, REASON_DISMISSED, REASON_CLOSED = 1, 2, 3
URGENCY_CRITICAL = 2
DEFAULT_TIMEOUT_MS = 5000
HISTORY_LIMIT = 50

_ALLOWED_TAGS = re.compile(r"</?(b|i|u)>", re.I)


def sanitize_markup(body):
    """Keep the tiny markup subset from the spec, escape everything else."""
    parts = []
    last = 0
    for m in _ALLOWED_TAGS.finditer(body):
        parts.append(html.escape(html.unescape(body[last:m.start()]), quote=False))
        parts.append(m.group(0).lower())
        last = m.end()
    parts.append(html.escape(html.unescape(body[last:]), quote=False))
    text = "".join(parts)
    try:
        Pango.parse_markup(text, -1, "\0")
        return text
    except GLib.Error:
        return html.escape(re.sub(r"<[^>]+>", "", body), quote=False)


class Notification:
    def __init__(self, nid, app_name, icon, summary, body, actions, hints, timeout):
        self.id = nid
        self.app_name = app_name
        self.icon = icon
        self.summary = summary
        self.body = body
        self.actions = list(zip(actions[0::2], actions[1::2]))
        self.hints = hints
        self.timeout = timeout
        self.time = time.time()
        self.urgency = hints.get("urgency", 1) if isinstance(hints.get("urgency"), int) else 1
        self.desktop_entry = hints.get("desktop-entry", "")

    def gicon(self):
        if self.icon:
            if self.icon.startswith("file://"):
                return Gio.FileIcon.new(Gio.File.new_for_uri(self.icon))
            if self.icon.startswith("/"):
                return Gio.FileIcon.new(Gio.File.new_for_path(self.icon))
            return Gio.ThemedIcon.new(self.icon)
        app = apps.app_by_id(self.desktop_entry + ".desktop") if self.desktop_entry else None
        if app and app.get_icon():
            return app.get_icon()
        return Gio.ThemedIcon.new("dialog-information-symbolic")


class Card(Gtk.Box):
    def __init__(self, server, note, in_history=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                         css_classes=["notification"])
        if note.urgency == URGENCY_CRITICAL:
            self.add_css_class("critical")
        self.note = note
        head = Gtk.Box(spacing=10)
        head.append(Gtk.Image(gicon=note.gicon(), pixel_size=32, valign=Gtk.Align.START))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, spacing=2)
        top = Gtk.Box(spacing=6)
        top.append(Gtk.Label(label=note.summary, xalign=0, hexpand=True, wrap=True,
                             wrap_mode=Pango.WrapMode.WORD_CHAR, css_classes=["heading"]))
        if in_history:
            stamp = GLib.DateTime.new_from_unix_local(int(note.time)).format("%H:%M")
            top.append(Gtk.Label(label=stamp, css_classes=["dim-label", "caption"]))
        text.append(top)
        if note.body:
            body = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                             lines=4 if not in_history else 2, ellipsize=Pango.EllipsizeMode.END,
                             css_classes=["notification-body"])
            body.set_markup(sanitize_markup(note.body))
            text.append(body)
        if note.app_name:
            text.append(Gtk.Label(label=note.app_name, xalign=0,
                                  css_classes=["dim-label", "caption"]))
        head.append(text)
        close = Gtk.Button(icon_name="window-close-symbolic", valign=Gtk.Align.START,
                           css_classes=["flat", "circular", "notification-close"])
        close.connect("clicked", lambda *_: server.dismiss(note.id, from_history=in_history))
        head.append(close)
        self.append(head)

        code = verification_code(note.summary, note.body)
        if code:
            copy = Gtk.Button(css_classes=["notification-code", "pill"],
                              halign=Gtk.Align.START)
            copy.set_child(Gtk.Label(label=_("Copy {code}").format(code=code)))
            copy.connect("clicked", lambda b, c=code: self._copy_code(b, c))
            self.append(copy)

        buttons = [(k, lbl) for k, lbl in note.actions if k != "default"]
        if buttons and not in_history:
            row = Gtk.Box(spacing=6, homogeneous=True)
            for key, label in buttons:
                b = Gtk.Button(label=label)
                b.connect("clicked", lambda _b, k=key: server.invoke(note.id, k))
                row.append(b)
            self.append(row)

        click = Gtk.GestureClick()
        def open_card(_gesture, _n, x, y):
            target = self.pick(x, y, Gtk.PickFlags.DEFAULT)
            if target is not None and (isinstance(target, Gtk.Button) or
                                       target.get_ancestor(Gtk.Button) is not None):
                return
            server.invoke(note.id, "default")
        click.connect("released", open_card)
        self.add_controller(click)


    @staticmethod
    def _copy_code(button, code):
        Gdk.Display.get_default().get_clipboard().set(code)
        button.get_child().set_label(_("Copied ✓"))
        button.add_css_class("copied")

class Popups(LayerWindow):
    def __init__(self, shell):
        super().__init__(shell, "aurora-notifications", layer=Layer.OVERLAY,
                         anchors=("top", "right"), margins={"top": 8, "right": 8})
        self.add_css_class("aurora-notifications")
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.box.set_size_request(380, -1)
        self.set_child(self.box)

    def sync(self):
        self.set_visible(self.box.get_first_child() is not None)


class NotificationServer:
    def __init__(self, shell):
        self.shell = shell
        self._next_id = 1
        self._live = {}        # id -> (Notification, Card, timeout source)
        self.history = []
        self._conn = None
        self.popups = Popups(shell)
        self._history_box = None
        node = Gio.DBusNodeInfo.new_for_xml(IFACE_XML)
        self._iface = node.interfaces[0]
        Gio.bus_own_name(Gio.BusType.SESSION, "org.freedesktop.Notifications",
                         Gio.BusNameOwnerFlags.REPLACE | Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT,
                         self._on_bus, None, self._on_lost)

    # --- D-Bus ---

    def _on_bus(self, conn, _name):
        self._conn = conn
        conn.register_object("/org/freedesktop/Notifications", self._iface,
                             self._on_call, None, None)

    def _on_lost(self, _conn, _name):
        print("aurora: could not own org.freedesktop.Notifications")

    def _on_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method == "GetCapabilities":
            invocation.return_value(GLib.Variant(
                "(as)", (["body", "body-markup", "actions", "icon-static", "persistence"],)))
        elif method == "GetServerInformation":
            invocation.return_value(GLib.Variant(
                "(ssss)", ("Aurora Shell", "Aurora OS", VERSION, "1.2")))
        elif method == "CloseNotification":
            self.close(params.unpack()[0], REASON_CLOSED)
            invocation.return_value(None)
        elif method == "Notify":
            nid = self.notify(*params.unpack())
            invocation.return_value(GLib.Variant("(u)", (nid,)))

    def _emit(self, signal, variant):
        if self._conn is not None:
            self._conn.emit_signal(None, "/org/freedesktop/Notifications",
                                   "org.freedesktop.Notifications", signal, variant)

    # --- model ---

    def notify(self, app_name, replaces_id, icon, summary, body, actions, hints, timeout):
        if replaces_id and replaces_id in self._live:
            nid = replaces_id
            self._remove_popup(nid)
        else:
            nid = self._next_id
            self._next_id += 1
        note = Notification(nid, app_name, icon, summary, body, actions, hints, timeout)
        s = settings.get()
        # Remember who sends notifications, so Settings can list them; muted apps
        # are dropped (critical ones still come through).
        if s is not None and app_name:
            seen = list(s.get_strv("notifications-seen-apps"))
            if app_name not in seen:
                s.set_strv("notifications-seen-apps", (seen + [app_name])[-60:])
            if app_name in s.get_strv("notifications-muted-apps") and \
                    note.urgency != URGENCY_CRITICAL:
                return nid
        self.history = [n for n in self.history if n.id != nid]
        if not hints.get("transient"):
            self.history.insert(0, note)
            del self.history[HISTORY_LIMIT:]
            self._refresh_history()

        dnd = s is not None and s.get_boolean("do-not-disturb")
        if dnd and note.urgency != URGENCY_CRITICAL:
            return nid

        card = Card(self, note)
        self.popups.box.prepend(card)
        source = 0
        if note.urgency != URGENCY_CRITICAL and timeout != 0:
            ms = DEFAULT_TIMEOUT_MS if timeout < 0 else timeout
            source = GLib.timeout_add(ms, self._expire, nid)
        self._live[nid] = (note, card, source)
        self.popups.sync()
        return nid

    def _expire(self, nid):
        entry = self._live.get(nid)
        if entry:
            self._live[nid] = (entry[0], entry[1], 0)
        self._remove_popup(nid)
        self._emit("NotificationClosed", GLib.Variant("(uu)", (nid, REASON_EXPIRED)))
        return GLib.SOURCE_REMOVE

    def _remove_popup(self, nid):
        entry = self._live.pop(nid, None)
        if entry is None:
            return
        _note, card, source = entry
        if source:
            GLib.source_remove(source)
        self.popups.box.remove(card)
        self.popups.sync()

    def close(self, nid, reason):
        self._remove_popup(nid)
        self._emit("NotificationClosed", GLib.Variant("(uu)", (nid, reason)))

    def dismiss(self, nid, from_history=False):
        if from_history:
            self.history = [n for n in self.history if n.id != nid]
            self._refresh_history()
        self.close(nid, REASON_DISMISSED)

    def invoke(self, nid, key):
        note = next((n for n in self.history if n.id == nid), None) or \
            (self._live[nid][0] if nid in self._live else None)
        if note is None:
            return
        has_default = any(k == "default" for k, _l in note.actions)
        if key == "default" and (not has_default or nid not in self._live):
            # A closed notification's D-Bus action may no longer have a
            # listener. Focus or launch its declared sender instead.
            app_id = note.desktop_entry.removesuffix(".desktop")
            windows = self.shell.toplevels.for_app(app_id) if app_id else []
            if windows:
                windows[0].activate()
            else:
                app = apps.find_app(app_id) if app_id else apps.find_app(note.app_name)
                if app is not None:
                    apps.launch(app)
        else:
            self._emit("ActionInvoked", GLib.Variant("(us)", (nid, key)))
            # Notifications the shell sent itself handle their actions here.
            if getattr(self.shell, "sysnotify", None) is not None:
                self.shell.sysnotify.invoke(nid, key)
        if not note.hints.get("resident"):
            self.close(nid, REASON_DISMISSED)

    # --- history UI (lives in the clock popover) ---

    def history_widget(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                        css_classes=["notification-history"])
        outer.set_size_request(360, -1)
        header = Gtk.Box()
        header.append(Gtk.Label(label=_("Notifications"), xalign=0, hexpand=True,
                                css_classes=["heading"]))
        self._summarize_btn = Gtk.Button(label=_("Summarize"), css_classes=["flat", "pill"],
                                         tooltip_text=_("Aurora AI summarizes your notifications"))
        self._summarize_btn.connect("clicked", lambda *_: self.summarize())
        header.append(self._summarize_btn)
        outer.append(header)
        self._history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroller = Gtk.ScrolledWindow(child=self._history_box, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      min_content_height=300)
        outer.append(scroller)

        # Like Ubuntu: Do Not Disturb and Clear under the list.
        bottom = Gtk.Box(spacing=8)
        bottom.append(Gtk.Label(label=_("Do Not Disturb"), xalign=0))
        dnd = Gtk.Switch(valign=Gtk.Align.CENTER)
        s = settings.get()
        if s:
            s.bind("do-not-disturb", dnd, "active", 0)
        bottom.append(dnd)
        bottom.append(Gtk.Box(hexpand=True))
        clear = Gtk.Button(label=_("Clear"), css_classes=["pill"])
        clear.connect("clicked", lambda *_: self.clear_history())
        bottom.append(clear)
        outer.append(bottom)
        self._refresh_history()
        return outer

    def summarize(self):
        lines = [f"- {n.app_name}: {n.summary} — {re.sub(r'<[^>]+>', '', n.body)[:200]}"
                 for n in self.history[:30]]
        apps.spawn(["aurora-assistant", "--ask",
                    "Summarize these notifications in a few short bullets, most important "
                    "first, and say if anything needs action:\n" + "\n".join(lines)])

    def clear_history(self):
        self.history = []
        self._refresh_history()

    def _refresh_history(self):
        box = self._history_box
        if box is None:
            return
        from aurora import ai
        self._summarize_btn.set_visible(ai.feature("notifications") and len(self.history) >= 3)
        while (c := box.get_first_child()) is not None:
            box.remove(c)
        if not self.history:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                            valign=Gtk.Align.CENTER, vexpand=True, margin_top=60)
            empty.append(Gtk.Image(icon_name="notifications-disabled-symbolic",
                                   pixel_size=48, css_classes=["dim-label"]))
            empty.append(Gtk.Label(label=_("No Notifications"), css_classes=["dim-label"]))
            box.append(empty)
            return
        for note in self.history:
            box.append(Card(self, note, in_history=True))
