"""Real GTK regression for batch rename path confinement."""
import tempfile
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib, Gtk, Gio
from aurora.files.app import FilesApp


def wait(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError('GTK state did not settle')


app = FilesApp()
app.register(None)
with tempfile.TemporaryDirectory(prefix='aurora-rename-audit-') as directory:
    root = Path(directory)
    source, outside = root / 'source', root / 'outside'
    source.mkdir(); outside.mkdir()
    for name in ('xa.md', 'xb.md'):
        (source / name).write_text(name)
    win = app.open_window(Gio.File.new_for_path(str(source)))
    wait(lambda: not win.dirlist.is_loading() and win.model.get_n_items() == 2)
    win.selection.select_all()
    win.batch_rename()
    dialog = win.get_visible_dialog()
    find = dialog.get_extra_child().get_first_child()
    replace = find.get_next_sibling()
    find.set_text('x'); replace.set_text('../outside/')
    dialog.emit('response', 'rename')
    assert all((source / name).exists() for name in ('xa.md', 'xb.md'))
    assert not list(outside.iterdir()), 'Batch rename moved files outside their folder'
    dialog.close()
    wait(lambda: win.get_visible_dialog() is None)
    win.batch_rename()
    dialog = win.get_visible_dialog()
    find = dialog.get_extra_child().get_first_child()
    replace = find.get_next_sibling()
    find.set_text('x'); replace.set_text('new-')
    dialog.emit('response', 'rename')
    wait(lambda: all((source / name).exists() for name in ('new-a.md', 'new-b.md')))
    win.undo()
    wait(lambda: all((source / name).exists() for name in ('xa.md', 'xb.md')) and not win._history_busy)
    win.redo()
    wait(lambda: all((source / name).exists() for name in ('new-a.md', 'new-b.md')) and not win._history_busy)
    dialog.close(); win.close()
print('PASS: batch rename confines names to their folder and supports Undo/Redo', flush=True)
