"""Desktop background, one surface per monitor, with a right-click menu."""

from gi.repository import Gdk, Gio, Gtk

from aurora.i18n import _
from aurora.shell.layer import Layer, LayerWindow

FADE_MS = 2500      # crossfade when the dynamic wallpaper moves to the next phase


class Wallpaper(LayerWindow):
    def __init__(self, app, monitor):
        super().__init__(app, "aurora-wallpaper", layer=Layer.BACKGROUND,
                         anchors=("top", "bottom", "left", "right"), monitor=monitor,
                         exclusive=-1)  # cover the whole output, ignore panels
        self.add_css_class("aurora-wallpaper")
        self.app = app
        # Two pictures in a crossfading stack: the new background fades in.
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE,
                                transition_duration=FADE_MS, hexpand=True, vexpand=True)
        self._pictures = []
        for name in ("a", "b"):
            pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
            self._stack.add_named(pic, name)
            self._pictures.append(pic)
        self._current = None
        overlay = Gtk.Overlay(child=self._stack)
        self.set_child(overlay)
        # Files from ~/Desktop, on the primary monitor only.
        self._icons = None
        if monitor == app.get_primary_monitor():
            from aurora.shell.desktopicons import DesktopIcons
            self._icons = DesktopIcons()
            overlay.add_overlay(self._icons)
            # A click on empty desktop clears the selection.
            clear = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
            clear.connect("pressed", self._on_background_click)
            overlay.add_controller(clear)
            drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            drop.connect("drop", self._on_drop)
            overlay.add_controller(drop)
        self._menu = self._build_menu(overlay)

        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self._on_right_click)
        overlay.add_controller(click)

        self._handler = app.daycycle.connect("wallpaper-changed", lambda *a: self.reload())
        self.connect("destroy", lambda *a: app.daycycle.disconnect(self._handler))
        self.reload()

    def _on_background_click(self, _gesture, _n, x, y):
        widget = self.get_child().pick(x, y, Gtk.PickFlags.DEFAULT)
        while widget is not None:
            if widget.has_css_class("desktop-icon"):
                return  # the icon handles its own click
            widget = widget.get_parent()
        self._icons.select(None)

    def _on_drop(self, _target, value, x, y):
        from aurora.shell.desktopicons import DesktopIcon, desktop_dir
        if not isinstance(value, Gdk.FileList) or self._icons is None:
            return False
        picked = self.get_child().pick(x, y, Gtk.PickFlags.DEFAULT)
        if picked is not None and (isinstance(picked, DesktopIcon) or
                                   picked.get_ancestor(DesktopIcon) is not None):
            return False  # the icon's own target handles folders and reordering
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        if not paths:
            return False
        import os
        if len(paths) == 1 and os.path.dirname(paths[0]) == desktop_dir():
            self._icons.reorder_to_end(os.path.basename(paths[0]))
            return True
        os.makedirs(desktop_dir(), exist_ok=True)
        from aurora.dnd import is_move
        self._icons.transfer(paths, desktop_dir(),
                             move=is_move(_target))
        return True

    def reload(self):
        path = self.app.daycycle.wallpaper()
        if path == self._current:
            return
        self._current = path
        visible = self._stack.get_visible_child()
        target = self._pictures[1] if visible is self._pictures[0] else self._pictures[0]
        target.set_file(Gio.File.new_for_path(path) if path else None)
        self._stack.set_visible_child(target)

    def _build_menu(self, parent):
        actions = Gio.SimpleActionGroup()
        for name, folder in (("new-file", False), ("new-folder", True)):
            create = Gio.SimpleAction.new(name, None)
            create.connect("activate", self._new_item, folder)
            actions.add_action(create)
        parent.insert_action_group("desktop", actions)
        menu = Gio.Menu()
        section = Gio.Menu()
        section.append(_("New File…"), "desktop.new-file")
        section.append(_("New Folder…"), "desktop.new-folder")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("Open Terminal"), "app.open-terminal")
        section.append(_("Open Files"), "app.open-files")
        menu.append_section(None, section)
        section = Gio.Menu()
        section.append(_("Change Background…"), "app.settings::appearance")
        section.append(_("Display Settings"), "app.settings::display")
        section.append(_("Settings"), "app.settings::")
        menu.append_section(None, section)
        popover = Gtk.PopoverMenu(menu_model=menu, has_arrow=False,
                                  halign=Gtk.Align.START,
                                  css_classes=["aurora-context-menu"])
        popover.set_parent(parent)
        return popover

    def _new_item(self, _action, _parameter, folder=False):
        import os
        from aurora.files.create import NewItemDialog
        from aurora.shell.desktopicons import desktop_dir
        directory = desktop_dir()
        dialog = NewItemDialog(self.app, Gio.File.new_for_path(directory), folder=folder)
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as err:
            dialog.error.set_label(str(err))
            dialog.error.set_visible(True)
        dialog.present()

    def _on_right_click(self, gesture, _n, x, y):
        from aurora.shell.desktopicons import DesktopIcon
        picked = self.get_child().pick(x, y, Gtk.PickFlags.DEFAULT)
        icon = picked if isinstance(picked, DesktopIcon) else (
            picked.get_ancestor(DesktopIcon) if picked is not None else None)
        if icon is not None and icon.gfile is not None:
            cx, cy = self.get_child().translate_coordinates(icon, x, y)[-2:]
            icon.show_menu(cx, cy)
            return
        self._menu.set_position(Gtk.PositionType.TOP if y > self.get_height() / 2
                                else Gtk.PositionType.BOTTOM)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self._menu.set_pointing_to(rect)
        self._menu.popup()
