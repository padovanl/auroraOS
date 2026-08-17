"""Small helpers shared by settings pages."""

import subprocess

from gi.repository import Adw, GLib, Gtk


def run(argv, check=False):
    """Run a command, returning stdout ('' on failure)."""
    try:
        res = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if check and res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"{argv[0]} failed")
    return res.stdout


def string_list(items):
    return Gtk.StringList.new(list(items))


def combo_row(title, labels, selected=0, subtitle=None, on_change=None, search=False):
    row = Adw.ComboRow(title=title, model=string_list(labels), enable_search=search,
                       use_markup=False)
    if subtitle:
        row.set_subtitle(subtitle)
    if 0 <= selected < len(labels):
        row.set_selected(selected)
    if on_change:
        row.connect("notify::selected", lambda r, _p: on_change(r.get_selected()))
    return row


def switch_row(title, active, on_change, subtitle=None):
    row = Adw.SwitchRow(title=title, active=active, use_markup=False)
    if subtitle:
        row.set_subtitle(subtitle)
    row.connect("notify::active", lambda r, _p: on_change(r.get_active()))
    return row


def toast(widget, message):
    """Show a toast in the window's overlay, if there is one."""
    root = widget.get_root()
    overlay = getattr(root, "toast_overlay", None)
    if overlay is not None:
        overlay.add_toast(Adw.Toast(title=message, timeout=3))


def plain_text(widget):
    """Show row titles as written: Adwaita reads them as markup, where an "&"
    (as in "Date & Time") makes the text disappear."""
    if isinstance(widget, Adw.PreferencesRow):
        widget.set_use_markup(False)
    child = widget.get_first_child()
    while child is not None:
        plain_text(child)
        child = child.get_next_sibling()


class Page(Adw.PreferencesPage):
    """Base class for a settings page registered in the sidebar."""

    page_id = ""
    title = ""
    icon_name = ""

    def __init__(self):
        super().__init__(title=self.title, icon_name=self.icon_name)
        self.build()
        plain_text(self)

    def build(self):
        raise NotImplementedError

    def group(self, title=None, description=None):
        g = Adw.PreferencesGroup()
        # Group titles are markup: an "&" (in "Date & Time") would hide the text.
        if title:
            g.set_title(GLib.markup_escape_text(title))
        if description:
            g.set_description(GLib.markup_escape_text(description))
        self.add(g)
        return g
