"""Aurora Assistant: chat with the AI (local or the cloud provider you chose).

    aurora-assistant                 open the window
    aurora-assistant --ask TEXT      open it and ask (Spotlight's "?" uses this)

Quick actions work on the clipboard: summarize, improve the writing,
translate, explain. Answers stream in; code blocks get a Copy button, and
answers can be read aloud when that feature is installed.
"""

import re
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from aurora import VERSION, ai, apps  # noqa: E402
from aurora.i18n import _  # noqa: E402

CSS = """
.bubble { border-radius: 16px; padding: 10px 14px; }
.bubble.user { background-color: alpha(@accent_bg_color, 0.85); color: @accent_fg_color; }
.bubble.assistant { background-color: alpha(currentColor, 0.06); }
.codeblock { border-radius: 10px; background-color: alpha(currentColor, 0.08); }
.codeblock textview { background: transparent; font-family: monospace; }
.quick-actions button { border-radius: 999px; }
"""

CODE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.S)


def _markup(text):
    """A little Markdown: **bold**, `code`, headings and bullets, safely escaped."""
    out = GLib.markup_escape_text(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"`([^`]+)`", r"<tt>\1</tt>", out)
    out = re.sub(r"(?m)^#{1,4} (.+)$", r"<b>\1</b>", out)
    out = re.sub(r"(?m)^[-*] ", "• ", out)
    return out


class Message(Gtk.Box):
    def __init__(self, role, text=""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                         halign=Gtk.Align.END if role == "user" else Gtk.Align.FILL,
                         margin_start=48 if role == "user" else 0,
                         margin_end=0 if role == "user" else 24)
        self.role = role
        self.text = text
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                            css_classes=["bubble", role])
        self.append(self.body)
        self.actions = Gtk.Box(spacing=4, visible=False)
        self.append(self.actions)
        self.render(streaming=False)

    def set_text(self, text, streaming=True):
        self.text = text
        self.render(streaming)

    def render(self, streaming):
        while (c := self.body.get_first_child()) is not None:
            self.body.remove(c)
        if streaming or self.role == "user":
            self.body.append(self._label(self.text or "…", plain=True))
            return
        pos = 0
        for m in CODE.finditer(self.text):
            if self.text[pos:m.start()].strip():
                self.body.append(self._label(self.text[pos:m.start()].strip()))
            self.body.append(self._code(m.group(1).rstrip()))
            pos = m.end()
        if self.text[pos:].strip():
            self.body.append(self._label(self.text[pos:].strip()))

    def _label(self, text, plain=False):
        label = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                          selectable=True)
        if plain:
            label.set_text(text)
        else:
            label.set_markup(_markup(text))
        return label

    def _code(self, code):
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["codeblock"])
        view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                            top_margin=8, bottom_margin=4, left_margin=10, right_margin=10)
        view.get_buffer().set_text(code)
        frame.append(view)
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text=_("Copy"),
                          halign=Gtk.Align.END, css_classes=["flat", "circular"],
                          margin_end=4, margin_bottom=4)
        copy.connect("clicked", lambda *_: Gdk.Display.get_default().get_clipboard().set(code))
        frame.append(copy)
        return frame


class AssistantWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Aurora Assistant"),
                         default_width=560, default_height=700)
        self.history = []
        self.busy = False
        self.title = Adw.WindowTitle(title=_("Aurora Assistant"))
        header = Adw.HeaderBar(title_widget=self.title)
        new = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("New Chat"))
        new.connect("clicked", lambda *_: self.new_chat())
        header.pack_start(new)
        prefs = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text=_("AI Settings"))
        prefs.connect("clicked", lambda *_: apps.spawn(["aurora-settings", "--page", "ai"]))
        header.pack_end(prefs)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        off = Adw.StatusPage(icon_name="aurora-assistant-symbolic", title=_("Aurora AI is off"),
                             description=_("Turn it on in Settings → AI. It runs on this "
                                           "computer, or with the cloud provider you choose."))
        open_btn = Gtk.Button(label=_("Open AI Settings"), halign=Gtk.Align.CENTER,
                              css_classes=["pill", "suggested-action"])
        open_btn.connect("clicked", lambda *_: apps.spawn(["aurora-settings", "--page", "ai"]))
        off.set_child(open_btn)
        self.stack.add_named(off, "off")

        chat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=16,
                            margin_bottom=16, margin_start=16, margin_end=16)
        self.empty = Adw.StatusPage(icon_name="aurora-assistant-symbolic",
                                    title=_("How can I help?"),
                                    description=_("Ask anything, or pick an action for the "
                                                  "text you copied."))
        self.list.append(self.empty)
        self.scroller = Gtk.ScrolledWindow(child=self.list, vexpand=True,
                                           hscrollbar_policy=Gtk.PolicyType.NEVER)
        chat.append(self.scroller)

        quick = Gtk.Box(spacing=6, margin_start=12, margin_end=12, css_classes=["quick-actions"])
        for label, prompt in (
            (_("Summarize"), "Summarize this text in a few bullet points:\n\n{}"),
            (_("Improve Writing"), "Improve the writing of this text; keep its language "
                                   "and meaning, reply with the new text only:\n\n{}"),
            (_("Translate"), "Translate this text into {lang}; reply with the translation "
                             "only:\n\n{}"),
            (_("Explain"), "Explain this simply:\n\n{}"),
        ):
            b = Gtk.Button(label=label, css_classes=["flat"],
                           tooltip_text=_("Uses the text you copied"))
            b.connect("clicked", lambda _b, p=prompt: self.on_clipboard(p))
            quick.append(b)
        chat.append(quick)

        bar = Gtk.Box(spacing=8, margin_top=8, margin_bottom=12, margin_start=12, margin_end=12)
        self.entry = Gtk.Entry(hexpand=True, placeholder_text=_("Ask Aurora…"))
        self.entry.connect("activate", lambda *_: self.send(self.entry.get_text()))
        bar.append(self.entry)
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic", css_classes=["circular",
                                                                           "suggested-action"])
        self.send_btn.connect("clicked", lambda *_: self.send(self.entry.get_text()))
        bar.append(self.send_btn)
        chat.append(bar)
        self.stack.add_named(chat, "chat")

        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(header)
        self.set_content(view)
        self.refresh()

    def refresh(self):
        on = ai.enabled()
        self.stack.set_visible_child_name("chat" if on else "off")
        which = ai.provider()
        label = {"local": _("On this computer"), "anthropic": "Claude",
                 "openai": _("OpenAI-compatible")}.get(which, which)
        self.title.set_subtitle(label if on else "")

    def new_chat(self):
        self.history = []
        while (c := self.list.get_first_child()) is not None:
            self.list.remove(c)
        self.list.append(self.empty)

    def on_clipboard(self, prompt):
        def got(clip, res):
            try:
                text = clip.read_text_finish(res) or ""
            except GLib.Error:
                text = ""
            if not text.strip():
                toast = _("Copy some text first, then pick an action.")
                self.entry.set_placeholder_text(toast)
                return
            import locale
            lang = (locale.getlocale(locale.LC_MESSAGES)[0] or "en").split("_")[0]
            target = "English" if lang == "en" else f"the language with ISO code '{lang}'"
            self.send(prompt.replace("{lang}", target).format(text.strip()[:12000]))
        Gdk.Display.get_default().get_clipboard().read_text_async(None, got)

    def send(self, text):
        text = text.strip()
        if not text or self.busy:
            return
        self.refresh()
        if not ai.enabled():
            return
        self.entry.set_text("")
        if self.empty.get_parent() is not None:
            self.list.remove(self.empty)
        self.list.append(Message("user", text))
        reply = Message("assistant")
        self.list.append(reply)
        self.history.append({"role": "user", "content": text})
        self.busy = True
        self.send_btn.set_sensitive(False)
        threading.Thread(target=self._run, args=(reply,), daemon=True).start()

    def _run(self, reply):
        from aurora.ai.providers import ProviderError, chat
        parts = []
        error = None
        try:
            for piece in chat(self.history[-12:]):
                parts.append(piece)
                GLib.idle_add(reply.set_text, "".join(parts))
                GLib.idle_add(self._scroll_down)
        except ProviderError as e:
            error = str(e)
        GLib.idle_add(self._done, reply, "".join(parts), error)

    def _done(self, reply, text, error):
        self.busy = False
        self.send_btn.set_sensitive(True)
        if error:
            reply.set_text(_("Something went wrong: {error}").format(error=error), streaming=True)
            return False
        self.history.append({"role": "assistant", "content": text})
        reply.set_text(text, streaming=False)
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text=_("Copy"),
                          css_classes=["flat", "circular"])
        copy.connect("clicked", lambda *_: Gdk.Display.get_default().get_clipboard().set(text))
        reply.actions.append(copy)
        if ai.feature("read-aloud"):
            speak = Gtk.Button(icon_name="audio-speakers-symbolic", tooltip_text=_("Read Aloud"),
                               css_classes=["flat", "circular"])
            speak.connect("clicked", lambda *_: self._speak(text))
            reply.actions.append(speak)
        reply.actions.set_visible(True)
        self._scroll_down()
        return False

    def _speak(self, text):
        from aurora.ai import speech
        clean = CODE.sub("", text)
        threading.Thread(target=lambda: speech.speak(clean), daemon=True).start()

    def _scroll_down(self):
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False


class AssistantApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Assistant",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        if self.window is None:
            self.window = AssistantWindow(self)
        self.window.present()
        self.window.refresh()
        if args[:1] == ["--ask"] and len(args) > 1:
            self.window.send(" ".join(args[1:]))
        return 0


def main():
    return AssistantApp().run(sys.argv)


__all__ = ["main", "VERSION"]
