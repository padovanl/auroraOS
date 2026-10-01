"""Pinned screenshots, like Snipaste: a screenshot that floats above every
window while you work (copy a code sample, keep a reference in view, compare).

Drag it anywhere; scroll to make it bigger or smaller; double-click or Esc
closes it; Ctrl+C copies the picture; right-click for Copy, Save As… and
Close. In the Aurora session it stays above the other windows."""

import shutil
import subprocess

from gi.repository import Gdk, Gio, GLib, Gtk

from aurora.i18n import _

TITLE = "Aurora Pinned Screenshot"
MAX_SCREEN_SHARE = 0.6      # a big screenshot starts at most this much of the screen


def initial_size(width, height, screen_w, screen_h, share=MAX_SCREEN_SHARE):
    """The picture's own size, shrunk to fit a share of the screen."""
    scale = min(1.0, screen_w * share / max(width, 1), screen_h * share / max(height, 1))
    return max(int(width * scale), 48), max(int(height * scale), 48)


class PinnedShot(Gtk.Window):
    def __init__(self, app, path):
        super().__init__(application=app, title=TITLE, decorated=False, resizable=True,
                         css_classes=["pinned-shot"])
        self.path = path
        self.texture = Gdk.Texture.new_from_filename(path)
        self.ratio = self.texture.get_width() / max(self.texture.get_height(), 1)
        monitor = Gdk.Display.get_default().get_monitors().get_item(0)
        geometry = monitor.get_geometry() if monitor else None
        w, h = initial_size(self.texture.get_width(), self.texture.get_height(),
                            geometry.width if geometry else 1920,
                            geometry.height if geometry else 1080)
        self.set_default_size(w, h)

        picture = Gtk.Picture(paintable=self.texture, content_fit=Gtk.ContentFit.FILL,
                              can_shrink=True)
        close = Gtk.Button(icon_name="window-close-symbolic", halign=Gtk.Align.END,
                           valign=Gtk.Align.START, margin_top=6, margin_end=6,
                           css_classes=["circular", "osd", "pinned-close"],
                           tooltip_text=_("Unpin"))
        close.connect("clicked", lambda *_a: self.close())
        overlay = Gtk.Overlay(child=picture)
        overlay.add_overlay(close)
        self.set_child(Gtk.WindowHandle(child=overlay))

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)
        # Before the drag handle, which would maximize on a double-click.
        double = Gtk.GestureClick(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        double.connect("pressed", self._on_press)
        self.add_controller(double)
        menu = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        menu.connect("pressed", self._on_menu)
        self.add_controller(menu)
        self.connect("map", lambda *_a: GLib.timeout_add(250, self._keep_on_top))

    def _on_press(self, gesture, n_press, _x, _y):
        if n_press == 2:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self.close()

    def _keep_on_top(self):
        """Wayfire: find this window by its title and keep it above the others."""
        from aurora import wayfirelayout
        try:
            for view in wayfirelayout.views():
                if view.get("title") == TITLE and view.get("role") == "toplevel":
                    wayfirelayout.request("wm-actions/set-always-on-top",
                                          {"view_id": view["id"], "state": True})
                    wayfirelayout.request("wm-actions/set-sticky",
                                          {"view_id": view["id"], "state": True})
        except (OSError, ValueError, ConnectionError, KeyError):
            pass
        return False

    def _on_scroll(self, _ctrl, _dx, dy):
        w = self.get_width() or self.get_default_size()[0]
        new_w = int(min(max(w * (0.9 if dy > 0 else 1.1), 64), 4000))
        self.set_default_size(new_w, int(new_w / self.ratio))
        return True

    def _on_key(self, _ctrl, keyval, _code, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if keyval in (Gdk.KEY_c, Gdk.KEY_C) and state & Gdk.ModifierType.CONTROL_MASK:
            self.copy()
            return True
        return False

    def copy(self):
        if shutil.which("wl-copy"):
            with open(self.path, "rb") as f:
                subprocess.Popen(["wl-copy", "--type", "image/png"], stdin=f)

    def save_as(self):
        dialog = Gtk.FileDialog(title=_("Save Screenshot"),
                                initial_name=GLib.path_get_basename(self.path))

        def done(dlg, res):
            try:
                target = dlg.save_finish(res)
            except GLib.Error:
                return
            if target is not None and target.get_path():
                shutil.copyfile(self.path, target.get_path())
        dialog.save(self, None, done)

    def _on_menu(self, gesture, _n, x, y):
        pop = Gtk.Popover(has_arrow=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for label, cb in ((_("Copy"), self.copy), (_("Save As…"), self.save_as),
                          (_("Open"), lambda: Gio.AppInfo.launch_default_for_uri(
                              GLib.filename_to_uri(self.path), None)),
                          (_("Unpin"), self.close)):
            b = Gtk.Button(label=label, css_classes=["flat"])
            b.get_child().set_xalign(0)
            b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), cb()))
            box.append(b)
        pop.set_child(box)
        pop.set_parent(self.get_child())
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        pop.set_pointing_to(rect)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()


def pin(app, path):
    window = PinnedShot(app, path)
    window.present()
    return window
