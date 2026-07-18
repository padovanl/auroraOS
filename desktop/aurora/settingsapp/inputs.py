"""Mouse & Touchpad, Keyboard (repeat, shortcuts) and Multitasking pages.

All three edit the compositor configuration through aurora.labwcconf.
"""

from gi.repository import Adw, Gtk

from aurora import labwcconf
from aurora.i18n import _
from aurora.settingsapp.util import Page, combo_row, switch_row


def _yes(v):
    return "yes" if v else "no"


class Mouse(Page):
    page_id = "mouse"
    title = _("Mouse & Touchpad")
    icon_name = "input-mouse-symbolic"

    def build(self):
        self.cfg = labwcconf.Config()
        general = self.group(_("General"))
        general.add(switch_row(_("Left-handed"),
                               self.cfg.device_get("default", "leftHanded") == "yes",
                               lambda v: self._set("default", "leftHanded", _yes(v))))

        mouse = self.group(_("Mouse"))
        mouse.add(self._speed_row("default"))
        profiles = ["adaptive", "flat"]
        cur = self.cfg.device_get("default", "accelProfile", "adaptive")
        mouse.add(combo_row(_("Acceleration"), [_("Adaptive"), _("Flat")],
                            profiles.index(cur) if cur in profiles else 0,
                            on_change=lambda i: self._set("default", "accelProfile", profiles[i])))
        mouse.add(switch_row(_("Natural scrolling"),
                             self.cfg.device_get("default", "naturalScroll") == "yes",
                             lambda v: self._set("default", "naturalScroll", _yes(v)),
                             subtitle=_("Content moves in the direction of the wheel")))

        tp = self.group(_("Touchpad"))
        tp.add(self._speed_row("touchpad"))
        tp.add(switch_row(_("Tap to click"), self.cfg.device_get("touchpad", "tap", "yes") == "yes",
                          lambda v: self._set("touchpad", "tap", _yes(v))))
        tp.add(switch_row(_("Natural scrolling"),
                          self.cfg.device_get("touchpad", "naturalScroll", "yes") == "yes",
                          lambda v: self._set("touchpad", "naturalScroll", _yes(v))))
        tp.add(switch_row(_("Disable while typing"),
                          self.cfg.device_get("touchpad", "disableWhileTyping", "yes") == "yes",
                          lambda v: self._set("touchpad", "disableWhileTyping", _yes(v))))
        methods = ["twofinger", "edge"]
        cur = self.cfg.device_get("touchpad", "scrollMethod", "twofinger")
        tp.add(combo_row(_("Scroll method"), [_("Two fingers"), _("Edge")],
                         methods.index(cur) if cur in methods else 0,
                         on_change=lambda i: self._set("touchpad", "scrollMethod", methods[i])))
        clicks = ["clickfinger", "buttonAreas"]
        cur = self.cfg.device_get("touchpad", "clickMethod", "clickfinger")
        tp.add(combo_row(_("Secondary click"), [_("Two-finger click"), _("Bottom-right corner")],
                         clicks.index(cur) if cur in clicks else 0,
                         on_change=lambda i: self._set("touchpad", "clickMethod", clicks[i])))

    def _speed_row(self, category):
        row = Adw.ActionRow(title=_("Pointer speed"))
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.1)
        try:
            scale.set_value(float(self.cfg.device_get(category, "pointerSpeed", "0")))
        except ValueError:
            scale.set_value(0)
        scale.set_size_request(240, -1)
        scale.set_valign(Gtk.Align.CENTER)
        scale.set_draw_value(False)
        scale.add_mark(0, Gtk.PositionType.BOTTOM, None)
        scale.connect("value-changed",
                      lambda sc: self._set(category, "pointerSpeed", f"{sc.get_value():.1f}"))
        row.add_suffix(scale)
        return row

    def _set(self, category, tag, value):
        self.cfg.device_set(category, tag, value)
        self.cfg.save()


