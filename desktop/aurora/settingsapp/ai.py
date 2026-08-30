"""Settings → AI: turn Aurora AI on, pick where answers come from, and set up
each feature (downloads happen here, with progress, and can be removed)."""

import os
import subprocess
import threading

from gi.repository import Adw, GLib, Gtk

from aurora import activities, ai, settings
from aurora.ai import components, keys
from aurora.i18n import _
from aurora.settingsapp.util import Page, combo_row, switch_row, toast

GB = 1e9


def _size(n):
    return GLib.format_size(n)


def _ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1e6
    except OSError:
        pass
    return 0


class Job:
    """Runs an install in a thread and reports progress on the main loop."""

    def __init__(self, row, work, done):
        self.row, self.done = row, done
        self.cancel = False
        self.activity_id = activities.create(
            _("Downloading {name}").format(name=row.get_title()), "download", cancellable=False)
        self.bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=120)
        row.add_suffix(self.bar)
        threading.Thread(target=self._run, args=(work,), daemon=True).start()

    def progress(self, done, total):
        fraction = done / total if total else 0
        activities.update(self.activity_id, progress=fraction)
        GLib.idle_add(self.bar.set_fraction, fraction)

    def _run(self, work):
        try:
            work(self)
            error = None
        except Exception as e:  # noqa: BLE001 - shown to the user
            error = str(e)
        GLib.idle_add(self._finish, error)

    def _finish(self, error):
        activities.update(self.activity_id, status="failed" if error else "finished",
                          progress=1.0 if not error else self.bar.get_fraction(),
                          error=error or "")
        self.row.remove(self.bar)
        self.done(error)
        return False


