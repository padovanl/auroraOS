"""Clipboard: a window on everything you have copied.

Spotlight already searched the history (Super+V); this is the room with the
light on. Everything copied, newest first, pinned things at the top, with the
pictures among them; search, click to copy, pin what you keep reaching for,
delete one entry or empty the lot.

Copying hands the text to wl-copy rather than to this window's own clipboard:
a Wayland client owns its selection only while it lives, and this window is
meant to be closed straight after you take something out of it.

    aurora-clipboard show      open this window
"""

import os
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from aurora import clipboard  # noqa: E402
from aurora.i18n import _  # noqa: E402

PREVIEW_LINES = 3
PREVIEW_CHARS = 220

CSS = """
.clip-row { padding: 10px 6px 10px 12px; }
.clip-text { font-size: 1.0em; }
.clip-mono { font-family: monospace; font-size: 0.95em; }
.clip-shot { border-radius: 8px; border: 1px solid alpha(currentColor, 0.15); }
.clip-when { font-size: 0.82em; }
/* The two buttons stay out of the way until the row is under the pointer or
   holds the keyboard focus; a pinned entry keeps its pin lit. */
.clip-row button { opacity: 0.4; transition: opacity 120ms ease; }
.clip-row:hover button, .clip-row:focus-within button, .clip-row button:hover,
.clip-row button:checked { opacity: 1; }
"""