class Keyboard(Page):
    page_id = "keyboard"
    title = _("Keyboard")
    icon_name = "input-keyboard-symbolic"

    def build(self):
        self.cfg = labwcconf.Config()
        typing = self.group(_("Typing"),
                            _("Keyboard layouts are in Language & Region."))
        typing.add(self._scale(_("Repeat delay (ms)"), ("keyboard", "repeatDelay"),
                               150, 1000, 25, 400))
        typing.add(self._scale(_("Repeat rate (per second)"), ("keyboard", "repeatRate"),
                               10, 60, 1, 30))
        typing.add(switch_row(_("Num Lock on at login"),
                              self.cfg.get("keyboard", "numlock", default="on") == "on",
                              lambda v: self._save(("keyboard", "numlock"),
                                                   "on" if v else "off")))

        self.shortcuts = self.group(_("Shortcuts"),
                                    _("Built-in shortcuts, plus your own commands."))
        add = Gtk.Button(icon_name="list-add-symbolic", css_classes=["flat"],
                         tooltip_text=_("Add Custom Shortcut"))
        add.connect("clicked", lambda *_: self._add_dialog())
        self.shortcuts.set_header_suffix(add)
        self._rows = []
        self._fill_shortcuts()

    def _scale(self, title, tags, lo, hi, step, default):
        row = Adw.ActionRow(title=title)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        try:
            scale.set_value(float(self.cfg.get(*tags, default=str(default))))
        except ValueError:
            scale.set_value(default)
        scale.set_size_request(240, -1)
        scale.set_valign(Gtk.Align.CENTER)
        scale.set_digits(0)
        scale.set_value_pos(Gtk.PositionType.LEFT)
        scale.connect("value-changed", lambda sc: self._save(tags, int(sc.get_value())))
        row.add_suffix(scale)
        return row

    def _save(self, tags, value):
        self.cfg.set(*tags, value=value)
        self.cfg.save()

    def _fill_shortcuts(self):
        for r in self._rows:
            self.shortcuts.remove(r)
        self._rows = []
        for key, action, command, element in self.cfg.keybinds():
            label = command if action == "Execute" else action
            row = Adw.ActionRow(title=label or "", subtitle_selectable=True)
            row.add_suffix(Gtk.ShortcutLabel(accelerator=_to_accel(key), valign=Gtk.Align.CENTER))
            if element.get("aurora-custom") == "yes":
                rm = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat"],
                                valign=Gtk.Align.CENTER, tooltip_text=_("Remove"))
                rm.connect("clicked", lambda _b, el=element: self._remove(el))
                row.add_suffix(rm)
            self.shortcuts.add(row)
            self._rows.append(row)

    def _remove(self, element):
        self.cfg.remove(element)
        self.cfg.save()
        self._fill_shortcuts()

    def _add_dialog(self):
        dialog = Adw.AlertDialog(heading=_("Add Custom Shortcut"),
                                 body=_("Press the key combination, then enter the command to run."))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        key_label = Gtk.Label(label=_("Press keys…"), css_classes=["title-3"])
        command = Gtk.Entry(placeholder_text=_("Command, e.g. firefox-esr --private-window"))
        box.append(key_label)
        box.append(command)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        captured = {"key": None}

        ctrl = Gtk.EventControllerKey()

        def pressed(_c, keyval, _code, state):
            from gi.repository import Gdk
            name = Gdk.keyval_name(keyval) or ""
            if name in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
                        "Super_L", "Super_R", "Tab"):
                return False
            mods = []
            if state & Gdk.ModifierType.SUPER_MASK:
                mods.append("W")
            if state & Gdk.ModifierType.CONTROL_MASK:
                mods.append("C")
            if state & Gdk.ModifierType.ALT_MASK:
                mods.append("A")
            if state & Gdk.ModifierType.SHIFT_MASK:
                mods.append("S")
            # Plain keys are typing in the command field, not a shortcut.
            if not mods and not name.startswith(("F", "XF86", "Print")):
                return False
            captured["key"] = "-".join(mods + [name])
            key_label.set_label(captured["key"])
            return True
        ctrl.connect("key-pressed", pressed)
        dialog.add_controller(ctrl)

        def response(_d, resp):
            if resp == "add" and captured["key"] and command.get_text().strip():
                self.cfg.add_command_keybind(captured["key"], command.get_text().strip())
                self.cfg.save()
                self._fill_shortcuts()
        dialog.connect("response", response)
        dialog.present(self.get_root())


def _to_accel(key):
    """labwc 'W-S-Return' → GTK '<Super><Shift>Return'."""
    if not key:
        return ""
    parts = key.split("-")
    mods = {"W": "<Super>", "C": "<Control>", "A": "<Alt>", "S": "<Shift>"}
    out = ""
    for p in parts[:-1]:
        out += mods.get(p, "")
    return out + parts[-1]


class Multitasking(Page):
    page_id = "multitasking"
    title = _("Multitasking")
    icon_name = "view-grid-symbolic"

    def build(self):
        self.cfg = labwcconf.Config()
        ws = self.group(_("Workspaces"),
                        _("Switch with Super+1…9 or Ctrl+Alt+Left/Right."))
        desktops = self.cfg.node("desktops")
        row = Adw.SpinRow.new_with_range(1, 9, 1)
        row.set_title(_("Number of workspaces"))
        row.set_value(int(desktops.get("number", "4")))
        row.connect("notify::value", lambda r, _p: self._set_workspaces(int(r.get_value())))
        ws.add(row)

        win = self.group(_("Windows"))
        win.add(switch_row(_("Snap windows to screen edges"),
                           self.cfg.get("snapping", "range", default="12") != "0",
                           lambda v: self._save(("snapping", "range"), 12 if v else 0),
                           subtitle=_("Drag a window to an edge to fill half the screen")))
        win.add(switch_row(_("Drag to the top to maximize"),
                           self.cfg.get("snapping", "topMaximize", default="yes") == "yes",
                           lambda v: self._save(("snapping", "topMaximize"), _yes(v))))
        win.add(switch_row(_("Focus follows the pointer"),
                           self.cfg.get("focus", "followMouse", default="no") == "yes",
                           lambda v: self._save(("focus", "followMouse"), _yes(v))))

    def _save(self, tags, value):
        self.cfg.set(*tags, value=value)
        self.cfg.save()

    def _set_workspaces(self, n):
        desktops = self.cfg.node("desktops")
        desktops.set("number", str(n))
        names = desktops.find("names")
        if names is not None:
            desktops.remove(names)
        self.cfg.save()