class AI(Page):
    page_id = "ai"
    title = _("AI")
    icon_name = "aurora-assistant-symbolic"

    def build(self):
        self.s = settings.get()
        s = self.s
        intro = self.group(
            _("Aurora AI"),
            _("A private assistant: ask questions from Spotlight with “?”, get commands in the "
              "terminal with ask and why, dictate text, have text read aloud and find "
              "documents by meaning. It runs on this computer; nothing is sent anywhere "
              "unless you choose a cloud provider below. Nothing is downloaded until you "
              "set up a feature."))
        intro.add(switch_row(_("Aurora AI"), s.get_boolean("ai-enabled"), self._set_enabled))
        intro.add(switch_row(_("Assistant button in the top bar"),
                             s.get_boolean("ai-panel-button"),
                             lambda v: s.set_boolean("ai-panel-button", v),
                             subtitle=_("The Assistant is also in the dock and opens with "
                                        "Super+Shift+Space")))

        where = self.group(_("Answers Come From"))
        providers = ["local", "anthropic", "openai"]
        cur = s.get_string("ai-provider")
        where.add(combo_row(_("Provider"), [_("This computer (private)"), "Anthropic Claude",
                                            _("OpenAI-compatible API")],
                            providers.index(cur) if cur in providers else 0,
                            on_change=lambda i: self._set_provider(providers[i])))
        self.local_group = self.group(
            _("Model on This Computer"),
            _("Bigger models answer better but need more memory. This computer has "
              "{ram:.0f} GB.").format(ram=_ram_gb()))
        self.model_rows = {}
        for mid, m in ai.catalog()["chat"].items():
            row = Adw.ActionRow(title=m["name"], subtitle=f"{m['description']} · "
                                f"{_size(m['size'])} · {_('needs {n} GB of memory').format(n=m['ram_gb'])}")
            self.model_rows[mid] = row
            self.local_group.add(row)
            self._model_buttons(mid)

        self.cloud_group = self.group(_("Cloud Provider"),
                                      _("Questions and the text you ask about are sent to the "
                                        "provider. Keys are kept in your login keyring. "
                                        "Claude and ChatGPT subscriptions work only in their "
                                        "own apps: Dev Hub installs Claude Code and Codex, "
                                        "which sign in with your subscription."))
        billing = Adw.ActionRow(
            title=_("API keys are paid per use"),
            subtitle=_("Every answer uses credits billed by the provider, separately from any "
                       "Claude Pro/Max or ChatGPT Plus subscription, which API keys don't use. "
                       "Check prices and set a spending limit in the provider's console. "
                       "Answers on this computer are free."),
            subtitle_lines=0)
        billing.add_prefix(Gtk.Image(icon_name="dialog-warning-symbolic", css_classes=["warning"]))
        self.cloud_group.add(billing)
        self.key_row = Adw.PasswordEntryRow(title=_("API key"), show_apply_button=True)
        self.key_row.connect("apply", lambda r: self._save_key(r.get_text()))
        self.cloud_group.add(self.key_row)
        self.claude_model = Adw.EntryRow(title=_("Claude model"), show_apply_button=True,
                                         text=s.get_string("ai-anthropic-model"))
        self.claude_model.connect("apply", lambda r: s.set_string("ai-anthropic-model",
                                                                  r.get_text().strip()))
        self.cloud_group.add(self.claude_model)
        presets = [(_("Choose a service…"), None), ("OpenAI", "https://api.openai.com/v1"),
                   ("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
                   ("Mistral", "https://api.mistral.ai/v1"),
                   ("OpenRouter", "https://openrouter.ai/api/v1"),
                   ("Groq", "https://api.groq.com/openai/v1"),
                   (_("Ollama on this computer"), "http://localhost:11434/v1")]

        def pick(i):
            url = presets[i][1]
            if url:
                s.set_string("ai-openai-url", url)
                self.openai_url.set_text(url)
        self.openai_service = combo_row(_("Service"), [n for n, _u in presets], 0,
                                        subtitle=_("Fills in the address; then add your key "
                                                   "and a model name"), on_change=pick)
        self.cloud_group.add(self.openai_service)
        self.openai_url = Adw.EntryRow(title=_("API address"), show_apply_button=True,
                                       text=s.get_string("ai-openai-url"))
        self.openai_url.connect("apply", lambda r: s.set_string("ai-openai-url",
                                                                r.get_text().strip()))
        self.cloud_group.add(self.openai_url)
        self.openai_model = Adw.EntryRow(title=_("Model"), show_apply_button=True,
                                         text=s.get_string("ai-openai-model"))
        self.openai_model.connect("apply", lambda r: s.set_string("ai-openai-model",
                                                                  r.get_text().strip()))
        self.cloud_group.add(self.openai_model)

        feats = self.group(_("Where Aurora AI Helps"),
                           _("Turn off anything you don't want. Features with a download are "
                             "set up the first time you switch them on."))
        for key, title, sub in (
            ("ai-writing-tools", _("Writing tools"),
             _("Select text anywhere and press Super+Shift+W: proofread, rewrite, shorten, "
               "summarize, translate, then replace the selection")),
            ("ai-files", _("Files"), _("“Summarize” and “Ask About This File” in the Files "
                                       "menu, for text, code, PDF and documents")),
            ("ai-screenshots", _("Screenshots"),
             _("“Ask Aurora” on the screenshot notification explains what's on screen")),
            ("ai-notifications", _("Notifications"),
             _("A Summarize button when notifications pile up")),
        ):
            feats.add(switch_row(title, s.get_boolean(key),
                                 lambda v, k=key: s.set_boolean(k, v), subtitle=sub))
        feats.add(switch_row(_("Ask from Spotlight"), s.get_boolean("ai-spotlight"),
                             lambda v: s.set_boolean("ai-spotlight", v),
                             subtitle=_("Type ? and a question. Super+Shift+Space opens the "
                                        "Assistant.")))
        feats.add(switch_row(_("Terminal commands"), s.get_boolean("ai-terminal"),
                             lambda v: s.set_boolean("ai-terminal", v),
                             subtitle=_("ask \"what to do\" suggests a command; why explains "
                                        "the last error")))

        self.dictation_row = switch_row(
            _("Dictation"), s.get_boolean("ai-dictation"), self._set_dictation,
            subtitle=_("Super+H, speak, Super+H again: the text is typed where you are. "
                       "Speech recognition runs on this computer (Whisper)."))
        feats.add(self.dictation_row)
        models = ["base", "small"]
        feats.add(combo_row(_("Dictation accuracy"),
                            [_("Quick (Whisper base)"), _("Accurate (Whisper small)")],
                            models.index(s.get_string("ai-whisper-model")),
                            on_change=lambda i: s.set_string("ai-whisper-model", models[i])))
        self.read_row = switch_row(
            _("Read aloud"), s.get_boolean("ai-read-aloud"), self._set_read_aloud,
            subtitle=_("Select text anywhere and press Super+Shift+R (a natural voice for "
                       "your language, Piper)"))
        feats.add(self.read_row)
        self.search_row = switch_row(
            _("Search documents by meaning"), s.get_boolean("ai-semantic-search"),
            self._set_semantic,
            subtitle=_("Spotlight finds files by what they're about, not only their name"))
        feats.add(self.search_row)
        folders = Adw.EntryRow(title=_("Folders to index"), show_apply_button=True,
                               text=", ".join(s.get_strv("ai-index-folders")))
        folders.connect("apply", lambda r: s.set_strv(
            "ai-index-folders", [f.strip() for f in r.get_text().split(",") if f.strip()]))
        feats.add(folders)
        index_now = Adw.ButtonRow(title=_("Update the Index Now"))
        index_now.connect("activated", lambda *_: self._index_now())
        feats.add(index_now)

        self._language_group()

        store = self.group(_("Storage"))
        self.usage = Adw.ActionRow(title=_("Space used by AI"),
                                   subtitle=_size(components.disk_usage()))
        store.add(self.usage)
        remove = Adw.ButtonRow(title=_("Remove All AI Downloads"), css_classes=["destructive-action"])
        remove.connect("activated", lambda *_: self._remove_all())
        store.add(remove)
        self._sync()

    # --- languages ---

    NATIVE = [("en", "English"), ("it", "Italiano"), ("es", "Español"), ("fr", "Français"),
              ("de", "Deutsch"), ("pt", "Português"), ("nl", "Nederlands"), ("pl", "Polski"),
              ("sv", "Svenska"), ("tr", "Türkçe"), ("ru", "Русский"), ("uk", "Українська"),
              ("zh", "中文"), ("ja", "日本語"), ("ko", "한국어"), ("ar", "العربية"),
              ("hi", "हिन्दी")]

    def _language_group(self):
        s = self.s
        g = self.group(_("Languages"),
                       _("Aurora AI understands and answers in many languages. Ask it in "
                         "any language, or tell it “reply in Italian”, whatever the system "
                         "language is."))
        codes = [""] + [c for c, _n in self.NATIVE]
        names = [_("The language I write in")] + [n for _c, n in self.NATIVE]
        cur = s.get_string("ai-language")
        g.add(combo_row(_("Answers in"), names, codes.index(cur) if cur in codes else 0,
                        on_change=lambda i: s.set_string("ai-language", codes[i])))
        dnames = [_("Detect automatically")] + [n for _c, n in self.NATIVE]
        cur = s.get_string("ai-dictation-language")
        g.add(combo_row(_("Dictation language"), dnames, codes.index(cur) if cur in codes else 0,
                        on_change=lambda i: s.set_string("ai-dictation-language", codes[i])))
        voices = list(ai.catalog()["voices"])
        native = dict(self.NATIVE)
        labels = [f"{native.get(v.split('_')[0], v)} ({v.split('_')[1]})" for v in voices]
        from aurora.ai import speech
        cur = speech.voice_code()
        self.voice_row = combo_row(_("Read-aloud voice"), labels,
                                   voices.index(cur) if cur in voices else 0, search=True,
                                   on_change=lambda i: self._set_voice(voices[i]))
        g.add(self.voice_row)
        self._voice_button(cur)

    def _voice_button(self, code):
        row = self.voice_row
        old = getattr(row, "_aurora_dl", None)
        if old is not None:
            row.remove(old)
            row._aurora_dl = None
        if components.speech_installed() and components.voice_installed(code):
            row.set_subtitle(_("Downloaded"))
            return
        row.set_subtitle(_("Not downloaded yet"))
        b = Gtk.Button(label=_("Download"), valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda *_: self._download_voice(code, b))
        row.add_suffix(b)
        row._aurora_dl = b

    def _set_voice(self, code):
        self.s.set_string("ai-voice", code)
        self._voice_button(code)

    def _download_voice(self, code, button):
        button.set_sensitive(False)

        def work(job):
            if not components.speech_installed():
                components.install_speech()
            components.install_voice(code, job.progress)
        Job(self.voice_row, work, lambda e: (self._after_setup(e, _("Voice ready")),
                                             self._voice_button(code)))

    # --- state ---

    def _sync(self):
        which = self.s.get_string("ai-provider")
        self.local_group.set_visible(which == "local")
        self.cloud_group.set_visible(which != "local")
        self.claude_model.set_visible(which == "anthropic")
        self.openai_url.set_visible(which == "openai")
        self.openai_service.set_visible(which == "openai")
        self.openai_model.set_visible(which == "openai")
        if which != "local":
            self.key_row.set_text(keys.get(which))
        for mid in self.model_rows:
            self._model_buttons(mid)
        self.usage.set_subtitle(_size(components.disk_usage()))

    def _set_enabled(self, on):
        self.s.set_boolean("ai-enabled", on)
        if on and self.s.get_string("ai-provider") == "local" and \
                not components.model_installed("chat", self.s.get_string("ai-model")):
            toast(self, _("Now download a model below"))
        if not on:
            subprocess.Popen(["aurora-ai", "stop"])

    def _set_provider(self, value):
        self.s.set_string("ai-provider", value)
        self._sync()

    def _save_key(self, key):
        try:
            keys.set(self.s.get_string("ai-provider"), key.strip())
            toast(self, _("Key saved in your keyring"))
        except RuntimeError as e:
            toast(self, str(e))

    # --- local models ---

    def _model_buttons(self, mid):
        row = self.model_rows[mid]
        for child in list(getattr(row, "_aurora_suffixes", [])):
            row.remove(child)
        row._aurora_suffixes = []
        current = self.s.get_string("ai-model") == mid
        if components.model_installed("chat", mid):
            if current:
                w = Gtk.Image(icon_name="object-select-symbolic", tooltip_text=_("In use"))
            else:
                w = Gtk.Button(label=_("Use"), valign=Gtk.Align.CENTER)
                w.connect("clicked", lambda *_: self._use_model(mid))
            delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                css_classes=["flat"], tooltip_text=_("Delete"))
            delete.connect("clicked", lambda *_: (components.remove_model("chat", mid),
                                                  self._sync()))
            for x in (w, delete):
                row.add_suffix(x)
                row._aurora_suffixes.append(x)
        else:
            b = Gtk.Button(label=_("Download"), valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda btn: self._download_model(mid, btn))
            row.add_suffix(b)
            row._aurora_suffixes.append(b)

    def _use_model(self, mid):
        self.s.set_string("ai-model", mid)
        subprocess.Popen(["aurora-ai", "stop"])   # the next question loads the new model
        self._sync()

    def _download_model(self, mid, button):
        button.set_sensitive(False)
        row = self.model_rows[mid]

        def work(job):
            if not components.runtime_installed():
                components.install_runtime(job.progress)
            components.install_model("chat", mid, job.progress)

        def done(error):
            if error:
                toast(self, _("Download failed: {error}").format(error=error))
            elif not components.model_installed("chat", self.s.get_string("ai-model")):
                self.s.set_string("ai-model", mid)
            self._sync()
        Job(row, work, done)

    # --- features that need downloads ---

    def _set_dictation(self, on):
        self.s.set_boolean("ai-dictation", on)
        model = self.s.get_string("ai-whisper-model")
        if on and not (components.speech_installed() and components.whisper_installed(model)):
            def work(job):
                if not components.speech_installed():
                    components.install_speech()
                components.install_whisper(model, job.progress)
            Job(self.dictation_row, work, lambda e: self._after_setup(e, _("Dictation is ready")))

    def _set_read_aloud(self, on):
        self.s.set_boolean("ai-read-aloud", on)
        from aurora.ai import speech
        code = speech.voice_code()
        if on and not (components.speech_installed() and components.voice_installed(code)):
            def work(job):
                if not components.speech_installed():
                    components.install_speech()
                components.install_voice(code, job.progress)
            Job(self.read_row, work, lambda e: self._after_setup(e, _("Read aloud is ready")))

    def _set_semantic(self, on):
        self.s.set_boolean("ai-semantic-search", on)
        subprocess.run(["systemctl", "--user", "enable" if on else "disable", "--now",
                        "aurora-ai-index.timer"], capture_output=True)
        if on and not components.model_installed("embed"):
            def work(job):
                if not components.runtime_installed():
                    components.install_runtime(job.progress)
                components.install_model("embed", progress=job.progress)
            Job(self.search_row, work, lambda e: (self._after_setup(e, _("Indexing your "
                                                                          "documents…")),
                                                  e or self._index_now()))

    def _after_setup(self, error, message):
        toast(self, _("Setup failed: {error}").format(error=error) if error else message)
        self._sync()

    def _index_now(self):
        subprocess.Popen(["systemctl", "--user", "start", "aurora-ai-index.service"])
        toast(self, _("Updating the index in the background"))

    def _remove_all(self):
        subprocess.run(["aurora-ai", "stop"], capture_output=True)
        components.remove_everything()
        for key in ("ai-dictation", "ai-read-aloud", "ai-semantic-search"):
            self.s.set_boolean(key, False)
        toast(self, _("AI downloads removed"))
        self._sync()


__all__ = ["AI", "os"]
