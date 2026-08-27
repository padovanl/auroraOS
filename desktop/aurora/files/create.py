"""Create files and folders without overwriting existing entries."""

from gi.repository import Adw, Gio, GLib, Gtk

from aurora.i18n import _


class NewItemDialog(Adw.Window):
    def __init__(self, app, directory, parent=None, folder=False):
        super().__init__(application=app, title=_("New Folder") if folder else _("New File"),
                         default_width=380, resizable=False, modal=True)
        if parent is not None:
            self.set_transient_for(parent)
        self.directory = directory
        self.folder = folder
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_top=12, margin_bottom=20, margin_start=20, margin_end=20)
        content.append(Gtk.Label(label=_("Name") if folder else _("File name"), xalign=0))
        self.entry = Gtk.Entry(text=_("Untitled Folder") if folder else _("Untitled.txt"),
                               activates_default=True)
        content.append(self.entry)
        self.error = Gtk.Label(wrap=True, xalign=0, visible=False, css_classes=["error"])
        content.append(self.error)
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda *_: self.close())
        self.create_button = Gtk.Button(label=_("Create"), css_classes=["suggested-action"])
        self.create_button.connect("clicked", self._create)
        buttons.append(cancel)
        buttons.append(self.create_button)
        content.append(buttons)
        toolbar = Adw.ToolbarView(content=content)
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_content(toolbar)
        self.set_default_widget(self.create_button)
        self.entry.connect("changed", self._validate)
        self._validate()
        self.entry.grab_focus()
        self.entry.select_region(0, len(self.entry.get_text().rsplit(".", 1)[0]))

    def _validate(self, *_):
        name = self.entry.get_text().strip()
        self.create_button.set_sensitive(bool(name) and name not in (".", "..") and "/" not in name)
        self.error.set_visible(False)

    def _create(self, *_):
        if not self.create_button.get_sensitive():
            return
        try:
            target = self.directory.get_child(self.entry.get_text().strip())
            if self.folder:
                target.make_directory(None)
            else:
                stream = target.create(Gio.FileCreateFlags.NONE, None)
                stream.close(None)
        except GLib.Error as err:
            self.error.set_label(err.message)
            self.error.set_visible(True)
            return
        self.close()
