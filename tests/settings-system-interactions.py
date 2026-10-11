"""Real GTK and two wlroots outputs: authorization, locking and display rollback."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from unittest.mock import patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402
from aurora.settingsapp import display, system  # noqa: E402

Adw.init()


def wait(predicate, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("Timed out waiting for GTK state")


def children(widget):
    child = widget.get_first_child()
    while child:
        yield child
        yield from children(child)
        child = child.get_next_sibling()


app = Adw.Application(application_id="org.aurora.SettingsAudit")
app.register(None)
window = Adw.ApplicationWindow(application=app, default_width=980, default_height=680)
messages, calls = [], []
released = threading.Event()


def admin(*args):
    calls.append(args)
    assert released.wait(5)
    return False, "Authorization was cancelled"


with patch.object(system, "admin", admin), patch.object(system, "toast",
                                                        lambda *args: messages.append(args[-1])):
    page = system.Privacy()
    window.set_content(page)
    window.present()
    row = page.firewall_row
    old = row.get_active()
    row.set_active(not old)
    wait(lambda: bool(calls))
    assert not row.get_sensitive()
    heartbeats = []
    GLib.idle_add(lambda: heartbeats.append(True) and False)
    wait(lambda: bool(heartbeats))
    system.admin_toggle(page, row, "firewall", not old, "done")
    assert len(calls) == 1
    released.set()
    wait(lambda: row.get_sensitive())
    assert row.get_active() == old and len(calls) == 1
    assert messages == ["Authorization was cancelled"]
    lock = next(w for w in children(page) if isinstance(w, Adw.ButtonRow)
                and w.get_title() == system._("Lock now"))
    with patch.object(system.apps, "spawn") as spawn:
        lock.emit("activated")
        spawn.assert_called_once_with(["aurora-lock"])
    successful = []
    with patch.object(system, "admin", lambda *args: (True, "")):
        system.admin_toggle(page, row, "firewall", old, "done",
                            lambda: successful.append(True))
        wait(lambda: row.get_sensitive())
        assert successful == [True]

print("ok: authorization remains responsive, cancellation restores state, lock is actionable", flush=True)

original = next(o for o in display.outputs() if o["name"] == "HEADLESS-2")
original_position = original["position"]
path = Path(os.environ["HOME"]) / ".config/aurora/displays.sh"
old_file = path.read_text() if path.exists() else None


def position():
    return next(o["position"] for o in display.outputs() if o["name"] == "HEADLESS-2")


try:
    page = display.Displays()
    window.set_content(page)
    wait(lambda: page.get_mapped())
    x, y, move = page.position_controls["HEADLESS-2"]
    x.set_value(1600)
    y.set_value(120)
    move.emit("clicked")
    wait(lambda: window.get_visible_dialog() is not None)
    assert position() == {"x": 1600, "y": 120}
    dialog = window.get_visible_dialog()
    dialog.set_close_response("keep")
    dialog.close()
    wait(lambda: window.get_visible_dialog() is None)
    assert "--pos 1600,120" in path.read_text()
    page.refresh()
    x, y, move = page.position_controls["HEADLESS-2"]
    assert (x.get_value_as_int(), y.get_value_as_int()) == (1600, 120)
    x.set_value(1700)
    move.emit("clicked")
    wait(lambda: window.get_visible_dialog() is not None)
    window.get_visible_dialog().close()
    wait(lambda: position() == {"x": 1600, "y": 120})
    wait(lambda: window.get_visible_dialog() is None)
    with patch.object(display, "KEEP_SECONDS", 1):
        x, y, move = page.position_controls["HEADLESS-2"]
        x.set_value(1800)
        move.emit("clicked")
        wait(lambda: position() == {"x": 1800, "y": 120})
        wait(lambda: position() == {"x": 1600, "y": 120})
        wait(lambda: window.get_visible_dialog() is None)
    assert "--pos 1600,120" in path.read_text() and "1800" not in path.read_text()
    subprocess.run(["grim", "/out/displays.png"], check=True)
    print("ok: two displays move, persist, revert and time out correctly", flush=True)
finally:
    subprocess.run(["wlr-randr", "--output", "HEADLESS-2", "--pos",
                    f"{original_position['x']},{original_position['y']}"], check=True)
    if old_file is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(old_file)
    window.close()
    wait(lambda: not window.get_visible())
