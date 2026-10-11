"""Real GTK checks for favorites, file clipboard and responsive clock/power settings."""
import tempfile
import gc
import threading
import time
from pathlib import Path
from unittest.mock import patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from aurora.files import bookmarks, clipboard
from aurora.files.app import FilesApp
from aurora.settingsapp import power, system, timedate

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


def pause():
    deadline = time.monotonic() + .25
    wait(lambda: time.monotonic() >= deadline)


def children(widget):
    child = widget.get_first_child()
    while child:
        yield child
        yield from children(child)
        child = child.get_next_sibling()


app = FilesApp()
app.register(None)
with tempfile.TemporaryDirectory(prefix="aurora-daily-") as directory:
    root = Path(directory)
    source, target = root / "source", root / "target"
    source.mkdir()
    target.mkdir()
    (source / "a.txt").write_text("A")
    (source / "b.txt").write_text("B")
    win = app.open_window(Gio.File.new_for_path(str(source)))
    other = app.open_window(Gio.File.new_for_path(str(target)))
    wait(lambda: not win.dirlist.is_loading() and not other.dirlist.is_loading()
         and win.sidebar.get_realized())
    location = Gio.File.new_for_path(str(source))

    def favorite(window):
        return next((row for row in children(window.sidebar)
                     if isinstance(row, Gtk.ListBoxRow) and getattr(row, "bookmark", False)
                     and row.file.equal(location)), None)
    win.add_to_sidebar()
    wait(lambda: favorite(win) is not None and favorite(other) is not None)
    win.sidebar._bookmark_change("rename", location, "Daily Projects")
    wait(lambda: favorite(other).place_label == "Daily Projects")
    assert bookmarks.read()[-1][1] == "Daily Projects"
    other.sidebar._bookmark_change("remove", location)
    wait(lambda: favorite(win) is None and favorite(other) is None)
    print("ok: add, rename and remove favorites updates both windows", flush=True)

    def select(name):
        wait(lambda: any(win.model.get_item(i).get_name() == name
                         for i in range(win.model.get_n_items())))
        index = next(i for i in range(win.model.get_n_items()) if win.model.get_item(i).get_name() == name)
        win.selection.select_item(index, True)

    clip = win.get_clipboard()
    select("a.txt")
    win.to_clipboard("copy")
    assert clip.get_formats().contain_mime_type(clipboard.MIME)
    clip.set("new text from another application")
    other.paste()
    pause()
    assert not other.jobs and not list(target.iterdir())
    clip.set(Gdk.FileList.new_from_list([Gio.File.new_for_path(str(source / "b.txt"))]))
    other.paste()
    wait(lambda: (target / "b.txt").exists() and not other.jobs)
    assert (target / "b.txt").read_text() == "B" and not (target / "a.txt").exists()
    print("ok: replaced clipboard cannot paste stale files; external file list is copied", flush=True)

    # Read the MIME stream, bypassing our local ownership cache, as when a
    # different file manager supplied GNOME's interoperable cut format.
    payload = "cut\n" + (source / "a.txt").as_uri() + "\n"
    clip.set_content(Gdk.ContentProvider.new_for_bytes(clipboard.MIME, GLib.Bytes.new(payload.encode())))
    other.paste()
    wait(lambda: (target / "a.txt").exists() and not (source / "a.txt").exists() and not other.jobs)
    print("ok: GNOME cut clipboard moves files with actual asynchronous MIME reads", flush=True)

    select("b.txt")
    win.to_clipboard("move")
    absent = root / "not-created-yet"
    absent.mkdir()
    other.open_location(Gio.File.new_for_path(str(absent)))
    absent.rmdir()
    other.paste()
    wait(lambda: not other.jobs and not clipboard.STATE["pending"])
    assert clipboard.owned(clip) and (source / "b.txt").exists()
    absent.mkdir()
    other._retry_job()
    wait(lambda: (absent / "b.txt").exists() and not other.jobs)
    assert not (source / "b.txt").exists() and not clipboard.owned(clip)
    print("ok: failed cut remains available; Retry finishes the move and clears its clipboard", flush=True)

    for index in range(2):
        (source / f"drag-{index}.txt").write_text(str(index))
    win.open_location(Gio.File.new_for_path(str(source)))
    wait(lambda: not win.dirlist.is_loading() and win.model.get_n_items() >= 2)
    for use_list in (False, True):
        win.set_list_view(use_list)
        pause()
        drags = []
        for widget in (win.view_stack, *children(win.view_stack)):
            controllers = widget.observe_controllers()
            drags += [controllers.get_item(i) for i in range(controllers.get_n_items())
                      if isinstance(controllers.get_item(i), Gtk.DragSource)]
        assert drags
        assert all(drag.get_actions() & Gdk.DragAction.COPY and
                   drag.get_actions() & Gdk.DragAction.MOVE for drag in drags)
        gc.collect()
        tile, item = next((widget, item) for widget, item in win._item_rows.items()
                          if widget.get_mapped() and item.get_item() is not None
                          and item.get_item().get_name() == "drag-0.txt")
        x, y = tile.translate_coordinates(win.view_stack,
                                           tile.get_width()/2, tile.get_height()/2)[-2:]
        assert win._item_position(win.view_stack, x, y) == item.get_position()
        assert drags[0].emit("prepare", x, y) is not None
        win._on_context_click(None, 1, x, y, win.view_stack)
        labels = {widget.get_label() for widget in children(win.context_menu)
                  if isinstance(widget, Gtk.Button)}
        assert {"Copy", "Cut"}.issubset(labels)
        win.context_menu.popdown()
        pause()
    files = Gdk.FileList.new_from_list([Gio.File.new_for_path(str(source / f"drag-{i}.txt")) for i in range(2)])
    assert other._drop_on_location(files, Gio.File.new_for_path(str(target)))
    wait(lambda: all((target / f"drag-{i}.txt").exists() for i in range(2)) and not other.jobs)
    assert all((source / f"drag-{i}.txt").exists() for i in range(2))
    print("ok: grid/list offer copy and move; multi-file drop preserves copied sources", flush=True)
    crumb = other.pathbar.get_last_child()
    controllers = crumb.observe_controllers()
    drop = next(controllers.get_item(i) for i in range(controllers.get_n_items())
                if isinstance(controllers.get_item(i), Gtk.DropTarget))
    assert drop.emit("drop", files, 0, 0)
    wait(lambda: all((absent / f"drag-{i}.txt").exists() for i in range(2)) and not other.jobs)
    print("ok: breadcrumb drop target copies a multiple-file selection", flush=True)

    # Delayed network callbacks must not block GTK or pull the user back to a
    # stale location after they navigate elsewhere.
    class Remote:
        def __init__(self):
            self.callback = None
            self.cancel = None
        def get_path(self):
            return None
        def is_native(self):
            return False
        def query_info_async(self, attrs, flags, priority, cancel, callback):
            self.cancel, self.callback = cancel, callback
        def query_info_finish(self, result):
            pytest_fail = "stale navigation completed"
            raise AssertionError(pytest_fail)
    remote = Remote()
    win.open_location(remote)
    assert remote.callback is not None and not remote.cancel.is_cancelled()
    heartbeats = []
    GLib.idle_add(lambda: heartbeats.append(True) and False)
    wait(lambda: bool(heartbeats))
    win.open_location(Gio.File.new_for_path(str(source)))
    assert remote.cancel.is_cancelled()
    remote.callback(remote, None)
    assert win.current.get_path() == str(source)
    print("ok: delayed network navigation stays responsive and cannot replace a newer location", flush=True)
    errors = []
    with patch.object(other.history, "undo", side_effect=GLib.Error.new_literal(
            Gio.io_error_quark(), "Cannot restore missing trash item", Gio.IOErrorEnum.NOT_FOUND)), \
            patch.object(other, "toast", lambda error: errors.append(error)):
        other.undo()
        wait(lambda: not other._history_busy)
    assert errors and "Cannot restore" in errors[-1]
    assert other._action("undo").get_enabled()
    print("ok: failed GIO undo clears its busy state and reports the restore error", flush=True)
    win.close()
    other.close()
    pause()
    assert not win.sidebar._volume_handlers and win.sidebar._bookmark_monitor is None
    print("ok: closing Files disconnects sidebar monitors", flush=True)

