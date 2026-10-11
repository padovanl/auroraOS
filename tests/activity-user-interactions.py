"""GTK activity-center usability and responsive user authorization."""
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib, Gtk
from aurora import activities
from aurora.settingsapp import system
from aurora.shell.panel import ActivityCenter


def wait(predicate):
    end = time.monotonic() + 5
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('GTK did not settle')


def children(widget):
    child = widget.get_first_child()
    while child:
        yield child
        yield from children(child)
        child = child.get_next_sibling()


Adw.init()
app = Adw.Application(application_id='org.aurora.ActivityAudit')
app.register(None)
window = Adw.ApplicationWindow(application=app)
with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, XDG_RUNTIME_DIR=directory):
    active = activities.create('Visible long transfer', 'copy')
    for n in range(12):
        ident = activities.create(f'Completed {n}', 'copy')
        activities.update(ident, status='finished')
    center = ActivityCenter()
    window.set_content(center)
    window.present()
    center.refresh()
    labels = [w.get_label() for w in children(center.rows) if isinstance(w, Gtk.Label)]
    assert 'Visible long transfer' in labels and 'Completed 0' in labels
    cancel = next(w for w in children(center.rows) if isinstance(w, Gtk.Button)
                  and w.get_icon_name() == 'process-stop-symbolic')
    cancel.emit('clicked')
    assert activities.cancelled(active)
    assert any(isinstance(w, Gtk.Label) and w.get_label() == 'Cancelling…'
               for w in children(center.rows))
    clear = next(w for w in children(center.rows) if isinstance(w, Gtk.Button)
                 and w.get_label() == 'Clear completed')
    clear.emit('clicked')
    assert [i['id'] for i in activities.list_recent()] == [active]
    activities.update(active, status='cancelled')
    activities.clear_finished()
    center.refresh()
    assert center.get_visible()
    assert any(isinstance(w, Gtk.Label) and w.get_label() == 'No recent activities'
               for w in children(center.rows))

page = system.Users()
window.set_content(page)
messages, calls = [], []
release = threading.Event()
def authorize(*args, **kwargs):
    calls.append(threading.get_ident())
    assert release.wait(5)
    return False, 'Authorization was cancelled'
with patch.object(system, 'admin', authorize), patch.object(system, 'toast', lambda _p, msg: messages.append(msg)):
    page._account_action(('add-user', 'audit-user', 'Audit User', 'no'), 'User added', 'password\n')
    wait(lambda: bool(calls))
    assert calls[0] != threading.get_ident() and not page.get_sensitive()
    heartbeat = []
    GLib.idle_add(lambda: heartbeat.append(True) and False)
    wait(lambda: bool(heartbeat))
    release.set()
    wait(lambda: page.get_sensitive())
    assert messages == ['Authorization was cancelled']

page._add_user_dialog()
dialog = window.get_visible_dialog()
rows = [w for w in children(dialog.get_extra_child()) if isinstance(w, Adw.EntryRow)]
full, username = rows[:2]
full.set_text('Alice Smith')
assert username.get_text() == 'alice'
username.set_text('my-login')
full.set_text('Alice Jones')
assert username.get_text() == 'my-login'
dialog.close()
window.close()
print('PASS: complete activity history, cancel feedback, clear and responsive user actions')
