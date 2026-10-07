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

from aurora import plaintext  # noqa: E402,F401  (rows and toasts: plain text)

from aurora import VERSION, ai, apps  # noqa: E402
from aurora.ai import conversations  # noqa: E402
from aurora.i18n import N_, _  # noqa: E402

CSS = """
window.assistant-float { border-radius: 20px; }
window.assistant-float.pip { border: 1px solid alpha(currentColor, 0.12);
  box-shadow: 0 16px 44px rgba(0, 0, 0, 0.35); }
window.assistant-float headerbar { min-height: 40px; }
window.assistant-float.collapsed headerbar { min-height: 46px; }
.assistant-unread { min-width: 9px; min-height: 9px; border-radius: 999px;
  background-color: @accent_bg_color; box-shadow: 0 0 0 3px alpha(@accent_bg_color, 0.25); }
button.model-picker { padding: 0 8px; min-height: 24px; font-size: 0.82em; font-weight: 600; }
.model-row { padding: 6px 10px; }
.bubble { border-radius: 16px; padding: 10px 14px; }
.bubble.user { background-color: alpha(@accent_bg_color, 0.85); color: @accent_fg_color; }
.bubble.assistant { background-color: alpha(currentColor, 0.06); }
.codeblock { border-radius: 10px; background-color: alpha(currentColor, 0.08); }
.codeblock textview { background: transparent; font-family: monospace; }
.quick-actions button { border-radius: 999px; }
.quick-actions > flowboxchild { padding: 0; }
entry.hint { outline: 2px solid alpha(@accent_bg_color, 0.8); outline-offset: -2px;
  transition: outline-color 300ms; }
button.jump-latest { min-width: 42px; min-height: 42px; border-radius: 999px; margin: 4px; }
button.jump-latest.unread { background: @accent_bg_color; color: @accent_fg_color;
  box-shadow: 0 0 0 3px alpha(@accent_bg_color, 0.25); }
@keyframes aurora-jump-nudge {
  0% { transform: translateY(0); }
  30% { transform: translateY(-5px); }
  60% { transform: translateY(3px); }
  100% { transform: translateY(0); }
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


def messages_for_provider(history, which, private=None):
    """Strip UI metadata and refuse to export file attachments to cloud APIs
    (a model on this computer or the local network is fine)."""
    if private is None:
        private = which == "local"
    if not private and any(item.get("local_only") for item in history):
        raise ValueError(_("Attachments require the local AI model"))
    return [{"role": item["role"], "content": item["content"]} for item in history[-12:]]


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


def _layer_shell():
    """gtk4-layer-shell, when the compositor supports it and the library was
    preloaded (bin/aurora-assistant does that), else None."""
    if os.environ.pop("AURORA_ASSISTANT_LAYER", None) != "1":
        return None
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell as LS
    except (ValueError, ImportError):
        return None
    return LS if LS.is_supported() else None


PIP_RIGHT = 16      # gap between the corner Assistant and the screen's right edge


def pip_bottom_margin(dock_covers, dock_right=None, screen_width=None, pip_width=0):
    """How far above the screen's bottom edge the corner Assistant sits: just
    above the dock when the dock is under it (it can grow as wide as the
    screen), right at the bottom when it isn't: the dock ends to its left, is
    on a side, turned off, or auto-hidden and out of sight."""
    if dock_covers <= 0:
        return 12
    if dock_right is not None and screen_width is not None and pip_width > 0:
        if dock_right + 12 <= screen_width - PIP_RIGHT - pip_width:
            return 12
    return dock_covers + 8


def dock_state_path():
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR") or GLib.get_user_runtime_dir(),
                        "aurora-dock")


def dock_state():
    """(pixels of the screen's bottom the dock covers, x of its right end or
    None), as the shell's dock publishes them (dock.py); a bottom dock's usual
    size when unknown."""
    try:
        with open(dock_state_path()) as f:
            fields = f.read().split()
        covers = max(int(fields[0]), 0) if fields else 0
        right = int(fields[1]) if len(fields) > 1 and int(fields[1]) >= 0 else None
        return covers, right
    except (OSError, ValueError):
        return 48 + 28 + 6, None


def dock_covers():
    return dock_state()[0]


def compact_height():
    """580 px, or less on a small screen, so the whole window stays visible."""
    display = Gdk.Display.get_default()
    monitors = display.get_monitors() if display else None
    if not monitors or monitors.get_n_items() == 0:
        return COMPACT[1]
    height = monitors.get_item(0).get_geometry().height
    return max(320, min(COMPACT[1], height - DOCK_ROOM - BAR_ROOM))


class AssistantWindow(Adw.ApplicationWindow):
    """A floating assistant, like a picture-in-picture video: in the bottom-right
    corner, above every window and on every workspace. It never takes the
    keyboard from the app you are using: it gets it when you click into it (or
    open it with Super+Shift+Space). Collapse it to a small bar, like a chat
    in a corner of a web page, or expand it for long answers.

    It is a layer-shell surface where the compositor allows (both of Aurora's);
    elsewhere an ordinary window that window rules keep on top."""

    def __init__(self, app):
        super().__init__(application=app, title=_("Aurora Assistant"),
                         default_width=COMPACT[0], default_height=compact_height())
        self.add_css_class("assistant-float")
        self.LS = _layer_shell()
        self.collapsed = False
        self.big = False
        if self.LS is not None:
            LS = self.LS
            LS.init_for_window(self)
            LS.set_namespace(self, "aurora-assistant")
            LS.set_layer(self, LS.Layer.TOP)
            for edge in (LS.Edge.BOTTOM, LS.Edge.RIGHT):
                LS.set_anchor(self, edge, True)
            self._place_pip()
            LS.set_margin(self, LS.Edge.RIGHT, PIP_RIGHT)
            LS.set_keyboard_mode(self, LS.KeyboardMode.ON_DEMAND)
            # Margins from the screen's edges, not from the room the dock and
            # the top bar leave: pip_bottom_margin() keeps it clear of the dock
            # itself, and lets it go down beside a floating one.
            LS.set_exclusive_zone(self, -1)
            self.add_css_class("pip")
            # Follow the dock: shown, auto-hidden, moved or turned off.
            self._dock_monitor = Gio.File.new_for_path(dock_state_path()).monitor_file(
                Gio.FileMonitorFlags.WATCH_MOVES, None)
            self._dock_monitor.connect("changed", lambda *_a: self._resize())
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
        self._full_only = [new]
        new.connect("clicked", lambda *_: self.new_chat())
        header.pack_start(new)
        past = Gtk.Button(icon_name="document-open-recent-symbolic",
                          tooltip_text=_("Conversations"))
        past.connect("clicked", self._show_conversations)
        header.pack_start(past)
        self._full_only.append(past)
        close = Gtk.Button(icon_name="window-close-symbolic", tooltip_text=_("Close"),
                           css_classes=["circular"])
        close.connect("clicked", lambda *_: self.close())
        header.pack_end(close)
        self.collapse_btn = Gtk.Button(icon_name="go-down-symbolic",
                                       tooltip_text=_("Minimize to a bar"))
        self.collapse_btn.connect("clicked", lambda *_: self.set_collapsed(not self.collapsed))
        header.pack_end(self.collapse_btn)
        self.unread = Gtk.Box(css_classes=["assistant-unread"], valign=Gtk.Align.CENTER,
                              visible=False)
        header.pack_start(self.unread)
        # A collapsed bar opens again with a click anywhere on it.
        reopen = Gtk.GestureClick()
        reopen.connect("released", lambda *_: self.collapsed and self.set_collapsed(False))
        header.add_controller(reopen)
        self.model_btn = Gtk.MenuButton(css_classes=["flat", "model-picker"],
                                        tooltip_text=_("Choose the model"))
        self.model_pop = Gtk.Popover()
        self.model_pop.connect("show", lambda *_: self._fill_models())
        self.model_btn.set_popover(self.model_pop)
        self.title.set_subtitle("")
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        title_box.append(Gtk.Label(label=_("Aurora Assistant"), css_classes=["heading"]))
        self.model_btn.set_halign(Gtk.Align.CENTER)
        title_box.append(self.model_btn)
        header.set_title_widget(title_box)
        self.expand_btn = Gtk.Button(icon_name="aurora-window-expand-symbolic",
                                     tooltip_text=_("Expand"))
        self.expand_btn.connect("clicked", lambda *_: self.toggle_size())
        self.connect("notify::maximized", self._on_maximized)
        header.pack_end(self.expand_btn)
        self._full_only.append(self.expand_btn)
        prefs = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text=_("AI Settings"))
        prefs.connect("clicked", lambda *_: apps.spawn(["aurora-settings", "--page", "ai"]))
        header.pack_end(prefs)
        self._full_only.append(prefs)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        off = Adw.StatusPage(icon_name="aurora-assistant-symbolic", title=_("Aurora AI is off"),
                             description=_("Turn it on in Settings → AI. It runs on this "
                                           "computer, or with the cloud provider you choose."))
        open_btn = Gtk.Button(label=_("Open AI Settings"), halign=Gtk.Align.CENTER,
                              css_classes=["pill", "suggested-action"])
        open_btn.connect("clicked", lambda *_: apps.spawn(["aurora-settings", "--page", "ai"]))
        off.set_child(open_btn)
        self.stack.add_named(off, "off")
        self.nomodel = Adw.StatusPage(icon_name="aurora-assistant-symbolic",
                                      title=_("No model yet"))
        get_model = Gtk.Button(label=_("Open AI Settings"), halign=Gtk.Align.CENTER,
                               css_classes=["pill", "suggested-action"])
        get_model.connect("clicked", lambda *_: apps.spawn(["aurora-settings", "--page", "ai"]))
        self.nomodel.set_child(get_model)
        self.stack.add_named(self.nomodel, "nomodel")

        chat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=16,
                            margin_bottom=16, margin_start=16, margin_end=16)
        self.empty = Adw.StatusPage(icon_name="aurora-assistant-symbolic",
                                    title=_("How can I help?"),
                                    description=_("Ask anything. The buttons below work on "
                                                  "the text you type or paste here, a file "
                                                  "you attach, or the text you last "
                                                  "copied."))
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
                           tooltip_text=_("Uses the text typed here, the attached file, "
                                          "or the text you copied"))
            b.connect("clicked", lambda _b, p=prompt, l=label: self.quick_action(p, l))
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
        # Settings → AI changes show at once: turning AI on, another provider
        # or model.
        from aurora import settings as aurora_settings
        s = aurora_settings.get()
        if s is not None:
            self._settings_handler = s.connect("changed", self._on_setting)
        self._models = None
        self.refresh()

    def toggle_size(self):
        if self.LS is None:
            # The compositor remembers the corner and size, and puts it back.
            if self.is_maximized():
                self.unmaximize()
            else:
                self.maximize()
            return
        self.big = not self.big
        self.set_collapsed(False)
        self._resize()
        self._on_maximized()

    def _place_pip(self, pip_width=0):
        covers, right = dock_state()
        pip_width = pip_width or max(self.get_width(), self.get_default_size()[0])
        self.LS.set_margin(self, self.LS.Edge.BOTTOM,
                           pip_bottom_margin(covers, right, self._screen()[0], pip_width))

    def _screen(self):
        display = Gdk.Display.get_default()
        monitors = display.get_monitors() if display else None
        if monitors and monitors.get_n_items():
            geometry = monitors.get_item(0).get_geometry()
            return geometry.width, geometry.height
        return 1280, 800

    def _resize(self):
        width, height = self._screen()
        if self.collapsed:
            size = (COMPACT[0] - 60, 1)
        elif self.big:
            size = (min(760, width - 64), height - DOCK_ROOM - BAR_ROOM - 16)
        else:
            size = (COMPACT[0], compact_height())
        if self.LS is not None:
            self._place_pip(size[0])
        self.set_default_size(*size)
        self.set_size_request(size[0], size[1] if size[1] > 1 else -1)

    def set_collapsed(self, collapsed):
        """A small bar in the corner, like a minimized chat; a reply that
        arrives meanwhile lights a dot."""
        self.collapsed = collapsed
        self.stack.set_visible(not collapsed)
        for button in self._full_only:
            button.set_visible(not collapsed)
        (self.add_css_class if collapsed else self.remove_css_class)("collapsed")
        self.collapse_btn.set_icon_name("go-up-symbolic" if collapsed else "go-down-symbolic")
        self.collapse_btn.set_tooltip_text(_("Open") if collapsed else _("Minimize to a bar"))
        if not collapsed:
            self.unread.set_visible(False)
        if self.LS is not None:
            self._resize()

    def take_keyboard(self):
        """Opened from the keyboard: take it once, so typing goes here; then
        give it back to whatever the user clicks next."""
        if self.LS is None:
            return
        self.LS.set_keyboard_mode(self, self.LS.KeyboardMode.EXCLUSIVE)
        self.entry.grab_focus()
        GLib.timeout_add(400, lambda: (self.LS.set_keyboard_mode(
            self, self.LS.KeyboardMode.ON_DEMAND), False)[1])

    def _on_maximized(self, *_a):
        big = self.big if self.LS is not None else self.is_maximized()
        self.expand_btn.set_icon_name("aurora-window-restore-symbolic" if big
                                      else "aurora-window-expand-symbolic")
        self.expand_btn.set_tooltip_text(_("Make Smaller") if big else _("Expand"))

    MODEL_KEYS = ("ai-enabled", "ai-provider", "ai-model", "ai-openai-url",
                  "ai-openai-model", "ai-anthropic-model")

    def _on_setting(self, _settings, key):
        if key in self.MODEL_KEYS:
            self._models = None
            self.refresh()

    def refresh(self):
        """Show the chat, or say what is missing: AI off, or no model to use."""
        on = ai.enabled()
        self.model_btn.set_visible(on)
        if not on:
            self.stack.set_visible_child_name("off")
            return
        self.stack.set_visible_child_name("chat")
        self._load_models()

    def _load_models(self):
        """Look up the models in a thread (a network server can be slow)."""
        from aurora.ai import models

        def work():
            try:
                result = models.available()
                error = None
            except OSError as err:
                result, error = None, str(err)
            GLib.idle_add(self._models_loaded, result, error)
        threading.Thread(target=work, daemon=True).start()

    def _models_loaded(self, result, error):
        if not ai.enabled():
            return False
        where = {"local": _("On this computer"), "anthropic": "Claude",
                 "openai": _("OpenAI-compatible")}
        if error is not None:
            self._models = None
            self.model_btn.set_label(_("Server not reachable"))
            self.nomodel.set_title(_("The AI server doesn't answer"))
            self.nomodel.set_description(GLib.markup_escape_text(
                _("Check that it is running, or its address in Settings → AI.") + f"\n{error}"))
            self.stack.set_visible_child_name("nomodel")
            return False
        which, found, current = result
        self._models = result
        if not found:
            self.model_btn.set_label(where.get(which, which))
            self.nomodel.set_title(_("No model yet"))
            self.nomodel.set_description(
                _("Download a model in Settings → AI, or connect to Ollama or LM Studio.")
                if which == "local" else _("This server offers no chat models."))
            self.stack.set_visible_child_name("nomodel")
            return False
        names = dict(found)
        if current not in names:
            # The chosen model is gone (or was never set): use the first one.
            from aurora.ai import models
            current = found[0][0]
            models.choose(which, current)
        self.model_btn.set_label(names[current])
        self.model_btn.set_sensitive(len(found) > 1)
        self.stack.set_visible_child_name("chat")
        return False

    def _fill_models(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=6,
                      margin_bottom=6, margin_start=6, margin_end=6)
        if self._models is not None:
            which, found, current = self._models
            from aurora.ai import models
            for model_id, label in found:
                row = Gtk.Button(css_classes=["flat", "model-row"])
                line = Gtk.Box(spacing=8)
                line.append(Gtk.Image(icon_name="object-select-symbolic",
                                      opacity=1 if model_id == current else 0))
                line.append(Gtk.Label(label=label, xalign=0))
                row.set_child(line)
                row.connect("clicked", lambda _b, m=model_id, w=which: (
                    models.choose(w, m), self.model_pop.popdown()))
                box.append(row)
        self.model_pop.set_child(box)

    def attach_file(self, path, summarize=False):
        """Open a file from Files, keeping it visibly attached until the user sends."""
        self.new_chat()
        self._queue_file(path, summarize)

    def _choose_files(self):
        dialog = Gtk.FileDialog(title=_("Attach files or photos"))
        # The corner Assistant floats above windows: out of the dialog's way
        # while it's open.
        was_collapsed = self.collapsed
        if self.LS is not None and not was_collapsed:
            self.set_collapsed(True)

        def chosen(file_dialog, result):
            if self.LS is not None and not was_collapsed:
                self.set_collapsed(False)
            try:
                files = file_dialog.open_multiple_finish(result)
            except GLib.Error:
                return
            for i in range(files.get_n_items()):
                path = files.get_item(i).get_path()
                if path:
                    self._queue_file(path)
        # No parent for a layer-shell surface: GTK would export it to the
        # file chooser (xdg-foreign), which layer surfaces can't be, and the
        # compositor drops the connection: the Assistant vanished.
        dialog.open_multiple(None if self.LS is not None else self, None, chosen)

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
            except Exception as err:  # noqa: BLE001 - any failure must end "Reading…"
                content = ""
                print(f"aurora-assistant: attachment: {err!r}")
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

    def quick_action(self, prompt, label=""):
        """Run a quick action (Summarize, Translate…) on, in this order: the text
        typed in the entry, the attached files, or the text you copied (or,
        failing that, selected) anywhere.

        GTK only sees the clipboard while this window has the keyboard, which a
        corner assistant usually doesn't: wl-paste reads it anyway (through the
        compositor's data-control protocol)."""
        def run(text):
            text = text.strip()[:12000]
            shown = text if len(text) <= 280 else text[:280] + "…"
            self.send(prompt.replace("{lang}", _user_language_name()).replace("{}", text),
                      display=f"{label}\n{shown}" if label else None)

        typed = self.entry.get_text()
        if typed.strip():
            run(typed)
            return
        if self.attachments:
            names = ", ".join(item["name"] for item in self.attachments)
            self.send(prompt.replace("{lang}", _user_language_name())
                      .replace("{}", f"(the attached file: {names})"), display=label or None)
            return

        def work():
            text = _clipboard_text()
            GLib.idle_add(done, text)

        def done(text):
            if not text.strip():
                self.entry.set_placeholder_text(
                    _("Type or paste text here, attach a file, or copy some text first"))
                self.entry.add_css_class("hint")
                GLib.timeout_add(1600, lambda: self.entry.remove_css_class("hint") or False)
                return False
            run(text)
            return False
        threading.Thread(target=work, daemon=True).start()

    def send(self, text, display=None):
        """Ask the model. `display` is what the chat shows instead of the full
        prompt (a quick action shows its name and the text, not the instructions)."""
        text = text.strip()
        if not text or self.busy:
            return
        self.refresh()
        if not ai.enabled():
            return
        if self.attachments and not ai.stays_private():
            self.entry.set_placeholder_text(
                _("Attachments stay private: use a model on this computer or your network"))
            return
        if not ai.stays_private() and any(m.get("local_only") for m in self.history):
            self.entry.set_placeholder_text(_("Start a new chat before using a cloud provider"))
            return
        self.entry.set_text("")
        if self.empty.get_parent() is not None:
            self.list.remove(self.empty)
        display_text = display or text
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
            messages = messages_for_provider(history, ai.provider(), ai.stays_private())
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
        if self.collapsed:
            self.unread.set_visible(True)
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


def _clipboard_text():
    """The copied text, else the selected text ('' if neither)."""
    import subprocess
    for argv in (["wl-paste", "--no-newline", "--type", "text"],
                 ["wl-paste", "--no-newline", "--primary", "--type", "text"]):
        try:
            res = subprocess.run(argv, capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout
    return ""


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
        if self.window.collapsed:
            self.window.set_collapsed(False)
        if "--focus" in args:
            self.window.take_keyboard()
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
