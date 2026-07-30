"""Quick Look: preview a file without opening an app (Space in Files).

Images, video and audio, PDF (first pages), text and source code (with syntax
highlighting), folders, and a summary card for anything else. Left/Right
move to the neighbouring file, Space or Escape close the preview.

Also runs on its own: `aurora-quicklook FILE...`.
"""

import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from aurora.i18n import _, ngettext  # noqa: E402

TEXT_LIMIT = 512 * 1024       # bytes of a text file shown in the preview
PDF_PAGES = 8                 # pages rendered for a PDF
ATTRS = ",".join(("standard::*", "time::modified", "thumbnail::path"))


def _kind(content_type):
    """The previewer for a content type: image, media, pdf, text or None."""
    ct = content_type or ""
    if Gio.content_type_is_a(ct, "image/*") or ct.startswith("image/"):
        return "image"
    if ct.startswith(("video/", "audio/")):
        return "media"
    if ct == "application/pdf":
        return "pdf"
    if Gio.content_type_is_a(ct, "text/plain") or ct in (
            "application/json", "application/xml", "application/javascript",
            "application/x-shellscript", "application/toml", "application/x-yaml",
            "application/sql", "application/x-desktop", "application/x-php"):
        return "text"
    return None


def _human_size(n):
    return GLib.format_size(n)


