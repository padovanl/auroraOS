"""File properties dialog."""

import os
import stat
import threading

from gi.repository import Adw, Gio, GLib, Gtk

from aurora.i18n import _


def _dir_size(path, cancel):
    total, count = 0, 0
    for root, dirs, files in os.walk(path):
        if cancel.is_set():
            break
        count += len(files) + len(dirs)
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total, count


class PropertiesDialog(Adw.Dialog):
    def __init__(self, files):
        super().__init__(title=_("Properties"), content_width=420)
        self._cancel = threading.Event()
        self.connect("closed", lambda *_: self._cancel.set())

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(page)
        self.set_child(view)

        if len(files) == 1:
            self._single(group, files[0])
        else:
            group.set_title(_("{n} items").format(n=len(files)))
            self.size_row = self._row(group, _("Total size"), _("Calculating…"))
            paths = [f.get_path() for f in files if f.get_path()]
            threading.Thread(target=self._measure, args=(paths,), daemon=True).start()

    def _row(self, group, title, value):
        row = Adw.ActionRow(title=title, subtitle=value or "—", subtitle_selectable=True)
        row.add_css_class("property")
        group.add(row)
        return row

    def _single(self, group, gfile):
        try:
            info = gfile.query_info("standard::*,time::*,unix::*,access::*",
                                    Gio.FileQueryInfoFlags.NONE, None)
        except GLib.Error as err:
            self._row(group, _("Error"), err.message)
            return
        icon = Gtk.Image(gicon=info.get_icon(), pixel_size=96, margin_bottom=12)
        group.set_header_suffix(None)
        group.add(icon)
        self._row(group, _("Name"), info.get_display_name())
        ctype = info.get_content_type() or ""
        self._row(group, _("Type"), Gio.content_type_get_description(ctype) if ctype else "")
        path = gfile.get_path()
        self._row(group, _("Location"), os.path.dirname(path) if path else gfile.get_uri())
        if info.get_file_type() == Gio.FileType.DIRECTORY and path:
            self.size_row = self._row(group, _("Contents"), _("Calculating…"))
            threading.Thread(target=self._measure, args=([path],), daemon=True).start()
        else:
            self._row(group, _("Size"), GLib.format_size(info.get_size()))
        dt = info.get_modification_date_time()
        if dt:
            self._row(group, _("Modified"), dt.to_local().format("%c"))
        dt = info.get_access_date_time()
        if dt:
            self._row(group, _("Accessed"), dt.to_local().format("%c"))
        if info.has_attribute("unix::mode"):
            mode = info.get_attribute_uint32("unix::mode")
            owner = info.get_attribute_string("owner::user") or \
                str(info.get_attribute_uint32("unix::uid"))
            self._row(group, _("Permissions"), f"{stat.filemode(mode)}  ({owner})")

    def _measure(self, paths):
        total, count = 0, 0
        for p in paths:
            if os.path.isdir(p) and not os.path.islink(p):
                t, c = _dir_size(p, self._cancel)
                total += t
                count += c
            else:
                try:
                    total += os.lstat(p).st_size
                except OSError:
                    pass
                count += 1
        text = _("{size} · {n} items").format(size=GLib.format_size(total), n=count)
        GLib.idle_add(self.size_row.set_subtitle, text)
