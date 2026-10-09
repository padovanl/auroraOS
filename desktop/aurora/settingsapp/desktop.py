"""Desktop & Dock: layout presets and every knob behind them."""

import subprocess

from gi.repository import Adw, Gtk

from aurora import look, settings
from aurora.i18n import N_, _
from aurora.settingsapp.util import Page, combo_row, switch_row, toast

# Each preset is a set of org.aurora.desktop values.
PRESETS = {
    "aurora": {
        "title": N_("Aurora"), "subtitle": N_("Menu bar on top, floating dock"),
        "icon": "preferences-desktop-apps-symbolic",
        "values": {"panel-position": "top", "panel-style": "bar", "clock-position": "right",
                   "panel-opacity": 0.78,
                   "dock-position": "bottom", "dock-style": "floating", "dock-icon-size": 48,
                   "dock-magnification": True, "dock-autohide": False,
                   "window-buttons": "left", "window-button-style": "traffic",
                   "launcher-style": "spotlight"},
    },
    "classic": {
        "title": N_("Classic"), "subtitle": N_("Full-width taskbar at the bottom"),
        "icon": "view-dual-symbolic",
        "values": {"panel-position": "top", "panel-style": "bar", "clock-position": "right",
                   "panel-opacity": 0.95,
                   "dock-position": "bottom", "dock-style": "panel", "dock-icon-size": 36,
                   "dock-magnification": False, "dock-autohide": False,
                   "window-buttons": "right", "window-button-style": "symbolic",
                   "launcher-style": "grid"},
    },
    "studio": {
        "title": N_("Studio"), "subtitle": N_("Dock on the left, clock in the middle"),
        "icon": "sidebar-show-symbolic",
        "values": {"panel-position": "top", "panel-style": "bar", "clock-position": "center",
                   "panel-opacity": 0.95,
                   "dock-position": "left", "dock-style": "panel", "dock-icon-size": 42,
                   "dock-magnification": False, "dock-autohide": False,
                   "window-buttons": "right", "window-button-style": "symbolic",
                   "launcher-style": "grid"},
    },
    "minimal": {
        "title": N_("Minimal"), "subtitle": N_("Dock hides until you need it"),
        "icon": "focus-windows-symbolic",
        "values": {"panel-position": "top", "panel-style": "bar", "clock-position": "center",
                   "panel-opacity": 0.5,
                   "dock-position": "bottom", "dock-style": "floating", "dock-icon-size": 44,
                   "dock-magnification": True, "dock-autohide": True,
                   "window-buttons": "left", "window-button-style": "traffic",
                   "launcher-style": "spotlight"},
    },
}

LOOK_KEYS = {"window-buttons", "window-button-style", "window-corner-radius", "window-gaps"}


class DesktopProfiles(Page):
    page_id = "profiles"
    title = _("Desktop Profiles")
    icon_name = "preferences-system-symbolic"

    def build(self):
        from aurora import desktopprofiles
        builtins = self.group(_("Ready-made profiles"),
                              _("Apply a set of dock, notification, animation and power settings."))
        for key, title in (("work", _("Work")), ("gaming", _("Gaming")),
                           ("battery", _("Battery"))):
            row = Adw.ButtonRow(title=title)
            row.connect("activated", lambda _r, name=key:
                        self._apply_profile(name))
            builtins.add(row)
        self.custom = self.group(_("Saved profiles"))
        self._refresh_custom()
        save = Adw.ButtonRow(title=_("Save current setup…"))
        save.connect("activated", lambda *_: self._save_dialog())
        self.custom.add(save)

    def _refresh_custom(self):
        from aurora import desktopprofiles
        for row in getattr(self, "_custom_rows", []):
            self.custom.remove(row)
        self._custom_rows = []
        for name in sorted(desktopprofiles.load()):
            row = Adw.ButtonRow(title=name)
            row.connect("activated", lambda _r, value=name: self._apply_profile(value))
            self.custom.add(row)
            self._custom_rows.append(row)

    def _apply_profile(self, name):
        from aurora import desktopprofiles
        if desktopprofiles.apply(name):
            toast(self, _("Profile applied"))

    def _save_dialog(self):
        from aurora import desktopprofiles
        dialog = Adw.AlertDialog(heading=_("Save current setup"))
        entry = Gtk.Entry(placeholder_text=_("Profile name"), max_length=40)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("save", _("Save"))

        def save(_dialog, response):
            if response != "save":
                return
            try:
                desktopprofiles.save(entry.get_text())
                self._refresh_custom()
                toast(self, _("Profile saved"))
            except (ValueError, RuntimeError, OSError):
                toast(self, _("Enter a valid profile name"))
        dialog.connect("response", save)
        dialog.present(self.get_root())


