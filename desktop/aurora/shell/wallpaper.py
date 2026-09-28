"""Desktop background, one surface per monitor, with a right-click menu."""

from gi.repository import Gdk, Gio, GLib, Gtk

from aurora.i18n import _
from aurora.shell.layer import Keyboard, Layer, LayerWindow

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
            self._selection_box = Gtk.DrawingArea(hexpand=True, vexpand=True,
                                                  can_target=False)
            self._selection_box.set_draw_func(self._draw_selection)
            overlay.add_overlay(self._selection_box)
            self._selection_rect = None
            self._selection_origin = None
            self._dragging_widget = False
            select_drag = Gtk.GestureDrag()
            select_drag.connect("drag-begin", self._selection_begin)
            select_drag.connect("drag-update", self._selection_update)
            select_drag.connect("drag-end", self._selection_end)
            overlay.add_controller(select_drag)
            # A click on empty desktop clears the selection.
            clear = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
            clear.connect("pressed", self._on_background_click)
            overlay.add_controller(clear)
            drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            drop.connect("drop", self._on_drop)
            overlay.add_controller(drop)
            # Widgets sit above the icons, each only as big as itself.
            from aurora.shell.widgets import WidgetLayer
            self.widgets = WidgetLayer(app, overlay, monitor)
            app.widget_layer = self.widgets
            # Typing into Notes, To Do and the widget options: the desktop
            # takes the keyboard when clicked, like any window.
            self.set_keyboard(Keyboard.ON_DEMAND)
        self._menu = self._build_menu(overlay)

        click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        click.connect("pressed", self._on_right_click)
        overlay.add_controller(click)

        self._handler = app.daycycle.connect("wallpaper-changed", lambda *a: self.reload())
        self.connect("destroy", lambda *a: app.daycycle.disconnect(self._handler))
        self.reload()

    def _on_background_click(self, _gesture, _n, x, y):
        if _gesture.get_current_event_state() & (Gdk.ModifierType.CONTROL_MASK |
                                               Gdk.ModifierType.SHIFT_MASK):
            return
        widget = self.get_child().pick(x, y, Gtk.PickFlags.DEFAULT)
        while widget is not None:
            if widget.has_css_class("desktop-icon"):
                return  # the icon handles its own click
            widget = widget.get_parent()
        self._icons.select(None)

    def _selection_begin(self, gesture, x, y):
        """One drag, one job: move the widget under the pointer, or draw the
        selection rectangle on empty desktop, never both."""
        picked = self.get_child().pick(x, y, Gtk.PickFlags.DEFAULT)
        from aurora.shell.desktopicons import DesktopIcon
        self._selection_origin = None
        self._dragging_widget = False
        if picked is not None and (isinstance(picked, DesktopIcon) or
                                   picked.get_ancestor(DesktopIcon) is not None):
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        if picked is not None and (picked is self.widgets.gallery or
                                   picked.is_ancestor(self.widgets.gallery)):
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        from aurora.shell.widgets import DesktopWidget
        on_widget = picked if isinstance(picked, DesktopWidget) else (
            picked.get_ancestor(DesktopWidget) if picked is not None else None)
        if on_widget is not None:
            widget = self.widgets.widget_at(picked)
            if widget is None:          # text in a Notes widget: select it instead
                gesture.set_state(Gtk.EventSequenceState.DENIED)
                return
            self._dragging_widget = True
            self.widgets.drag_begin(widget, x, y)
            return
        if self.widgets.editing:
            # Arranging widgets: no selection rectangle (it works everywhere
            # else, outside edit mode).
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        self._selection_origin = (x, y, set(self._icons._selected))

    def _selection_update(self, _gesture, dx, dy):
        if self._dragging_widget:
            self.widgets.drag_update(dx, dy)
            return
        if self._selection_origin is None:
            return
        x, y, original = self._selection_origin
        self._selection_rect = (x, y, x + dx, y + dy)
        self._selection_box.queue_draw()
        start = self.get_child().translate_coordinates(self._icons, x, y)[-2:]
        end = self.get_child().translate_coordinates(self._icons, x + dx, y + dy)[-2:]
        self._icons.select_rect(*start, *end, original)

    def _selection_end(self, *_args):
        if self._dragging_widget:
            self._dragging_widget = False
            self.widgets.drag_end()
        self._selection_origin = None
        self._selection_rect = None
        self._selection_box.queue_draw()

    def _draw_selection(self, _area, cr, _width, _height):
        if self._selection_rect is None:
            return
        x1, y1, x2, y2 = self._selection_rect
        x, y = min(x1, x2), min(y1, y2)
        width, height = abs(x2 - x1), abs(y2 - y1)
        cr.set_source_rgba(0.66, 0.44, 1.0, 0.20)
        cr.rectangle(x, y, width, height)
        cr.fill_preserve()
        cr.set_source_rgba(0.76, 0.60, 1.0, 0.85)
        cr.set_line_width(1)
        cr.stroke()

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
            cx, cy = self.get_child().translate_coordinates(self._icons, x, y)[-2:]
            self._icons.place(os.path.basename(paths[0]), cx - 40, cy - 40)
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
        popover = Gtk.Popover(has_arrow=False, halign=Gtk.Align.START,
                              css_classes=["aurora-context-menu"])
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1,
                      margin_top=3, margin_bottom=3, margin_start=3, margin_end=3)
        sections = [
            [(_("New File…"), "desktop.new-file", None),
             (_("New Folder…"), "desktop.new-folder", None)],
            [(_("Open Terminal"), "app.open-terminal", None),
             (_("Open Files"), "app.open-files", None)],
            [(_("Edit Widgets…"), "app.edit-widgets", None),
             (_("Change Background…"), "app.settings", "appearance"),
             (_("Display Settings"), "app.settings", "display"),
             (_("Settings"), "app.settings", "")],
        ]
        for index, section in enumerate(sections):
            if index:
                box.append(Gtk.Separator())
            for label, action, target in section:
                button = Gtk.Button(label=label, css_classes=["flat", "context-action"],
                                    action_name=action)
                button.get_child().set_xalign(0)
                if target is not None:
                    button.set_action_target_value(GLib.Variant("s", target))
                button.connect("clicked", lambda *_: popover.popdown())
                box.append(button)
        popover.set_child(box)
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
