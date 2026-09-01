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
from aurora.shell import search
from aurora.shell.launcher import AppTile, ResultRow
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

    desktopicons.DesktopIcons._order_path = staticmethod(lambda: str(root / "order.json"))
    (root / "Desktop/a.txt").write_text("a")
    (root / "Desktop/b.txt").write_text("b")
    icons = desktopicons.DesktopIcons()
    icons.reorder("b.txt", "a.txt")
    assert icons._load_order().index("b.txt") < icons._load_order().index("a.txt")
    buttons = []
    child = icons.get_first_child()
    while child is not None:
        buttons.append(child.get_child())
        child = child.get_next_sibling()
    a_icon = next(button for button in buttons if button.gfile and
                  button.gfile.get_basename() == "a.txt")
    controls = a_icon.observe_controllers()
    assert any(isinstance(controls.get_item(i), Gtk.DragSource)
               for i in range(controls.get_n_items()))
    assert any(isinstance(controls.get_item(i), Gtk.DropTarget)
               for i in range(controls.get_n_items()))
    icons.transfer([str(root / "Desktop/a.txt")], str(root / "Desktop/New folder"), move=True)
    settle(lambda: (root / "Desktop/New folder/a.txt").exists())
    assert not (root / "Desktop/a.txt").exists()
    print("ok: desktop icon reordering and move into folder")
    icon_window = Gtk.Window(child=icons, default_width=450, default_height=300)
    icon_window.present()
    settle(lambda: icon_window.get_width() > 0)
    child = icons.get_first_child()
    while child is not None and (child.get_child().gfile is None or
                                  child.get_child().gfile.get_basename() != "b.txt"):
        child = child.get_next_sibling()
    assert child is not None
    child.get_child().show_menu(8, 8)
    pop = child.get_child().get_last_child()
    assert isinstance(pop, Gtk.Popover)
    labels = []
    button = pop.get_child().get_first_child()
    while button is not None:
        if isinstance(button, Gtk.Button):
            labels.append(button.get_label())
        button = button.get_next_sibling()
    assert {"Open", "Rename…", "Move to Trash"}.issubset(labels)
    pop.popdown()
    icon_window.close()
    print("ok: desktop file context menu")

    app_info = Gio.DesktopAppInfo.new("org.aurora.Files.desktop")
    assert app_info is not None
    tile = AppTile(app_info, SimpleNamespace())
    tile_grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE)
    tile_grid.append(tile)
    tile_window = Gtk.Window(child=tile_grid, default_width=200, default_height=160)
    tile_window.present()
    settle(lambda: tile_window.get_width() > 0)
    tile._show_menu(None, 1, 10, 10)
    app_menu = tile.get_last_child()
    assert isinstance(app_menu, Gtk.Popover)
    labels = []
    button = app_menu.get_child().get_first_child()
    while button is not None:
        if isinstance(button, Gtk.Button):
            labels.append(button.get_label())
        button = button.get_next_sibling()
    assert {"Open", "New Window", "Add to Desktop", "Show in Files"}.issubset(labels)
    tile._add_to_desktop()
    assert (root / "Desktop/org.aurora.Files.desktop").exists()
    app_menu.popdown()
    tile_window.close()
    print("ok: app launcher context menu and desktop shortcut")

    match = next(result for result in search.search_apps("Files")
                 if result.app is not None and result.app.get_id() == app_info.get_id())
    result_row = ResultRow(match, SimpleNamespace())
    result_list = Gtk.ListBox()
    result_list.append(result_row)
    search_window = Gtk.Window(child=result_list, default_width=400, default_height=100)
    search_window.present()
    settle(lambda: search_window.get_width() > 0)
    result_row._show_menu(None, 1, 10, 10)
    result_menu = result_row.get_last_child()
    assert isinstance(result_menu, Gtk.Popover)
    result_menu.popdown()
    search_window.close()
    print("ok: app search result context menu")

    file_result = search.Result("existing.txt", "Recent file", path=str(root / "existing.txt"))
    file_row = ResultRow(file_result)
    file_list = Gtk.ListBox()
    file_list.append(file_row)
    file_window = Gtk.Window(child=file_list, default_width=400, default_height=100)
    file_window.present()
    settle(lambda: file_window.get_width() > 0)
    file_row._show_menu(None, 1, 10, 10)
    file_menu = file_row.get_last_child()
    assert isinstance(file_menu, Gtk.Popover)
    file_actions = []
    button = file_menu.get_child().get_first_child()
    while button is not None:
        if isinstance(button, Gtk.Button):
            file_actions.append(button.get_label())
        button = button.get_next_sibling()
    assert {"Open", "Show in Files", "Copy Path", "Ask Aurora about this file"}.issubset(
        file_actions)
    file_menu.popdown()
    file_window.close()
    print("ok: recent-file search context actions")

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
    moved = root / "move.txt"
    moved.write_text("move me")
    move_list = Gdk.FileList.new_from_list([Gio.File.new_for_path(str(moved))])
    assert win._drop_on_location(move_list, Gio.File.new_for_path(str(empty)), move=True)
    settle(lambda: (empty / "move.txt").exists() and not moved.exists())
    win.undo()
    settle(lambda: moved.exists() and not (empty / "move.txt").exists())
    print("ok: dropped file move and undo")
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
