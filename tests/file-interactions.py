"""Real GTK layout checks for empty-space clicks and new-file dialogs."""
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from aurora.files.app import FilesApp
from aurora.files.create import NewItemDialog
from aurora.shell import desktopicons
from aurora.shell.wallpaper import Wallpaper


def settle(predicate=lambda: True):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            time.sleep(.1)
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            return
        time.sleep(.05)
    raise AssertionError("GTK did not reach the expected state")


app = FilesApp()
app.register(None)
with tempfile.TemporaryDirectory(prefix="aurora-files-check-") as directory:
    root = Path(directory)
    (root / "existing.txt").write_text("keep this")
    win = app.open_window(Gio.File.new_for_path(directory))
    settle(lambda: not win.dirlist.is_loading() and win.view_stack.get_height() > 100)
    for list_view in (False, True):
        win.set_list_view(list_view)
        settle()
        win.selection.select_item(0, True)
        x, y = win.view_stack.get_width() / 2, win.view_stack.get_height() - 30
        assert win._item_position(win.view_stack, x, y) is None
        controllers = win.view_stack.observe_controllers()
        primary = next(controllers.get_item(i) for i in range(controllers.get_n_items())
                       if isinstance(controllers.get_item(i), Gtk.GestureClick)
                       and controllers.get_item(i).get_button() == Gdk.BUTTON_PRIMARY)
        primary.emit("pressed", 1, x, y)
        assert win.selection.get_selection().is_empty(), "empty click did not deselect"
        print(f"ok: empty-space deselection in {'list' if list_view else 'grid'}")

    win.new_file()
    dialog = next(w for w in app.get_windows() if isinstance(w, NewItemDialog))
    dialog.entry.set_text("existing.txt")
    dialog._create()
    assert (root / "existing.txt").read_text() == "keep this"
    assert dialog.error.get_visible(), "duplicate name must show an error"
    dialog.entry.set_text("../invalid")
    assert not dialog.create_button.get_sensitive()
    dialog.entry.set_text("new.txt")
    dialog._create()
    assert (root / "new.txt").read_bytes() == b""
    assert win._action("undo").get_enabled()
    win.undo()
    settle(lambda: not (root / "new.txt").exists() and win._action("redo").get_enabled())
    win.redo()
    settle(lambda: (root / "new.txt").exists() and win._action("undo").get_enabled())
    print("ok: new-file undo/redo")
    print("ok: new file, invalid name and overwrite protection")

    settle(lambda: any(win.model.get_item(i).get_name() == "new.txt"
                       for i in range(win.model.get_n_items())))
    index = next(i for i in range(win.model.get_n_items())
                 if win.model.get_item(i).get_name() == "new.txt")
    win.selection.select_item(index, True)
    win._action("duplicate").activate(None)
    settle(lambda: (root / "new (2).txt").exists())
    assert (root / "new.txt").exists()
    print("ok: Duplicate action creates a second file without overwriting")

    desktopicons.desktop_dir = lambda: str(root / "Desktop")
    Wallpaper._new_item(SimpleNamespace(app=app), None, None)
    dialog = next(w for w in app.get_windows() if isinstance(w, NewItemDialog))
    dialog.entry.set_text("desktop.txt")
    dialog._create()
    assert (root / "Desktop/desktop.txt").is_file()
    print("ok: desktop new-file callback")
    Wallpaper._new_item(SimpleNamespace(app=app), None, None, True)
    dialog = next(w for w in app.get_windows() if isinstance(w, NewItemDialog))
    dialog.entry.set_text("New folder")
    dialog._create()
    assert (root / "Desktop/New folder").is_dir()
    print("ok: desktop new-folder callback")

    win.new_tab(Gio.File.new_for_path(str(root / "Desktop")))
    settle(lambda: win.current.get_path() == str(root / "Desktop"))
    win.open_location(Gio.File.new_for_path(str(root)))
    assert len(win.back_stack) == 1
    win.switch_tab(0)
    assert win.current.get_path() == str(root) and not win.back_stack
    win.switch_tab(1)
    assert win.current.get_path() == str(root) and len(win.back_stack) == 1
    win.go_back()
    assert win.current.get_path() == str(root / "Desktop")
    win.close_tab(1)
    assert len(win.tabs) == 1 and win.current.get_path() == str(root)
    print("ok: tabs preserve locations and navigation history")

    empty = root / "empty"
    empty.mkdir()
    win.open_location(Gio.File.new_for_path(str(empty)))
    settle(lambda: not win.dirlist.is_loading() and win.view_stack.get_visible_child_name() == "empty")
    files = Gdk.FileList.new_from_list([Gio.File.new_for_path(str(root / "existing.txt"))])
    assert win._drop_on_location(files, Gio.File.new_for_path(str(empty)))
    settle(lambda: (empty / "existing.txt").exists())
    win.undo()
    settle(lambda: not (empty / "existing.txt").exists() and win._action("redo").get_enabled())
    win.redo()
    settle(lambda: (empty / "existing.txt").exists() and win._action("undo").get_enabled())
    print("ok: dropped file copy and undo/redo")
    win._on_context_click(None, 1, 100, 100, win.view_stack)
    menu = win.context_menu.get_menu_model()
    section = menu.get_item_link(0, "section")
    actions = [section.get_item_attribute_value(i, "action", None).get_string()
               for i in range(section.get_n_items())]
    assert "win.new-file" in actions
    print("ok: empty folder context menu contains New File")
    win.context_menu.popdown()
    settle()
    win._on_context_click(None, 1, 100, win.view_stack.get_height() - 20, win.view_stack)
    settle(lambda: win.context_menu.get_width() > 0)
    print(f"popover size: {win.context_menu.get_width()} x {win.context_menu.get_height()}")
    assert win.context_menu.get_position() == Gtk.PositionType.TOP
    assert win.context_menu.get_width() >= 250
    print("ok: context menu opens upward and has usable width")
    win.context_menu.popdown()
    win.close()
print("ALL FILE INTERACTION CHECKS PASSED")
