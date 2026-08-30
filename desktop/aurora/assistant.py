"""Aurora Assistant: chat with the AI (local or the cloud provider you chose).

    aurora-assistant                 open the window
    aurora-assistant --ask TEXT      open it and ask (Spotlight's "?" uses this)
    aurora-assistant --writing       writing tools for the selected text (Super+Shift+W)
    aurora-assistant --file PATH [--summarize]   ask about a file (Files' menu)

Quick actions work on the clipboard: summarize, improve the writing,
translate, explain. Answers stream in; code blocks get a Copy button, and
answers can be read aloud when that feature is installed.
"""

import re
import os
import sys
import threading
import uuid

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from aurora import VERSION, ai, apps  # noqa: E402
from aurora.ai import conversations  # noqa: E402
from aurora.i18n import N_, _  # noqa: E402

CSS = """
window.assistant-float { border-radius: 20px; }
window.assistant-float headerbar { min-height: 40px; }
.bubble { border-radius: 16px; padding: 10px 14px; }
.bubble.user { background-color: alpha(@accent_bg_color, 0.85); color: @accent_fg_color; }
.bubble.assistant { background-color: alpha(currentColor, 0.06); }
.codeblock { border-radius: 10px; background-color: alpha(currentColor, 0.08); }
.codeblock textview { background: transparent; font-family: monospace; }
.quick-actions button { border-radius: 999px; }
.quick-actions > flowboxchild { padding: 0; }
button.jump-latest { min-width: 42px; min-height: 42px; border-radius: 999px; margin: 4px; }
button.jump-latest.unread { background: @accent_bg_color; color: @accent_fg_color;
  box-shadow: 0 0 0 3px alpha(@accent_bg_color, 0.25); }
@keyframes aurora-jump-nudge {
  0%, 100% { transform: translateY(0); }
  30% { transform: translateY(-5px); }
  60% { transform: translateY(3px); }
}
button.jump-latest.unread image { animation: aurora-jump-nudge 0.7s ease-in-out 2; }
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


COMPACT = (400, 580)
# Screen height the window leaves free: the dock and a gap below it (the window
# rule puts it in the bottom-right corner, above the dock), the top bar above.
DOCK_ROOM, BAR_ROOM = 110, 46


def compact_height():
    """580 px, or less on a small screen, so the whole window stays visible."""
    display = Gdk.Display.get_default()
    monitors = display.get_monitors() if display else None
    if not monitors or monitors.get_n_items() == 0:
        return COMPACT[1]
    height = monitors.get_item(0).get_geometry().height
    return max(320, min(COMPACT[1], height - DOCK_ROOM - BAR_ROOM))


class AssistantWindow(Adw.ApplicationWindow):
    """A floating assistant, like a picture-in-picture video: it stays above other
    windows and on every workspace (a labwc window rule), in a corner, so it can stay
    open while you work elsewhere. Drag it by its bar; expand it for long answers."""

    def __init__(self, app):
        super().__init__(application=app, title=_("Aurora Assistant"),
                         default_width=COMPACT[0], default_height=compact_height())
        self.add_css_class("assistant-float")
        self.history = []
        self.busy = False
        self.conversation_id = uuid.uuid4().hex
        self.saved_conversations = conversations.load()
        self.stop_event = None
        self.follow_reply = True
        self.attachments = []
        self.current_reply = None
        self.title = Adw.WindowTitle(title=_("Aurora Assistant"))
        header = Adw.HeaderBar(title_widget=self.title, show_start_title_buttons=False,
                               show_end_title_buttons=False, css_classes=["flat"])
        new = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("New Chat"))
        new.connect("clicked", lambda *_: self.new_chat())
        header.pack_start(new)
        past = Gtk.Button(icon_name="document-open-recent-symbolic",
                          tooltip_text=_("Conversations"))
        past.connect("clicked", self._show_conversations)
        header.pack_start(past)
        close = Gtk.Button(icon_name="window-close-symbolic", tooltip_text=_("Close"),
                           css_classes=["circular"])
        close.connect("clicked", lambda *_: self.close())
        header.pack_end(close)
        self.expand_btn = Gtk.Button(icon_name="aurora-window-expand-symbolic",
                                     tooltip_text=_("Expand"))
        self.expand_btn.connect("clicked", lambda *_: self.toggle_size())
        self.connect("notify::maximized", self._on_maximized)
        header.pack_end(self.expand_btn)
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
        self.scroller.get_vadjustment().connect("changed", self._on_content_size)
        self.scroller.get_vadjustment().connect("value-changed", self._on_scroll_position)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_user_scroll)
        self.scroller.add_controller(scroll)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._drop_files)
        chat.add_controller(drop)
        self.latest = Gtk.Button(icon_name="go-down-symbolic",
                                 tooltip_text=_("Jump to latest"),
                                 halign=Gtk.Align.CENTER, visible=False,
                                 css_classes=["jump-latest"])
        self.latest.connect("clicked", lambda *_: self._resume_follow())
        chat.append(self.latest)

        # Wraps onto a second line when the window is narrow, never cut off.
        quick = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=4,
                            row_spacing=4, max_children_per_line=4, homogeneous=False,
                            margin_start=12, margin_end=12, css_classes=["quick-actions"])
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
        # FlowBox children take focus and hover highlight of their own; the
        # buttons already have both.
        child = quick.get_first_child()
        while child is not None:
            child.set_focusable(False)
            child = child.get_next_sibling()
        chat.append(quick)

        self.attachment_bar = Gtk.Box(spacing=6, margin_start=12, margin_end=12,
                                      visible=False)
        chat.append(self.attachment_bar)

        bar = Gtk.Box(spacing=8, margin_top=8, margin_bottom=12, margin_start=12, margin_end=12)
        self.entry = Gtk.Entry(hexpand=True, placeholder_text=_("Ask Aurora…"))
        self.entry.connect("activate", lambda *_: self.send(self.entry.get_text()))
        attach = Gtk.Button(icon_name="mail-attachment-symbolic",
                            tooltip_text=_("Attach files or photos"), css_classes=["flat"])
        attach.connect("clicked", lambda *_: self._choose_files())
        bar.append(attach)
        bar.append(self.entry)
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic", css_classes=["circular",
                                                                           "suggested-action"])
        self.send_btn.connect("clicked", lambda *_: self.send(self.entry.get_text()))
        bar.append(self.send_btn)
        self.stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic",
                                   tooltip_text=_("Stop generating"), visible=False,
                                   css_classes=["circular"])
        self.stop_btn.connect("clicked", lambda *_: self._stop())
        bar.append(self.stop_btn)
        chat.append(bar)
        self.stack.add_named(chat, "chat")

        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(header)
        self.set_content(view)
        self.refresh()

    def toggle_size(self):
        # The compositor remembers the corner and size, and puts it back.
        if self.is_maximized():
            self.unmaximize()
        else:
            self.maximize()

    def _on_maximized(self, *_a):
        big = self.is_maximized()
        self.expand_btn.set_icon_name("aurora-window-restore-symbolic" if big
                                      else "aurora-window-expand-symbolic")
        self.expand_btn.set_tooltip_text(_("Make Smaller") if big else _("Expand"))

    def refresh(self):
        on = ai.enabled()
        self.stack.set_visible_child_name("chat" if on else "off")
        which = ai.provider()
        label = {"local": _("On this computer"), "anthropic": "Claude",
                 "openai": _("OpenAI-compatible")}.get(which, which)
        self.title.set_subtitle(label if on else "")

    def attach_file(self, path, summarize=False):
        """Open a file from Files, keeping it visibly attached until the user sends."""
        self.new_chat()
        self._queue_file(path, summarize)

    def _choose_files(self):
        dialog = Gtk.FileDialog(title=_("Attach files or photos"))

        def chosen(file_dialog, result):
            try:
                files = file_dialog.open_multiple_finish(result)
            except GLib.Error:
                return
            for i in range(files.get_n_items()):
                path = files.get_item(i).get_path()
                if path:
                    self._queue_file(path)
        dialog.open_multiple(self, None, chosen)

    def _drop_files(self, _target, value, _x, _y):
        paths = [f.get_path() for f in value.get_files() if f.get_path()]
        for path in paths:
            self._queue_file(path)
        return bool(paths)

    def _queue_file(self, path, summarize=False):
        count = 0
        child = self.attachment_bar.get_first_child()
        while child is not None:
            count += 1
            child = child.get_next_sibling()
        if count >= 4:
            self.entry.set_placeholder_text(_("Up to four attachments per message"))
            return
        name = os.path.basename(path)
        try:
            readable = os.path.isfile(path) and os.path.getsize(path) <= 20 * 1024 * 1024
        except OSError:
            readable = False
        if not readable:
            self.entry.set_placeholder_text(_("Can't attach {name}").format(name=name))
            return
        chip = Gtk.Button(label=_("Reading {name}…").format(name=name),
                          css_classes=["pill"])
        self.attachment_bar.append(chip)
        self.attachment_bar.set_visible(True)

        def work():
            from aurora.ai.index import extract
            ext = os.path.splitext(path)[1].lower()
            try:
                if ext in (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"):
                    from aurora.ocr import recognize
                    content = recognize(path)
                    kind = "OCR"
                else:
                    content = extract(path)
                    kind = "text"
            except (OSError, RuntimeError) as err:
                content = ""
                print(f"aurora-assistant: attachment: {err}")
                kind = "text"
            GLib.idle_add(self._attachment_ready, chip, path, content, kind, summarize)
        threading.Thread(target=work, daemon=True).start()

    def _attachment_ready(self, chip, path, content, kind, summarize):
        if chip.get_parent() is not self.attachment_bar:
            return False
        name = os.path.basename(path)
        if not content.strip():
            self.attachment_bar.remove(chip)
            self.attachment_bar.set_visible(self.attachment_bar.get_first_child() is not None)
            self.entry.set_placeholder_text(_("Can't read text from {name}").format(name=name))
            return False
        attachment = {"name": name, "text": content[:16000], "kind": kind}
        self.attachments.append(attachment)
        chip.set_label("📷 " + name if kind == "OCR" else "📄 " + name)
        chip.set_tooltip_text(_("Remove attachment"))
        chip.connect("clicked", lambda *_: self._remove_attachment(attachment, chip))
        if summarize:
            self.send(_("Summarize this file in a few bullet points."))
        else:
            self.entry.set_placeholder_text(_("Ask about {name}…").format(name=name))
            self.entry.grab_focus()
        return False

    def _remove_attachment(self, attachment, chip):
        if attachment in self.attachments:
            self.attachments.remove(attachment)
        self.attachment_bar.remove(chip)
        self.attachment_bar.set_visible(self.attachment_bar.get_first_child() is not None)

    def new_chat(self):
        self._stop()
        self.history = []
        self.attachments = []
        while (c := self.attachment_bar.get_first_child()) is not None:
            self.attachment_bar.remove(c)
        self.attachment_bar.set_visible(False)
        self.conversation_id = uuid.uuid4().hex
        while (c := self.list.get_first_child()) is not None:
            self.list.remove(c)
        self.list.append(self.empty)
        self._resume_follow()

    def _save_chat(self):
        if self.history:
            self.saved_conversations = conversations.upsert(
                self.saved_conversations, self.conversation_id, self.history)
            conversations.save(self.saved_conversations)

    def _show_conversations(self, button):
        pop = Gtk.Popover(autohide=True, position=Gtk.PositionType.BOTTOM)
        pop.set_parent(button)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                      margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
        for item in self.saved_conversations[:20]:
            row = Gtk.Box(spacing=4)
            open_btn = Gtk.Button(label=item.get("title") or _("New Chat"), hexpand=True)
            open_btn.connect("clicked", lambda _b, c=item: (self._open_chat(c), pop.popdown()))
            row.append(open_btn)
            delete = Gtk.Button(icon_name="user-trash-symbolic",
                                tooltip_text=_("Delete conversation"))
            delete.connect("clicked", lambda _b, c=item: (self._delete_chat(c), pop.popdown()))
            row.append(delete)
            box.append(row)
        if not self.saved_conversations:
            box.append(Gtk.Label(label=_("No saved conversations")))
        pop.set_child(box)
        pop.popup()

    def _open_chat(self, item):
        self._stop()
        self.conversation_id = item["id"]
        self.history = list(item["messages"])
        while (c := self.list.get_first_child()) is not None:
            self.list.remove(c)
        for message in self.history:
            role = message.get("role")
            if role in ("user", "assistant"):
                self.list.append(Message(role, message.get("display", message.get("content", ""))))
        self._resume_follow()

    def _delete_chat(self, item):
        self.saved_conversations = [c for c in self.saved_conversations
                                    if c.get("id") != item.get("id")]
        conversations.save(self.saved_conversations)
        if self.conversation_id == item.get("id"):
            self.new_chat()

    def _stop(self):
        if self.stop_event is not None:
            self.stop_event.set()
            self.stop_event = None
            if self.current_reply is not None:
                partial = self.current_reply.text.strip()
                if partial:
                    self.history.append({"role": "assistant", "content": partial})
                    self._save_chat()
                else:
                    self.list.remove(self.current_reply)
            self.current_reply = None
        self.busy = False
        if hasattr(self, "send_btn"):
            self.send_btn.set_sensitive(True)
            self.stop_btn.set_visible(False)

    def _on_user_scroll(self, _controller, _dx, dy):
        if dy < 0:
            self.follow_reply = False
        elif dy > 0:
            adj = self.scroller.get_vadjustment()
            self.follow_reply = adj.get_value() + adj.get_page_size() >= adj.get_upper() - 64
        self.latest.set_visible(not self.follow_reply)
        return False

    def _on_content_size(self, *_args):
        if self.follow_reply:
            GLib.idle_add(self._scroll_down)
        elif self.busy:
            self.latest.add_css_class("unread")
            self.latest.set_visible(True)

    def _on_scroll_position(self, adjustment):
        if not self.follow_reply and adjustment.get_value() + adjustment.get_page_size() \
                >= adjustment.get_upper() - 8:
            self._resume_follow()

    def _resume_follow(self):
        self.follow_reply = True
        self.latest.remove_css_class("unread")
        self.latest.set_visible(False)
        GLib.idle_add(self._scroll_down)

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
            self.send(prompt.replace("{lang}", _user_language_name()).format(text.strip()[:12000]))
        Gdk.Display.get_default().get_clipboard().read_text_async(None, got)

    def send(self, text):
        text = text.strip()
        if not text or self.busy:
            return
        self.refresh()
        if not ai.enabled():
            return
        if self.attachments and ai.provider() != "local":
            self.entry.set_placeholder_text(_("Attachments require the local AI model"))
            return
        if ai.provider() != "local" and any(m.get("local_only") for m in self.history):
            self.entry.set_placeholder_text(_("Start a new chat before using a cloud provider"))
            return
        self.entry.set_text("")
        if self.empty.get_parent() is not None:
            self.list.remove(self.empty)
        display_text = text
        if self.attachments:
            display_text += "\n" + " ".join(
                ("📷 " if item["kind"] == "OCR" else "📄 ") + item["name"]
                for item in self.attachments)
        self.list.append(Message("user", display_text))
        reply = Message("assistant")
        self.list.append(reply)
        self.current_reply = reply
        context = "\n\n".join(
            f"Attached {item['kind']} from {item['name']}:\n{item['text']}"
            for item in self.attachments)
        full_text = text + ("\n\n" + context if context else "")
        self.history.append({"role": "user", "content": full_text, "display": display_text,
                             "local_only": bool(context)})
        self.attachments = []
        while (chip := self.attachment_bar.get_first_child()) is not None:
            self.attachment_bar.remove(chip)
        self.attachment_bar.set_visible(False)
        self._save_chat()
        self.busy = True
        self.send_btn.set_sensitive(False)
        self.stop_btn.set_visible(True)
        self._resume_follow()
        self.stop_event = threading.Event()
        threading.Thread(target=self._run, args=(reply, list(self.history), self.stop_event),
                         daemon=True).start()

    def _run(self, reply, history, stop_event):
        from aurora.ai.providers import ProviderError, chat
        parts = []
        error = None
        try:
            if ai.provider() != "local" and any(m.get("local_only") for m in history):
                raise ProviderError(_("Attachments require the local AI model"))
            messages = [{"role": item["role"], "content": item["content"]}
                        for item in history[-12:]]
            for piece in chat(messages):
                if stop_event.is_set():
                    break
                parts.append(piece)
                GLib.idle_add(self._stream_piece, reply, "".join(parts), stop_event)
        except (ProviderError, OSError, ValueError) as e:
            error = str(e)
        GLib.idle_add(self._done, reply, "".join(parts), error, stop_event)

    def _stream_piece(self, reply, text, stop_event):
        if stop_event is self.stop_event and not stop_event.is_set():
            reply.set_text(text)
        return False

    def _done(self, reply, text, error, stop_event):
        if stop_event is not self.stop_event:
            return False
        self.busy = False
        self.send_btn.set_sensitive(True)
        self.stop_btn.set_visible(False)
        self.stop_event = None
        self.current_reply = None
        if error:
            reply.set_text(_("Something went wrong: {error}").format(error=error), streaming=True)
            return False
        self.history.append({"role": "assistant", "content": text})
        self._save_chat()
        reply.set_text(text, streaming=False)
        copy = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text=_("Copy"),
                          css_classes=["flat", "circular"])
        copy.connect("clicked", lambda *_: Gdk.Display.get_default().get_clipboard().set(text))
        reply.actions.append(copy)
        retry = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=_("Regenerate"),
                           css_classes=["flat", "circular"])
        retry.connect("clicked", lambda *_: self._regenerate(reply))
        reply.actions.append(retry)
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
        if not self.follow_reply:
            return False
        adj = self.scroller.get_vadjustment()
        adj.set_value(max(0, adj.get_upper() - adj.get_page_size()))
        return False

    def _regenerate(self, reply):
        if self.busy or not self.history or self.history[-1].get("role") != "assistant":
            return
        self.history.pop()
        self._save_chat()
        self.list.remove(reply)
        replacement = Message("assistant")
        self.list.append(replacement)
        self.current_reply = replacement
        self.busy = True
        self.send_btn.set_sensitive(False)
        self.stop_btn.set_visible(True)
        self.stop_event = threading.Event()
        threading.Thread(target=self._run,
                         args=(replacement, list(self.history), self.stop_event),
                         daemon=True).start()


WRITING_ACTIONS = [
    ("proofread", N_("Proofread"), "Fix spelling, grammar and punctuation. Keep the wording, "
                                   "language and meaning. Reply with the corrected text only."),
    ("friendly", N_("Friendlier"), "Rewrite this in a warmer, friendlier tone, same language. "
                                   "Reply with the new text only."),
    ("professional", N_("More Professional"), "Rewrite this in a clear, professional tone, same "
                                              "language. Reply with the new text only."),
    ("concise", N_("Shorter"), "Make this shorter and clearer without losing information, same "
                               "language. Reply with the new text only."),
    ("summary", N_("Summarize"), "Summarize this in two or three sentences, same language."),
    ("points", N_("Key Points"), "List the key points of this as short bullets, same language."),
    ("translate", N_("Translate"), "Translate this into {lang}. Reply with the translation only."),
]


def _user_language_name():
    """Translate into the AI answer language if one is set, else the system language."""
    import locale
    from aurora import settings
    from aurora.ai.providers import LANGUAGES
    s = settings.get()
    lang = (s.get_string("ai-language") if s else "") or \
        (locale.getlocale(locale.LC_MESSAGES)[0] or "en").split("_")[0]
    return LANGUAGES.get(lang, "English")


class WritingTools(Adw.ApplicationWindow):
    """Apple-style writing tools: act on the selected text, then replace it."""

    def __init__(self, app, text):
        super().__init__(application=app, title=_("Writing Tools"), default_width=520,
                         default_height=520)
        self.source = text
        self.result = ""
        header = Adw.HeaderBar(title_widget=Adw.WindowTitle(title=_("Writing Tools"),
                                                            subtitle=_("Aurora AI")))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12,
                      margin_bottom=12, margin_start=16, margin_end=16)
        preview = Gtk.Label(label=text[:400] + ("…" if len(text) > 400 else ""), xalign=0,
                            wrap=True, lines=4, ellipsize=Pango.EllipsizeMode.END,
                            css_classes=["dim-label"])
        box.append(preview)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4,
                           column_spacing=6, row_spacing=6)
        for key, label, prompt in WRITING_ACTIONS:
            b = Gtk.Button(label=_(label), css_classes=["pill"])
            b.connect("clicked", lambda _b, p=prompt: self.run(p))
            flow.append(b)
        box.append(flow)
        self.output = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, editable=True,
                                   top_margin=10, bottom_margin=10, left_margin=10,
                                   right_margin=10, css_classes=["card"])
        box.append(Gtk.ScrolledWindow(child=self.output, vexpand=True))
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        copy = Gtk.Button(label=_("Copy"))
        copy.connect("clicked", lambda *_: self._copy())
        self.replace = Gtk.Button(label=_("Replace Selection"), css_classes=["suggested-action"],
                                  sensitive=False)
        self.replace.connect("clicked", lambda *_: self._replace())
        actions.append(copy)
        actions.append(self.replace)
        box.append(actions)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(header)
        self.set_content(view)

    def run(self, prompt):
        buf = self.output.get_buffer()
        buf.set_text(_("Working…"))
        self.replace.set_sensitive(False)
        instruction = prompt.replace("{lang}", _user_language_name())
        messages = [{"role": "user", "content": f"{instruction}\n\n---\n{self.source}"}]

        def work():
            from aurora.ai.providers import ProviderError, chat
            parts = []
            try:
                for piece in chat(messages, max_tokens=1500):
                    parts.append(piece)
                    GLib.idle_add(buf.set_text, "".join(parts))
                GLib.idle_add(self._done)
            except ProviderError as e:
                GLib.idle_add(buf.set_text, _("Something went wrong: {error}").format(error=e))
        threading.Thread(target=work, daemon=True).start()

    def _done(self):
        self.replace.set_sensitive(True)
        return False

    def _text(self):
        buf = self.output.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()

    def _copy(self):
        Gdk.Display.get_default().get_clipboard().set(self._text())

    def _replace(self):
        """Put the result on the clipboard, close, and paste it over the selection."""
        import subprocess
        text = self._text()
        subprocess.run(["wl-copy", "--", text])
        self.close()
        subprocess.Popen(["sh", "-c", "sleep 0.4; wtype -M ctrl -k v -m ctrl"])


def _selected_text():
    import subprocess
    for args in (["wl-paste", "--primary", "--no-newline"], ["wl-paste", "--no-newline"]):
        res = subprocess.run(args, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout
    return ""


class AssistantApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Assistant",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        ensure_float_rule()
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        if args[:1] == ["--writing"]:
            text = _selected_text()
            if ai.enabled() and text.strip():
                WritingTools(self, text).present()
                return 0
        if self.window is None:
            self.window = AssistantWindow(self)
        self.window.present()
        self.window.refresh()
        if args[:1] == ["--ask"] and len(args) > 1:
            self.window.send(" ".join(args[1:]))
        elif args[:1] == ["--file"] and len(args) > 1:
            self.window.attach_file(args[1], summarize="--summarize" in args)
        return 0


# labwc keeps the Assistant above other windows and on every workspace, in the
# bottom-right corner, like a picture-in-picture video.
FLOAT_ACTIONS = [("ToggleAlwaysOnTop", {}), ("ToggleOmnipresent", {}),
                 ("MoveToEdge", {"direction": "right", "snapWindows": "no"}),
                 ("MoveToEdge", {"direction": "down", "snapWindows": "no"})]


def ensure_float_rule():
    """Add the window rule to configs made before it existed (it must be there before
    the window maps)."""
    import xml.etree.ElementTree as ET

    from aurora import labwcconf
    try:
        cfg = labwcconf.Config()
    except (OSError, ET.ParseError):
        return
    rules = cfg.node("windowRules")
    if any(r.get("identifier") == "org.aurora.Assistant" for r in rules.findall("windowRule")):
        return
    rule = ET.SubElement(rules, "windowRule", identifier="org.aurora.Assistant",
                         skipWindowSwitcher="yes")
    for name, attrs in FLOAT_ACTIONS:
        ET.SubElement(rule, "action", name=name, **attrs)
    cfg.save()


def main():
    return AssistantApp().run(sys.argv)


__all__ = ["main", "VERSION"]
