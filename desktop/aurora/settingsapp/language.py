"""Language & Region: session language, formats and keyboard layouts.

Language is stored in ~/.config/aurora/locale.conf (read by aurora-session).
Keyboard layouts go to ~/.config/labwc/environment and apply immediately.
"""

import os
import re
import subprocess

from gi.repository import Adw, Gtk

from aurora import config_path
from aurora.i18n import _
from aurora.settingsapp.util import Page, combo_row, run, toast

# Native names for the languages Aurora ships.
LANGUAGE_NAMES = {
    "en_US": "English (United States)", "en_GB": "English (United Kingdom)",
    "it_IT": "Italiano", "de_DE": "Deutsch", "fr_FR": "Français", "es_ES": "Español",
    "pt_BR": "Português (Brasil)", "pt_PT": "Português (Portugal)", "nl_NL": "Nederlands",
    "pl_PL": "Polski", "sv_SE": "Svenska", "tr_TR": "Türkçe", "ru_RU": "Русский",
    "uk_UA": "Українська", "zh_CN": "中文（简体）", "zh_TW": "中文（繁體）",
    "ja_JP": "日本語", "ko_KR": "한국어", "ar_EG": "العربية", "hi_IN": "हिन्दी",
}

XKB_LIST = "/usr/share/X11/xkb/rules/evdev.lst"


def installed_locales():
    out = run(["locale", "-a"])
    found = []
    for line in out.split():
        m = re.match(r"^([a-z]{2,3}_[A-Z]{2})(\.utf8)?$", line)
        if m:
            name = m.group(1) + (".UTF-8" if m.group(2) else "")
            found.append(name)
    return sorted(set(found), key=lambda l: LANGUAGE_NAMES.get(l.split(".")[0], l))


def locale_label(loc):
    return LANGUAGE_NAMES.get(loc.split(".")[0], loc)


def xkb_layouts():
    layouts = []
    try:
        with open(XKB_LIST) as f:
            section = None
            for line in f:
                if line.startswith("!"):
                    section = line[1:].strip()
                    continue
                if section == "layout" and line.strip():
                    code, _sp, desc = line.strip().partition(" ")
                    layouts.append((code, desc.strip()))
    except OSError:
        layouts = [("us", "English (US)")]
    return sorted(layouts, key=lambda l: l[1])


def read_conf(path):
    values = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and not k.startswith("#"):
                    values[k] = v.strip().strip('"')
    return values


def write_conf(path, values, header="# Written by Aurora Settings"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(header + "\n")
        for k, v in values.items():
            if v:
                f.write(f'{k}="{v}"\n')


def current_locale():
    user = read_conf(config_path("locale.conf"))
    system = read_conf("/etc/default/locale")
    return user.get("LANG") or system.get("LANG") or os.environ.get("LANG", "en_US.UTF-8")


class Language(Page):
    page_id = "language"
    title = _("Language & Region")
    icon_name = "preferences-desktop-locale-symbolic"

    def build(self):
        self.locales = installed_locales() or ["en_US.UTF-8"]
        labels = [locale_label(l) for l in self.locales]
        user = read_conf(config_path("locale.conf"))

        lang = self.group(_("Language"),
                          _("Changes take effect the next time you log in."))
        cur = current_locale()
        idx = self._index(cur)
        lang.add(combo_row(_("Language"), labels, idx, search=True,
                           on_change=lambda i: self._set("LANG", self.locales[i])))
        fmt = user.get("LC_TIME") or cur
        lang.add(combo_row(_("Formats"), labels, self._index(fmt),
                           subtitle=_("Dates, times, numbers and units"), search=True,
                           on_change=self._set_formats))

        restart = Adw.ButtonRow(title=_("Log Out Now"))
        restart.connect("activated", lambda *_: subprocess.Popen(["labwc", "--exit"]))
        lang.add(restart)

        kb = self.group(_("Keyboard"),
                        _("Add several layouts and switch with Alt+Shift."))
        self.layouts = xkb_layouts()
        self.kb_group = kb
        self.kb_rows = []
        add = Adw.ComboRow(title=_("Add layout"),
                           model=Gtk.StringList.new([d for _c, d in self.layouts]),
                           enable_search=True)
        add.set_selected(Gtk.INVALID_LIST_POSITION)
        add.connect("notify::selected", self._on_add_layout)
        self.add_row = add
        kb.add(add)
        self._refresh_layouts()

    def _index(self, loc):
        base = loc.split(".")[0]
        for i, l in enumerate(self.locales):
            if l.split(".")[0] == base:
                return i
        return 0

    def _set(self, key, value):
        path = config_path("locale.conf")
        values = read_conf(path)
        values[key] = value
        if key == "LANG":
            values["LANGUAGE"] = value.split(".")[0]
        write_conf(path, values)
        toast(self, _("Language will change after you log out."))

    def _set_formats(self, i):
        path = config_path("locale.conf")
        values = read_conf(path)
        for k in ("LC_TIME", "LC_NUMERIC", "LC_MONETARY", "LC_MEASUREMENT", "LC_PAPER"):
            values[k] = self.locales[i]
        write_conf(path, values)

    # --- keyboard ---

    def _env_path(self):
        return os.path.join(os.path.expanduser("~/.config/labwc"), "environment")

    def _current_layouts(self):
        env = read_conf(self._env_path())
        value = env.get("XKB_DEFAULT_LAYOUT") or os.environ.get("XKB_DEFAULT_LAYOUT", "us")
        return [x for x in value.split(",") if x]

    def _save_layouts(self, codes):
        path = self._env_path()
        env = read_conf(path)
        env["XKB_DEFAULT_LAYOUT"] = ",".join(codes)
        env["XKB_DEFAULT_OPTIONS"] = "grp:alt_shift_toggle" if len(codes) > 1 else ""
        write_conf(path, env)
        subprocess.Popen(["labwc", "--reconfigure"], stderr=subprocess.DEVNULL)
        self._refresh_layouts()

    def _refresh_layouts(self):
        for r in self.kb_rows:
            self.kb_group.remove(r)
        self.kb_rows = []
        names = dict(self.layouts)
        codes = self._current_layouts()
        for code in codes:
            row = Adw.ActionRow(title=names.get(code, code), subtitle=code)
            row.add_prefix(Gtk.Image(icon_name="input-keyboard-symbolic"))
            if len(codes) > 1:
                rm = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                css_classes=["flat"], tooltip_text=_("Remove"))
                rm.connect("clicked", lambda _b, c=code: self._save_layouts(
                    [x for x in self._current_layouts() if x != c]))
                row.add_suffix(rm)
            self.kb_group.add(row)
            self.kb_rows.append(row)

    def _on_add_layout(self, row, _p):
        i = row.get_selected()
        if i == Gtk.INVALID_LIST_POSITION:
            return
        code = self.layouts[i][0]
        codes = self._current_layouts()
        if code not in codes:
            self._save_layouts(codes + [code])
        row.set_selected(Gtk.INVALID_LIST_POSITION)