def when(seconds):
    """'just now', '12 minutes ago', 'yesterday' — the age of an entry."""
    if not seconds:
        return ""
    age = max(0, time.time() - seconds)
    if age < 60:
        return _("just now")
    if age < 3600:
        n = int(age // 60)
        return _("{n} min ago").format(n=n)
    if age < 86400:
        n = int(age // 3600)
        return _("{n} h ago").format(n=n)
    if age < 172800:
        return _("yesterday")
    return _("{n} days ago").format(n=int(age // 86400))


def looks_like_code(text):
    """Code and paths read better in a monospace font."""
    if "\n" in text.strip():
        lines = [line for line in text.splitlines() if line.strip()]
        indented = sum(1 for line in lines if line[:1] in (" ", "\t"))
        if lines and indented >= max(1, len(lines) // 3):
            return True
    sample = text.strip()
    return (sample.startswith(("/", "~/", "./", "http://", "https://", "{", "[", "<", "$ "))
            or any(token in sample for token in ("();", " => ", "def ", "function ", "SELECT ")))


def copy_text(text):
    """Hand the text to wl-copy, which keeps serving it after we are gone."""
    try:
        subprocess.run(["wl-copy", "--"], input=text.encode(), check=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        display = Gdk.Display.get_default()
        if display is not None:
            display.get_clipboard().set(text)       # at least while this window lives
        return False


def copy_image(path):
    try:
        with open(path, "rb") as image:
            subprocess.run(["wl-copy", "--type", "image/png"], stdin=image, check=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


class Entry:
    """One thing in the history: a piece of text, or a picture."""

    def __init__(self, text=None, path=None, pinned=False, stamp=0):
        self.text = text
        self.path = path
        self.pinned = pinned
        self.stamp = stamp

    @property
    def is_image(self):
        return self.path is not None

    def matches(self, query):
        if not query:
            return True
        if self.is_image:
            return query in _("Image").lower()
        return query in self.text.lower()

    def copy(self):
        return copy_image(self.path) if self.is_image else copy_text(self.text)

    def forget(self):
        if self.is_image:
            try:
                os.remove(self.path)
            except OSError:
                pass
        else:
            clipboard.delete(self.text)


def history():
    """Everything, pinned first, each with its age."""
    entries = []
    for text, info in clipboard.entries():
        entries.append(Entry(text=text, pinned=info["pinned"], stamp=info["time"]))
    for path in clipboard.image_paths():
        try:
            entries.append(Entry(path=path, stamp=os.path.getmtime(path)))
        except OSError:
            continue
    entries.sort(key=lambda e: (not e.pinned, -(e.stamp or 0)))
    return entries


class Row(Gtk.ListBoxRow):
    def __init__(self, window, entry):
        super().__init__(css_classes=["clip-row"])
        self.entry = entry
        box = Gtk.Box(spacing=12)
        if entry.is_image:
            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
            try:
                texture = Gdk.Texture.new_from_filename(entry.path)
            except GLib.Error:
                texture = None
            if texture is not None:
                shot = Gtk.Picture(paintable=texture, content_fit=Gtk.ContentFit.CONTAIN,
                                   can_shrink=True, height_request=104,
                                   halign=Gtk.Align.START)
                framed = Gtk.Box(css_classes=["clip-shot"], overflow=Gtk.Overflow.HIDDEN,
                                 halign=Gtk.Align.START)
                framed.append(shot)
                body.append(framed)
            body.append(Gtk.Label(label=_("Image"), halign=Gtk.Align.START,
                                  css_classes=["dim-label", "clip-when"]))
            box.append(body)
        else:
            text = entry.text
            shown = "\n".join(text.splitlines()[:PREVIEW_LINES])[:PREVIEW_CHARS]
            label = Gtk.Label(label=shown or text[:PREVIEW_CHARS], xalign=0, hexpand=True,
                              wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, lines=PREVIEW_LINES,
                              ellipsize=Pango.EllipsizeMode.END, halign=Gtk.Align.START,
                              css_classes=["clip-mono" if looks_like_code(text) else "clip-text"])
            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            body.append(label)
            lines = text.count("\n") + 1
            detail = when(entry.stamp)
            if lines > 1:
                detail = " · ".join(x for x in (detail, _("{n} lines").format(n=lines)) if x)
            if detail:
                body.append(Gtk.Label(label=detail, xalign=0, halign=Gtk.Align.START,
                                      css_classes=["dim-label", "clip-when"]))
            box.append(body)

        pin = Gtk.ToggleButton(icon_name="view-pin-symbolic", active=entry.pinned,
                               css_classes=["flat"], valign=Gtk.Align.CENTER,
                               tooltip_text=_("Keep at the top"))
        if not Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).has_icon(
                "view-pin-symbolic"):
            pin.set_icon_name("starred-symbolic")
        pin.connect("toggled", lambda button: window.set_pinned(entry, button.get_active()))
        if entry.is_image:
            pin.set_visible(False)      # pins live in the text history's own store
        delete = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat"],
                            valign=Gtk.Align.CENTER, tooltip_text=_("Remove from history"))
        delete.connect("clicked", lambda *_a: window.forget(entry))
        box.append(pin)
        box.append(delete)
        self.set_child(box)


class ClipboardWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Clipboard"),
                         default_width=560, default_height=680)
        self.toasts = Adw.ToastOverlay()
        self.search = Gtk.SearchEntry(placeholder_text=_("Search what you copied"),
                                      hexpand=True)
        self.search.connect("search-changed", lambda *_a: self.refresh())
        self.search.connect("activate", lambda *_a: self._take_first())

        menu = Gio.Menu()
        menu.append(_("Empty History"), "win.clear")
        menu.append(_("Clipboard Settings…"), "win.settings")
        header = Adw.HeaderBar()
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       tooltip_text=_("Menu")))

        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                css_classes=["boxed-list"], valign=Gtk.Align.START,
                                margin_top=12, margin_bottom=12,
                                margin_start=12, margin_end=12)
        self.list.connect("row-activated", lambda _l, row: self.take(row.entry))
        self.scroller = Gtk.ScrolledWindow(child=self.list, vexpand=True,
                                           hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.empty = Adw.StatusPage(icon_name="edit-paste-symbolic",
                                    title=_("Nothing copied yet"),
                                    description=_("Whatever you copy shows up here. "
                                                  "Turn the history off in Settings → Privacy."))
        self.stack = Gtk.Stack()
        self.stack.add_named(self.scroller, "list")
        self.stack.add_named(self.empty, "empty")

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bar = Gtk.Box(margin_top=8, margin_bottom=4, margin_start=12, margin_end=12)
        bar.append(self.search)
        body.append(bar)
        body.append(self.stack)
        view = Adw.ToolbarView(content=body)
        view.add_top_bar(header)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        for name, callback in (("clear", self._confirm_clear), ("settings", self._settings)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_a, cb=callback: cb())
            self.add_action(action)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        self._watch()
        self.refresh()
        self.search.grab_focus()

    # --- the list ---

    def refresh(self):
        query = self.search.get_text().strip().lower()
        entries = [e for e in history() if e.matches(query)]
        self.list.remove_all()
        for entry in entries:
            self.list.append(Row(self, entry))
        everything = bool(history())
        self.stack.set_visible_child_name("list" if entries else "empty")
        if not everything:
            self.empty.set_title(_("Nothing copied yet"))
        elif not entries:
            self.empty.set_title(_("No matches"))
        row = self.list.get_row_at_index(0)
        if row is not None:
            self.list.select_row(row)

    def _watch(self):
        """Follow the history file, so a copy made elsewhere shows up here."""
        try:
            path = Gio.File.new_for_path(clipboard.history_path())
            self._monitor = path.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self._monitor.connect("changed", lambda *_a: self._later())
        except GLib.Error:
            self._monitor = None
        self._pending = 0

    def _later(self):
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(300, lambda: (self.refresh(), False)[1])

    # --- using it ---

    def take(self, entry):
        if entry.copy():
            self.toasts.add_toast(Adw.Toast(title=_("Copied"), timeout=1))
        else:
            self.toasts.add_toast(Adw.Toast(title=_("Could not copy that"), timeout=3))
        GLib.timeout_add(220, lambda: (self.close(), False)[1])

    def _take_first(self):
        row = self.list.get_selected_row() or self.list.get_row_at_index(0)
        if row is not None:
            self.take(row.entry)

    def set_pinned(self, entry, value):
        if not entry.is_image and clipboard.pin(entry.text, value):
            entry.pinned = value
            self._later()

    def forget(self, entry):
        entry.forget()
        self.refresh()

    def _confirm_clear(self):
        dialog = Adw.MessageDialog(transient_for=self, modal=True,
                                   heading=_("Empty the clipboard history?"),
                                   body=_("Everything copied, pinned entries and pictures "
                                          "included, is forgotten. This cannot be undone."))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("clear", _("Empty History"))
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.connect("response", lambda _d, response: response == "clear" and
                       (clipboard.clear(), self.refresh()))
        dialog.present()

    def _settings(self):
        try:
            subprocess.Popen(["aurora-settings", "privacy"], start_new_session=True)
        except OSError as err:
            print(f"aurora: could not open Settings: {err}")

    def _on_key(self, _ctrl, keyval, _code, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace) and not self.search.has_focus():
            row = self.list.get_selected_row()
            if row is not None:
                self.forget(row.entry)
                return True
        if keyval == Gdk.KEY_f and state & Gdk.ModifierType.CONTROL_MASK:
            self.search.grab_focus()
            return True
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Clipboard")

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        window = self.props.active_window or ClipboardWindow(self)
        window.present()


def main():
    return App().run(sys.argv[:1])