window = Adw.ApplicationWindow(application=app, default_width=850, default_height=700)
calls, released = [], threading.Event()


def fake_time(argv, check=False, timeout=10):
    if argv == ["timedatectl", "show"]:
        return "NTP=yes\nTimezone=UTC\n"
    if argv == ["timedatectl", "list-timezones"]:
        return "UTC\nEurope/Rome\n"
    calls.append(argv)
    assert timeout == 300
    assert released.wait(5)
    raise RuntimeError("Authorization was cancelled")


with patch.object(timedate, "run", fake_time):
    page = timedate.DateTime()
    window.set_content(page)
    window.present()
    wait(lambda: page.get_realized())
    page.ntp_row.set_active(False)
    wait(lambda: bool(calls))
    assert not page.get_sensitive()
    heartbeats = []
    GLib.idle_add(lambda: heartbeats.append(True) and False)
    wait(lambda: bool(heartbeats))
    released.set()
    wait(lambda: page.get_sensitive())
    assert page.ntp_row.get_active() and not page.manual_group.get_sensitive() and len(calls) == 1
    calls.clear()
    released.clear()
    page.zone_row.set_selected(1)
    wait(lambda: bool(calls))
    released.set()
    wait(lambda: page.get_sensitive())
    assert page.zone_row.get_selected() == 0 and len(calls) == 1
    print("ok: time authorization stays responsive; cancelled NTP/timezone restores selection", flush=True)

