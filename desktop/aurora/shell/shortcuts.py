"""Keyboard shortcuts at a glance (Super+/): every shortcut, described the same
way as in Settings → Keyboard, over a dimmed screen. Any key or click closes it."""

from gi.repository import Gdk, Gtk

from aurora import apps, labwcconf
from aurora.i18n import _
from aurora.shell.layer import Keyboard, Layer, LayerWindow


def shortcut_rows():
    """[(description, [labwc key, …])] in the order of the configuration, one row
    per action (keys that do the same thing share it)."""
    from aurora.settingsapp.inputs import describe_shortcut
    rows, index = [], {}
    for key, action, command, element in labwcconf.Config().keybinds():
        title = describe_shortcut(action, command, element)
        if not title or key.startswith("XF86"):  # media keys are labeled on the keyboard
            continue
        if title in index:
            rows[index[title]][1].append(key)
        else:
            index[title] = len(rows)
            rows.append((title, [key]))
    return rows


class ShortcutsOverlay(LayerWindow):
    def __init__(self, shell):
        super().__init__(shell, "aurora-shortcuts", layer=Layer.OVERLAY,
                         anchors=("top", "bottom", "left", "right"), exclusive=-1,
                         keyboard=Keyboard.EXCLUSIVE)
        self.shell = shell
        self.add_css_class("aurora-shortcuts")
        from aurora.settingsapp.inputs import _to_accel
        self._to_accel = _to_accel

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                       halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                       css_classes=["shortcuts-card"])
        card.append(Gtk.Label(label=_("Keyboard Shortcuts"), css_classes=["title-2"]))
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=2, max_children_per_line=3,
                                column_spacing=28, row_spacing=4)
        scroller = Gtk.ScrolledWindow(child=self.flow, propagate_natural_height=True,
                                      propagate_natural_width=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      max_content_height=640)
        card.append(scroller)
        foot = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        foot.append(Gtk.Label(label=_("Press any key to close"), css_classes=["dim-label"]))
        edit = Gtk.Button(label=_("Change Shortcuts…"), css_classes=["flat"])
        edit.connect("clicked", lambda *_: (self.set_visible(False),
                                            apps.spawn(["aurora-settings", "--page", "keyboard"])))
        foot.append(edit)
        card.append(foot)
        self.set_child(card)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)

    def toggle(self):
        if self.get_visible():
            self.set_visible(False)
            return
        self.shell.close_overlays(self)
        self._fill()
        self.present()

    def _fill(self):
        while (child := self.flow.get_first_child()) is not None:
            self.flow.remove(child)
        for title, keys in shortcut_rows():
            row = Gtk.Box(spacing=12, css_classes=["shortcuts-row"])
            row.append(Gtk.Label(label=title, xalign=0, hexpand=True, wrap=True,
                                 max_width_chars=30))
            for key in keys[:2]:
                if key in ("Super_L", "Super_R"):
                    accel = Gtk.ShortcutLabel(accelerator="Super_L", valign=Gtk.Align.CENTER)
                    keycap = accel.get_first_child()
                    if isinstance(keycap, Gtk.Label):
                        keycap.set_label(_("Super"))
                else:
                    accel = Gtk.ShortcutLabel(accelerator=self._to_accel(key),
                                              valign=Gtk.Align.CENTER)
                row.append(accel)
            self.flow.append(row)

    def _on_key(self, _ctrl, keyval, _code, _state):
        # Modifier presses alone don't close it: Super is still held after Super+/.
        if keyval in (Gdk.KEY_Super_L, Gdk.KEY_Super_R, Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
                      Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
            return False
        self.set_visible(False)
        return True

    def _on_click(self, gesture, _n, x, y):
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        card = self.get_child()
        if picked is None or not (picked is card or picked.is_ancestor(card)):
            self.set_visible(False)