class Desktop(Page):
    page_id = "desktop"
    title = _("Desktop & Dock")
    icon_name = "preferences-desktop-apps-symbolic"

    def build(self):
        self.s = settings.get()
        if self.s is None:
            self.group(_("Settings schema not installed"))
            return
        self._syncing = False

        layouts = self.group(_("Layout"), _("Start from a preset, then fine-tune below."))
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           max_children_per_line=4, min_children_per_line=2,
                           column_spacing=10, row_spacing=10)
        self.preset_buttons = {}
        first = None
        for key, p in PRESETS.items():
            btn = Gtk.ToggleButton(css_classes=["card", "layout-card"])
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          margin_top=14, margin_bottom=14, margin_start=10, margin_end=10)
            box.append(Gtk.Image(icon_name=p["icon"], pixel_size=36))
            box.append(Gtk.Label(label=_(p["title"]), css_classes=["heading"]))
            box.append(Gtk.Label(label=_(p["subtitle"]), wrap=True, justify=Gtk.Justification.CENTER,
                                 css_classes=["dim-label", "caption"], max_width_chars=18))
            btn.set_child(box)
            if first is None:
                first = btn
            else:
                btn.set_group(first)
            btn.connect("toggled", lambda b, k=key: b.get_active() and self._apply_preset(k))
            self.preset_buttons[key] = btn
            flow.append(btn)
        layouts.add(flow)

        bar = self.group(_("Top Bar"))
        self._combo(bar, _("Style"), "panel-style",
                    [("floating", _("Floating")), ("bar", _("Edge to edge"))])
        self._combo(bar, _("Position"), "panel-position",
                    [("top", _("Top")), ("bottom", _("Bottom"))])
        self._combo(bar, _("Clock"), "clock-position",
                    [("right", _("Right")), ("center", _("Center"))])
        self._scale(bar, _("Opacity"), "panel-opacity", 0.3, 1.0, 0.05, double=True)
        self._switch(bar, _("Show seconds"), "clock-show-seconds")
        self._switch(bar, _("System monitor"), "panel-system-monitor")
        self._switch(bar, _("Show Desktop button"), "show-desktop-button")

        widgets = self.group(_("Desktop Widgets"),
                             _("Clock, calendar, weather, system, Git projects, containers, "
                               "GPU, games and more, on the desktop under your windows."))
        self._switch(widgets, _("Show widgets"), "desktop-widgets")
        edit = Adw.ButtonRow(title=_("Edit Widgets…")) if hasattr(Adw, "ButtonRow") else None
        if edit is not None:
            edit.connect("activated", lambda *_: subprocess.Popen(
                ["aurora-shell", "edit-widgets"], start_new_session=True))
            widgets.add(edit)

        dock = self.group(_("Dock"))
        self._combo(dock, _("Position"), "dock-position",
                    [("bottom", _("Bottom")), ("left", _("Left")), ("right", _("Right")),
                     ("hidden", _("Hidden"))])
        self._combo(dock, _("Style"), "dock-style",
                    [("floating", _("Floating")), ("islands", _("Islands")),
                     ("panel", _("Full-width panel"))])
        self._scale(dock, _("Icon size"), "dock-icon-size", 24, 80, 2)
        self._switch(dock, _("Magnify icons on hover"), "dock-magnification")
        self._switch(dock, _("Automatically hide"), "dock-autohide")
        self._switch(dock, _("Show Trash"), "dock-show-trash")

        win = self.group(_("Windows"))
        self._combo(win, _("Buttons"), "window-buttons",
                    [("left", _("Left")), ("right", _("Right"))])
        self._combo(win, _("Button style"), "window-button-style",
                    [("traffic", _("Colored circles")), ("symbolic", _("Monochrome icons"))])
        self._scale(win, _("Corner radius"), "window-corner-radius", 0, 18, 1)
        self._scale(win, _("Gaps around snapped windows"), "window-gaps", 0, 24, 1)

        desk = self.group(_("Desktop"))
        self._switch(desk, _("Show files from the Desktop folder"), "desktop-icons")
        self._combo(desk, _("Icon position"), "desktop-icons-position",
                    [("left", _("Top left")), ("right", _("Top right"))])

        search = self.group(_("Super Key"))
        self._combo(search, _("Super opens"), "launcher-style",
                    [("spotlight", _("Spotlight search")), ("grid", _("Launchpad (all apps)"))])

        results = self.group(_("Search Results"), _("What Spotlight shows as you type."))
        for key, title in (("apps", _("Apps")), ("files", _("Recent files")),
                           ("settings", _("Settings")), ("projects", _("Code projects")),
                           ("calculator", _("Calculator")),
                           ("convert", _("Unit and currency conversion")),
                           ("ai", _("Ask Aurora AI")), ("web", _("Web search"))):
            def toggle(on, key=key):
                off = [k for k in self.s.get_strv("search-disabled") if k != key]
                self.s.set_strv("search-disabled", off if on else off + [key])
            results.add(switch_row(title, key not in self.s.get_strv("search-disabled"), toggle))

        self._sync_presets()

    # --- helpers ---

    def _changed(self, key):
        if key in LOOK_KEYS:
            look.apply()
        if not self._syncing and key not in ("clock-show-seconds", "desktop-icons",
                                                    "desktop-icons-position",
                                                    "panel-system-monitor",
                                                    "show-desktop-button",
                                                    "desktop-widgets"):
            self.s.set_string("layout", "custom")
            self._sync_presets()

    def _combo(self, group, title, key, options):
        ids = [o[0] for o in options]
        current = self.s.get_string(key)

        def changed(i):
            self.s.set_string(key, ids[i])
            self._changed(key)
        row = combo_row(title, [o[1] for o in options], ids.index(current) if current in ids else 0,
                        on_change=changed)
        group.add(row)

    def _switch(self, group, title, key):
        def changed(v):
            self.s.set_boolean(key, v)
            self._changed(key)
        group.add(switch_row(title, self.s.get_boolean(key), changed))

    def _scale(self, group, title, key, lo, hi, step, double=False):
        row = Adw.ActionRow(title=title)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        scale.set_size_request(240, -1)
        scale.set_valign(Gtk.Align.CENTER)
        scale.set_value(self.s.get_double(key) if double else self.s.get_int(key))
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.LEFT)
        scale.set_digits(2 if double else 0)
        # With its unit: the opacity read "0.78", the sizes a bare number.
        if hasattr(scale, "set_format_value_func"):
            scale.set_format_value_func(
                (lambda _s, v: f"{v * 100:.0f}%") if double else (lambda _s, v: f"{int(v)} px"))

        def changed(sc):
            if double:
                self.s.set_double(key, round(sc.get_value(), 2))
            else:
                self.s.set_int(key, int(sc.get_value()))
            self._changed(key)
        scale.connect("value-changed", changed)
        row.add_suffix(scale)
        group.add(row)

    def _apply_preset(self, key):
        if self._syncing:
            return
        self._syncing = True
        for k, v in PRESETS[key]["values"].items():
            if isinstance(v, bool):
                self.s.set_boolean(k, v)
            elif isinstance(v, int):
                self.s.set_int(k, v)
            elif isinstance(v, float):
                self.s.set_double(k, v)
            else:
                self.s.set_string(k, v)
        self.s.set_string("layout", key)
        look.apply()
        self._syncing = False
        # Rebuild rows so they show the preset's values.
        self._rebuild()

    def _rebuild(self):
        parent = self.get_parent()
        if parent is None:
            return
        fresh = Desktop()
        stack = parent
        name = stack.get_page(self).get_name() if isinstance(stack, Gtk.Stack) else None
        if name:
            stack.remove(self)
            stack.add_named(fresh, name)
            stack.set_visible_child(fresh)
            root = fresh.get_root()
            if hasattr(root, "_pages"):
                root._pages[self.page_id] = fresh

    def _sync_presets(self):
        current = self.s.get_string("layout")
        self._syncing = True
        for key, btn in self.preset_buttons.items():
            btn.set_active(key == current)
        if current == "custom":
            for btn in self.preset_buttons.values():
                btn.set_active(False)
        self._syncing = False