class QuickLook(Adw.Window):
    """A borderless-looking preview window over a list of files."""

    def __init__(self, files, index=0, parent=None, on_move=None):
        super().__init__(default_width=900, default_height=640, modal=False)
        self.add_css_class("quicklook")
        if parent is not None:
            self.set_transient_for(parent)
        self.files = list(files)
        self.index = index
        self.on_move = on_move        # called with the new index when the user browses
        self._media = None

        self.title = Adw.WindowTitle()
        header = Adw.HeaderBar(title_widget=self.title)
        self.open_btn = Gtk.Button(css_classes=["suggested-action"])
        self.open_btn.connect("clicked", lambda *_: self._open())
        header.pack_end(self.open_btn)
        nav = Gtk.Box(css_classes=["linked"])
        for icon, step, tip in (("go-previous-symbolic", -1, _("Previous")),
                                ("go-next-symbolic", 1, _("Next"))):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.connect("clicked", lambda _b, s=step: self.move(s))
            nav.append(b)
        header.pack_start(nav)
        self.nav = nav

        self.body = Adw.Bin(vexpand=True, hexpand=True)
        view = Adw.ToolbarView(content=self.body)
        view.add_top_bar(header)
        self.set_content(view)

        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.connect("close-request", lambda *_: self._stop_media() or False)
        self.show_file()

    # --- navigation ---

    def _on_key(self, _ctrl, keyval, _code, state):
        if keyval in (Gdk.KEY_space, Gdk.KEY_Escape):
            self.close()
            return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Up):
            self.move(-1)
            return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Down):
            self.move(1)
            return True
        if keyval == Gdk.KEY_Return:
            self._open()
            return True
        return False

    def move(self, step):
        if len(self.files) < 2:
            return
        self.index = (self.index + step) % len(self.files)
        if self.on_move:
            self.on_move(self.index)
        self.show_file()

    def set_files(self, files, index):
        self.files, self.index = list(files), index
        self.show_file()

    def _open(self):
        gfile = self.files[self.index]
        launcher = Gtk.FileLauncher(file=gfile)
        launcher.launch(self.get_transient_for() or self, None, None)
        self.close()

    # --- content ---

    def show_file(self):
        self._stop_media()
        gfile = self.files[self.index]
        self.nav.set_visible(len(self.files) > 1)
        try:
            info = gfile.query_info(ATTRS, Gio.FileQueryInfoFlags.NONE, None)
        except GLib.Error as e:
            self.title.set_title(gfile.get_basename() or "")
            self.body.set_child(Adw.StatusPage(icon_name="dialog-error-symbolic",
                                               title=_("Can’t Preview"), description=e.message))
            return
        name = info.get_display_name()
        ct = info.get_content_type() or ""
        self.title.set_title(name)
        self.title.set_subtitle(Gio.content_type_get_description(ct) +
                                ("" if info.get_file_type() == Gio.FileType.DIRECTORY
                                 else " · " + _human_size(info.get_size())))
        app = Gio.AppInfo.get_default_for_type(ct, False) if ct else None
        self.open_btn.set_label(_("Open with {app}").format(app=app.get_display_name())
                                if app else _("Open"))

        widget = None
        if info.get_file_type() == Gio.FileType.DIRECTORY:
            widget = self._folder(gfile, info)
        else:
            kind = _kind(ct)
            try:
                if kind == "image":
                    widget = self._image(gfile)
                elif kind == "media":
                    widget = self._video(gfile)
                elif kind == "pdf":
                    widget = self._pdf(gfile)
                elif kind == "text":
                    widget = self._text(gfile, name, ct)
            except (GLib.Error, OSError, ValueError, ImportError):
                widget = None
            if widget is None:
                widget = self._summary(info)
        self.body.set_child(widget)

    def _stop_media(self):
        if self._media is not None:
            stream = self._media.get_media_stream()
            if stream is not None:
                stream.set_playing(False)
            self._media = None

    def _image(self, gfile):
        texture = Gdk.Texture.new_from_file(gfile)
        return Gtk.Picture(paintable=texture, content_fit=Gtk.ContentFit.CONTAIN,
                           can_shrink=True, margin_top=12, margin_bottom=12,
                           margin_start=12, margin_end=12)

    def _video(self, gfile):
        video = Gtk.Video(file=gfile, autoplay=True)
        self._media = video
        return video

    def _pdf(self, gfile):
        gi.require_version("Poppler", "0.18")
        from gi.repository import Poppler
        doc = Poppler.Document.new_from_gfile(gfile, None, None)
        pages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                        margin_top=16, margin_bottom=16, halign=Gtk.Align.CENTER)
        for i in range(min(doc.get_n_pages(), PDF_PAGES)):
            page = doc.get_page(i)
            w, h = page.get_size()
            area = Gtk.DrawingArea(content_width=int(w * 1.2), content_height=int(h * 1.2),
                                   css_classes=["quicklook-page"])

            def draw(_a, cr, aw, ah, page=page, w=w):
                cr.set_source_rgb(1, 1, 1)
                cr.paint()
                cr.scale(aw / w, aw / w)
                page.render(cr)
            area.set_draw_func(draw)
            pages.append(area)
        if doc.get_n_pages() > PDF_PAGES:
            pages.append(Gtk.Label(label=_("{n} more pages").format(
                n=doc.get_n_pages() - PDF_PAGES), css_classes=["dim-label"]))
        return Gtk.ScrolledWindow(child=pages, hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)

    def _text(self, gfile, name, ct):
        ok, data, _etag = gfile.load_contents(None)
        text = bytes(data[:TEXT_LIMIT]).decode("utf-8", errors="replace")
        if "\0" in text:
            raise ValueError("binary")
        try:
            gi.require_version("GtkSource", "5")
            from gi.repository import GtkSource
            GtkSource.init()
            buf = GtkSource.Buffer()
            lang = GtkSource.LanguageManager.get_default().guess_language(name, ct)
            if lang is not None:
                buf.set_language(lang)
            dark = Adw.StyleManager.get_default().get_dark()
            scheme = GtkSource.StyleSchemeManager.get_default().get_scheme(
                "Adwaita-dark" if dark else "Adwaita")
            if scheme is not None:
                buf.set_style_scheme(scheme)
            view = GtkSource.View(buffer=buf, show_line_numbers=True, monospace=True)
        except (ValueError, ImportError):
            buf = Gtk.TextBuffer()
            view = Gtk.TextView(buffer=buf, monospace=True)
        buf.set_text(text)
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        for side in ("top", "bottom", "left", "right"):
            getattr(view, f"set_{side}_margin")(12)
        return Gtk.ScrolledWindow(child=view)

    def _folder(self, gfile, info):
        count = 0
        try:
            enum = gfile.enumerate_children("standard::name", Gio.FileQueryInfoFlags.NONE, None)
            while enum.next_file(None) is not None:
                count += 1
        except GLib.Error:
            pass
        page = Adw.StatusPage(gicon=info.get_icon(), title=info.get_display_name(),
                              description=ngettext("{n} item", "{n} items", count).format(n=count))
        return page

    def _summary(self, info):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        thumb = info.get_attribute_byte_string("thumbnail::path")
        if thumb and os.path.exists(thumb):
            box.append(Gtk.Picture(file=Gio.File.new_for_path(thumb), can_shrink=True,
                                   content_fit=Gtk.ContentFit.CONTAIN,
                                   height_request=256, width_request=256))
        else:
            box.append(Gtk.Image(gicon=info.get_icon(), pixel_size=128))
        box.append(Gtk.Label(label=info.get_display_name(), css_classes=["title-2"],
                             wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                             justify=Gtk.Justification.CENTER))
        details = [Gio.content_type_get_description(info.get_content_type() or ""),
                   _human_size(info.get_size())]
        mtime = info.get_modification_date_time()
        if mtime is not None:
            details.append(_("Modified {date}").format(
                date=mtime.to_local().format("%x %H:%M")))
        box.append(Gtk.Label(label=" · ".join(details), css_classes=["dim-label"]))
        return box


class QuickLookApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.QuickLook",
                         flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE)

    def do_open(self, files, _n, _hint):
        win = QuickLook(files)
        win.set_application(self)
        win.present()

    def do_activate(self):
        print("usage: aurora-quicklook FILE...", file=sys.stderr)


def main():
    return QuickLookApp().run(sys.argv)
