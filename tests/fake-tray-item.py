#!/usr/bin/env python3
"""A minimal StatusNotifierItem with a dbusmenu, for the smoke test."""
from gi.repository import Gio, GLib

XML = """<node>
<interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/>
  <property name="IconName" type="s" access="read"/><property name="Menu" type="o" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
</interface>
<interface name="com.canonical.dbusmenu">
  <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/>
    <arg type="as" direction="in"/><arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
  <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
  <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/>
    <arg type="v" direction="in"/><arg type="u" direction="in"/></method>
</interface></node>"""
PROPS = {"Category": GLib.Variant("s", "ApplicationStatus"), "Id": GLib.Variant("s", "fake"),
         "Title": GLib.Variant("s", "Fake Tray App"), "Status": GLib.Variant("s", "Active"),
         "IconName": GLib.Variant("s", "applications-games"),
         "Menu": GLib.Variant("o", "/MenuBar"), "ItemIsMenu": GLib.Variant("b", False)}


def call(conn, sender, path, iface, method, params, inv):
    if method == "GetLayout":
        item = GLib.Variant("(ia{sv}av)", (1, {"label": GLib.Variant("s", "_Quit")}, []))
        inv.return_value(GLib.Variant("(u(ia{sv}av))", (1, (0, {}, [item]))))
    elif method == "AboutToShow":
        inv.return_value(GLib.Variant("(b)", (False,)))
    else:
        inv.return_value(None)


def acquired(conn, name):
    node = Gio.DBusNodeInfo.new_for_xml(XML)
    conn.register_object("/StatusNotifierItem", node.interfaces[0], call,
                         lambda *a: PROPS.get(a[4]), None)
    conn.register_object("/MenuBar", node.interfaces[1], call, None, None)
    conn.call_sync("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                   "org.kde.StatusNotifierWatcher", "RegisterStatusNotifierItem",
                   GLib.Variant("(s)", (name,)), None, Gio.DBusCallFlags.NONE, -1, None)
    print("registered")


Gio.bus_own_name(Gio.BusType.SESSION, "org.kde.StatusNotifierItem-4242-1",
                 Gio.BusNameOwnerFlags.NONE, acquired, None, None)
GLib.timeout_add_seconds(30, lambda: loop.quit())
loop = GLib.MainLoop()
loop.run()