with patch.object(timedate, "run", lambda argv, **kwargs: calls.append(argv) or ""):
    page.ntp_row.set_active(False)
    wait(lambda: page.get_sensitive())
    assert page.manual_group.get_sensitive() and not page._ntp
    page.calendar.select_day(GLib.DateTime.new_local(2026, 10, 11, 0, 0, 0))
    page.hour.set_value(14)
    page.minute.set_value(37)
    page.apply_button.emit("activated")
    wait(lambda: page.get_sensitive())
    assert calls[-1] == ["timedatectl", "set-time", "2026-10-11 14:37:00"]
    print("ok: manual calendar, hour and minute apply the chosen local date/time", flush=True)
window.set_content(None)
pause()
assert page._clock_source == 0

calls.clear()
released.clear()


def admin(*args):
    calls.append(args)
    assert released.wait(5)
    return False, "Authorization was cancelled"


with patch.object(system, "admin", admin), patch.object(power.Power, "_battery", lambda self: "50%"), \
        patch.object(power.Power, "_health", lambda self: None), \
        patch.object(power, "charge_limit_supported", lambda: True), \
        patch.object(power, "charge_limit_on", lambda: False), \
        patch.object(power, "has_lid", lambda: True), \
        patch.object(power, "logind_value", lambda key, default: default):
    page = power.Power()
    window.set_content(page)
    for row, change, old_value in (
        (page.power_row, lambda: page.power_row.set_selected(1), 0),
        (page.lid_row, lambda: page.lid_row.set_selected(1), 0),
        (page.limit_row, lambda: page.limit_row.set_active(True), False),
    ):
        released.clear()
        count = len(calls)
        change()
        wait(lambda: len(calls) > count)
        assert not row.get_sensitive()
        heartbeats = []
        GLib.idle_add(lambda: heartbeats.append(True) and False)
        wait(lambda: bool(heartbeats))
        released.set()
        wait(lambda: row.get_sensitive())
        value = row.get_active() if isinstance(row, Adw.SwitchRow) else row.get_selected()
        assert value == old_value and len(calls) == count + 1
    print("ok: cancelled power-button, lid and charge-limit changes restore state without freezing", flush=True)
window.close()
pause()
print("ALL DAILY INTERACTION CHECKS PASSED", flush=True)
