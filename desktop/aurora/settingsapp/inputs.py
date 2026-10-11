"""Mouse & Touchpad, Keyboard (repeat, shortcuts) and Multitasking pages.

All three edit the compositor configuration through aurora.labwcconf.
"""

from gi.repository import Adw, Gtk

from aurora import labwcconf, settings
from aurora.i18n import _
from aurora.settingsapp.util import Page, combo_row, switch_row


def _yes(v):
    return "yes" if v else "no"


def describe_shortcut(action, command, element):
    """What a keybinding does, in words (custom commands show the command)."""
    commands = {
        "aurora-shell launcher": _("Search and Launchpad"),
        "aurora-shell quick-settings": _("Control Center"),
        "aurora-shell clipboard": _("Clipboard history"),
        "aurora-clipboard show": _("Clipboard window"),
        "aurora-shell emoji": _("Emoji picker"),
        "aurora-shell dictate": _("Dictation"),
        "aurora-shell read-aloud": _("Read selected text aloud"),
        "aurora-shell assistant": _("Aurora Assistant"),
        "aurora-shell writing": _("Writing tools"),
        "aurora-shell overview": _("Show all windows"),
        "aurora-shell snap-layouts": _("Snap layouts"),
        "aurora-shell always-on-top": _("Keep window on top"),
        "aurora-shell screenshot": _("Screenshot of the screen"),
        "aurora-shell screenshot area": _("Screenshot of an area"),
        "aurora-shell screenshot text": _("Copy text from the screen"),
        "aurora-shell screenshot pin": _("Pin an area of the screen"),
        "aurora-shell record": _("Start or stop screen recording"),
        "aurora-shell record area": _("Record an area of the screen"),
        "aurora-shell colorpick": _("Pick a color from the screen"),
        "aurora-shell shortcuts": _("Show keyboard shortcuts"),
        "aurora-shell keep-awake": _("Keep Awake"),
        "aurora-shell volume up": _("Volume up"),
        "aurora-shell volume down": _("Volume down"),
        "aurora-shell volume mute": _("Mute"),
        "aurora-shell brightness up": _("Brightness up"),
        "aurora-shell brightness down": _("Brightness down"),
        "ptyxis --new-window": _("New terminal window"),
        "aurora-files": _("Files"),
        "aurora-taskmanager": _("Task Manager"),
        "aurora-settings": _("Settings"),
        "aurora-shell lock": _("Lock screen"),
        "aurora-lock": _("Lock screen"),
    }
    actions = {
        "NextWindow": _("Next window"),
        "PreviousWindow": _("Previous window"),
        "Close": _("Close window"),
        "Maximize": _("Maximize window"),
        "UnMaximize": _("Restore window size"),
        "Iconify": _("Minimize window"),
        "ToggleFullscreen": _("Full screen"),
        "ToggleAlwaysOnTop": _("Keep window on top"),
        "ToggleMagnify": _("Zoom on or off"),
        "ZoomIn": _("Zoom in"),
        "ZoomOut": _("Zoom out"),
        "ShowMenu": _("Window menu"),
    }
    action_el = element.find("action") if element is not None else None
    arg = lambda name: action_el.get(name) if action_el is not None else None  # noqa: E731
    if action == "Execute":
        if element is not None and element.get("aurora-custom") == "yes":
            return command or ""
        return commands.get(command, command or "")
    if action == "SnapToEdge":
        return _("Snap window left") if arg("direction") == "left" else _("Snap window right")
    if action == "SnapToRegion":
        regions = {"top-left": _("Move window to the top-left quarter"),
                   "top-right": _("Move window to the top-right quarter"),
                   "bottom-left": _("Move window to the bottom-left quarter"),
                   "bottom-right": _("Move window to the bottom-right quarter"),
                   "left-third": _("Move window to the left third"),
                   "center-third": _("Move window to the center third"),
                   "right-third": _("Move window to the right third")}
        region = arg("region") or ""
        return regions.get(region, region)
    if action == "GoToDesktop":
        to = arg("to") or ""
        if to == "left":
            return _("Previous workspace")
        if to == "right":
            return _("Next workspace")
        return _("Go to workspace {n}").format(n=to)
    if action == "SendToDesktop":
        return _("Move window to workspace {n}").format(n=arg("to") or "")
    return actions.get(action, action or "")


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
        aurora = settings.get()
        if aurora is not None:
            tp.add(switch_row(_("Gestures"), aurora.get_boolean("gestures"),
                              lambda v: aurora.set_boolean("gestures", v),
                              subtitle=_("Three fingers: up for all windows, down for the "
                                         "desktop, sideways to change workspace. Pinch with "
                                         "four fingers for Launchpad.")))

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
        aurora_s = settings.get()
        if aurora_s is not None:
            typing.add(switch_row(_("Show Caps Lock and Num Lock on screen"),
                                  aurora_s.get_boolean("lock-keys-osd"),
                                  lambda v: aurora_s.set_boolean("lock-keys-osd", v),
                                  subtitle=_("A moment's notice when you press them")))

        # Compose key: type accents and symbols as sequences (Compose, ', e → é).
        from aurora.settingsapp.language import set_xkb_option, xkb_option
        compose = self.group(_("Special Characters"),
                             _("Press the Compose key, then a sequence: ' then e gives é, "
                               "o then c gives ©, = then e gives €."))
        keys = [("", _("None")), ("compose:ralt", _("Right Alt")),
                ("compose:rwin", _("Right Super")), ("compose:menu", _("Menu key")),
                ("compose:rctrl", _("Right Ctrl")), ("compose:caps", _("Caps Lock"))]
        cur = xkb_option("compose:")
        ids = [k for k, _l in keys]
        compose.add(combo_row(_("Compose key"), [label for _k, label in keys],
                              ids.index(cur) if cur in ids else 0,
                              on_change=lambda i: set_xkb_option("compose:", ids[i])))
        compose.add(Adw.ActionRow(title=_("Emoji"),
                                  subtitle=_("Super+. opens the emoji picker in any app.")))

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
        built_in = {}  # description -> row, so keys doing the same thing share a row
        for key, action, command, element in self.cfg.keybinds():
            title = describe_shortcut(action, command, element)
            if key in ("Super_L", "Super_R"):
                # The Super key on its own ("Super L" as GTK would write it).
                accel = Gtk.ShortcutLabel(accelerator="Super_L", valign=Gtk.Align.CENTER)
                keycap = accel.get_first_child()
                if isinstance(keycap, Gtk.Label):
                    keycap.set_label(_("Super"))
            else:
                accel = Gtk.ShortcutLabel(accelerator=_to_accel(key), valign=Gtk.Align.CENTER)
            custom = element.get("aurora-custom") == "yes"
            if not custom and title in built_in:
                accel.set_margin_start(14)
                built_in[title].add_suffix(accel)
                continue
            row = Adw.ActionRow(title=title, use_markup=False, subtitle_selectable=True)
            row.add_suffix(accel)
            if not custom:
                built_in[title] = row
            if custom:
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

        aurora = settings.get()
        if aurora is not None:
            corners = self.group(_("Hot Corners"),
                                 _("Push the pointer into a corner of the screen to…"))
            actions = [("none", _("Do Nothing")), ("overview", _("Show All Windows")),
                       ("launchpad", _("Show Apps (Launchpad)")),
                       ("desktop", _("Show Desktop")),
                       ("quick-settings", _("Open Control Center")),
                       ("notifications", _("Open Notifications")),
                       ("lock", _("Lock Screen")), ("screen-off", _("Turn Screen Off"))]
            ids = [a for a, _l in actions]
            for corner, title in (("top-left", _("Top left")), ("top-right", _("Top right")),
                                  ("bottom-left", _("Bottom left")),
                                  ("bottom-right", _("Bottom right"))):
                key = f"hot-corner-{corner}"
                cur = aurora.get_string(key)
                corners.add(combo_row(title, [lbl for _a, lbl in actions],
                                      ids.index(cur) if cur in ids else 0,
                                      on_change=lambda i, k=key: aurora.set_string(k, ids[i])))

        win = self.group(_("Windows"),
                         _("Super+W shows all windows. Super+Left/Right fills half the screen, "
                           "Super+Ctrl+U/I/J/K a quarter, Super+Ctrl+D/F/G a third. "
                           "Hold Super while dragging a window to drop it into a quarter or third."))
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
