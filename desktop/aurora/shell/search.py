"""Search providers for the launcher."""

import ast
import math
import operator
import os
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable

from gi.repository import Gdk, Gio

from aurora import apps, settings
from aurora.i18n import N_, _


@dataclass
class Result:
    title: str
    subtitle: str = ""
    icon: object = "application-x-executable"   # icon name or Gio.Icon
    activate: Callable = field(default=lambda: None)
    score: float = 0.0
    app: object = None  # set only for application results (context menu)
    path: str = ""  # local file or project, for context actions


# --- Applications ----------------------------------------------------------

def _app_score(app, q):
    name = (app.get_display_name() or "").lower()
    if name == q:
        return 100
    if name.startswith(q):
        return 90
    if any(w.startswith(q) for w in name.split()):
        return 80
    if q in name:
        return 70
    generic = (app.get_generic_name() or "").lower()
    if q in generic:
        return 60
    keywords = " ".join(app.get_keywords() or []).lower()
    if q in keywords:
        return 55
    exe = os.path.basename(app.get_executable() or "").lower()
    if exe.startswith(q):
        return 50
    desc = (app.get_description() or "").lower()
    if len(q) > 2 and q in desc:
        return 30
    return 0


def search_apps(query):
    q = query.lower().strip()
    out = []
    for app in apps.all_apps():
        score = _app_score(app, q)
        if score:
            out.append(Result(app.get_display_name(), app.get_description() or "",
                              app.get_icon() or "application-x-executable",
                              lambda a=app: apps.launch(a), score, app))
    return out


# --- Calculator ------------------------------------------------------------

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_FUNCS = {name: getattr(math, name) for name in
          ("sqrt", "sin", "cos", "tan", "log", "log10", "log2", "exp", "floor", "ceil",
           "factorial", "radians", "degrees")}
_FUNCS["abs"] = abs
_FUNCS["round"] = round
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _FUNCS and not node.keywords:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


def calculate(expr):
    """Safely evaluate an arithmetic expression; returns a number or None."""
    expr = expr.strip().lstrip("=").replace("^", "**").replace("×", "*").replace("÷", "/")
    expr = expr.replace(",", ".") if expr.count(",") and "(" not in expr else expr
    if not expr or not any(c.isdigit() for c in expr):
        return None
    if not any(c in expr for c in "+-*/%()") and not expr.startswith(tuple(_FUNCS)):
        return None
    try:
        value = _eval(ast.parse(expr, mode="eval"))
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            value = int(value)
        else:
            value = round(value, 10)
    return value


def search_calculator(query):
    value = calculate(query)
    if value is None:
        return []

    def copy():
        Gdk.Display.get_default().get_clipboard().set(str(value))

    return [Result(f"= {value}", _("Press Enter to copy the result"),
                   "accessories-calculator-symbolic", copy, 200)]


# --- Conversions: units and currencies ------------------------------------

_rates_fetching = False


def search_convert(query, refresh=None):
    from aurora import convert
    parsed = convert.parse(query)
    if parsed is None:
        return []
    value, frm, to = parsed
    if convert.is_currency(frm, to):
        rates = convert.cached_rates()
        if rates is None:
            _fetch_rates(refresh)
            return [Result(_("Getting today’s exchange rates…"), _("European Central Bank"),
                           "network-transmit-receive-symbolic", score=200)]
        result = convert.convert_currency(value, frm, to, rates)
        source = _("Exchange rate: European Central Bank")
    else:
        result = convert.convert_units(value, frm, to)
        source = _("Unit conversion")
    if result is None:
        return []
    text = convert.format_number(result)
    return [Result(f"{convert.format_number(value)} {frm} = {text} {to}",
                   source + " · " + _("Press Enter to copy the result"),
                   "accessories-calculator-symbolic", lambda: _copy(text), 200)]


def _fetch_rates(refresh):
    global _rates_fetching
    if _rates_fetching:
        return
    _rates_fetching = True
    import threading
    from gi.repository import GLib

    def work():
        global _rates_fetching
        from aurora import convert
        try:
            convert.fetch_rates()
        except Exception as e:  # noqa: BLE001 - offline is normal
            print(f"aurora: exchange rates unavailable: {e}")
        _rates_fetching = False
        if refresh:
            GLib.idle_add(lambda: (refresh(), False)[1])
    threading.Thread(target=work, daemon=True).start()


def _copy(text):
    Gdk.Display.get_default().get_clipboard().set(text)


# --- Emoji (":" prefix) ----------------------------------------------------

_EMOJI = None
_EMOJI_RANGES = [(0x1F300, 0x1F5FF), (0x1F600, 0x1F64F), (0x1F680, 0x1F6FF),
                 (0x1F900, 0x1F9FF), (0x1FA70, 0x1FAFF), (0x2600, 0x26FF), (0x2700, 0x27BF)]


def _emoji_table():
    """(character, lower-case name) for every emoji Python's Unicode data knows."""
    global _EMOJI
    if _EMOJI is None:
        import unicodedata
        _EMOJI = []
        for lo, hi in _EMOJI_RANGES:
            for cp in range(lo, hi + 1):
                name = unicodedata.name(chr(cp), "")
                if name:
                    _EMOJI.append((chr(cp), name.lower()))
    return _EMOJI


def search_emoji(query):
    q = query[1:].strip().lower()
    if not q:
        return []
    out = []
    for char, name in _emoji_table():
        words = name.split()
        if q in name:
            score = 150 if q in words else 140 if any(w.startswith(q) for w in words) else 120
            out.append(Result(f"{char}  {name.title()}", _("Emoji · Press Enter to copy"),
                              "face-smile-symbolic", lambda c=char: _copy(c), score))
    out.sort(key=lambda r: -r.score)
    return out[:24]


# --- Clipboard history ("clip:" prefix, Super+V) ---------------------------

CLIPBOARD_PREFIX = "clip:"


def search_clipboard(query):
    from aurora import clipboard
    q = query[len(CLIPBOARD_PREFIX):].strip().lower()
    out = []
    for i, text in enumerate(clipboard.load()):
        if q and q not in text.lower():
            continue
        one_line = " ".join(text.split())
        lines = text.count("\n") + 1
        subtitle = (_("Clipboard · {n} lines").format(n=lines) if lines > 1
                    else _("Clipboard"))
        out.append(Result(one_line[:120], subtitle, "edit-paste-symbolic",
                          lambda t=text: _copy(t), 500 - i))
    if not q or q in _("Image").lower():
        for i, path in enumerate(clipboard.image_paths()):
            try:
                texture = Gdk.Texture.new_from_filename(path)
            except Exception:  # damaged image must not break Spotlight
                continue
            out.append(Result(_("Image"), _("Clipboard"), texture,
                              lambda t=texture: Gdk.Display.get_default().get_clipboard().set_texture(t),
                              400 - i))
    if not out:
        out.append(Result(_("Clipboard history is empty") if not q else _("No matches"),
                          _("Copied text shows up here. Turn it off in Settings → Privacy."),
                          "edit-paste-symbolic", score=0))
    return out


# --- Projects (git repositories) -------------------------------------------

PROJECT_DIRS = ("~/Projects", "~/projects", "~/src", "~/code", "~/Code", "~/git", "~/dev",
                "~/work", "~/repos", "~/Development")
_projects_cache = (0.0, [])


def find_projects():
    """Git repositories up to two levels below the usual project folders."""
    import time
    global _projects_cache
    stamp, cached = _projects_cache
    if time.time() - stamp < 60:
        return cached
    found = []
    seen = set()
    for base in PROJECT_DIRS:
        base = os.path.expanduser(base)
        if not os.path.isdir(base) or os.path.realpath(base) in seen:
            continue
        seen.add(os.path.realpath(base))
        for depth1 in _subdirs(base):
            if os.path.isdir(os.path.join(depth1, ".git")):
                found.append(depth1)
                continue
            for depth2 in _subdirs(depth1):
                if os.path.isdir(os.path.join(depth2, ".git")):
                    found.append(depth2)
    _projects_cache = (time.time(), found)
    return found


def _subdirs(path):
    try:
        return [e.path for e in os.scandir(path) if e.is_dir() and not e.name.startswith(".")]
    except OSError:
        return []


def _branch(repo):
    try:
        with open(os.path.join(repo, ".git", "HEAD")) as f:
            head = f.read().strip()
        return head.rsplit("/", 1)[-1] if head.startswith("ref:") else head[:8]
    except OSError:
        return ""


def open_project(path):
    """Open a project in the installed code editor, or a terminal there."""
    import shutil
    for editor in ("code", "codium", "zed", "subl"):
        if shutil.which(editor):
            apps.spawn([editor, path])
            return
    apps.spawn(["ptyxis", "--new-window", "--working-directory", path])


def search_projects(query):
    q = query.lower().strip()
    if len(q) < 2:
        return []
    out = []
    home = os.path.expanduser("~")
    for repo in find_projects():
        name = os.path.basename(repo).lower()
        if not (name.startswith(q) or q in name):
            continue
        branch = _branch(repo)
        where = repo.replace(home, "~", 1) + (f" · {branch}" if branch else "")
        out.append(Result(os.path.basename(repo), _("Project · {where}").format(where=where),
                          "folder-code-symbolic" if name.startswith(q) else "folder-symbolic",
                          lambda r=repo: open_project(r), 75 if name.startswith(q) else 45,
                          path=repo))
    return out[:6]


# --- Aurora AI ("?" prefix, and a fallback for questions) -------------------

def search_ai(query):
    from aurora import ai
    if not ai.feature("spotlight"):
        return []
    q = query.strip()
    if q.startswith("?"):
        q = q[1:].strip()
        score = 1000
    elif len(q.split()) >= 3:
        score = 2                         # below real results, above web search
    else:
        return []
    if not q:
        return [Result(_("Ask Aurora…"), _("Type a question after the ?"),
                       "aurora-assistant-symbolic", score=score)]
    return [Result(_("Ask Aurora: “{q}”").format(q=q), _("Aurora AI · opens the Assistant"),
                   "aurora-assistant-symbolic",
                   lambda: apps.spawn(["aurora-assistant", "--ask", q]), score)]


def search_semantic(query, callback):
    """Documents that match the query's meaning (async; calls back on the main loop)."""
    from aurora import ai
    if not ai.feature("semantic-search") or len(query.strip()) < 4 or \
            query.strip()[0] in "?:>":
        return
    import threading
    from gi.repository import GLib

    def work():
        try:
            from aurora.ai import index, providers
            hits = index.search(providers.embed([query])[0], limit=5)
        except Exception as e:  # noqa: BLE001 - search must never break Spotlight
            print(f"aurora: semantic search unavailable: {e}")
            return
        results = []
        home = os.path.expanduser("~")
        # Keep clear matches only: above a floor, and close to the best one.
        best = hits[0][1] if hits else 0
        for path, score, passage in hits:
            if score < max(0.25, best - 0.15):
                continue
            excerpt = " ".join(passage.split())[:90]
            results.append(Result(os.path.basename(path),
                                  _("By meaning · {where} · “{excerpt}…”").format(
                                      where=os.path.dirname(path).replace(home, "~", 1),
                                      excerpt=excerpt),
                                  "text-x-generic",
                                  lambda p=path: Gio.AppInfo.launch_default_for_uri(
                                      Gio.File.new_for_path(p).get_uri(), None),
                                  20 + score))
        if results:
            GLib.idle_add(lambda: (callback(query, results), False)[1])
    threading.Thread(target=work, daemon=True).start()


# --- Settings panels -------------------------------------------------------

SETTINGS_PAGES = [
    ("appearance", N_("Appearance"), "preferences-desktop-appearance-symbolic",
     N_("background wallpaper dark light theme accent color style")),
    ("display", N_("Displays"), "video-display-symbolic",
     N_("monitor screen resolution scale refresh")),
    ("sound", N_("Sound"), "audio-speakers-symbolic",
     N_("audio volume speaker microphone output input")),
    ("network", N_("Network"), "network-wireless-symbolic",
     N_("wifi wireless ethernet internet proxy vpn")),
    ("language", N_("Language & Region"), "preferences-desktop-locale-symbolic",
     N_("language keyboard layout input region format locale")),
    ("datetime", N_("Date & Time"), "preferences-system-time-symbolic",
     N_("clock time zone timezone date")),
    ("power", N_("Power"), "battery-good-symbolic",
     N_("battery sleep suspend screen blank lock")),
    ("health", N_("System Health"), "security-high-symbolic",
     N_("doctor diagnostics problems disk space smart firmware drivers repair check")),
    ("ai", N_("AI"), "aurora-assistant-symbolic",
     N_("artificial intelligence assistant chat model dictation voice speech read aloud")),
    ("about", N_("About"), "help-about-symbolic",
     N_("system information version hardware memory disk")),
]


def search_settings(query, open_settings):
    q = query.lower().strip()
    out = []
    for page, title, icon, keywords in SETTINGS_PAGES:
        t = _(title).lower()
        hay = t + " " + _(keywords).lower() + " " + keywords
        if t.startswith(q):
            score = 65
        elif q in hay:
            score = 40
        else:
            continue
        out.append(Result(_(title), _("Settings"), icon,
                          lambda p=page: open_settings(p), score))
    return out


# --- Files (recent documents) ---------------------------------------------

def search_recent(query):
    from gi.repository import Gtk
    q = query.lower().strip()
    out = []
    for info in Gtk.RecentManager.get_default().get_items()[:200]:
        name = info.get_display_name() or ""
        if q in name.lower() and info.exists():
            uri = info.get_uri()
            path = Gio.File.new_for_uri(uri).get_path() or ""
            out.append(Result(name, _("Recent file"), info.get_gicon() or "text-x-generic",
                              lambda u=uri: Gio.AppInfo.launch_default_for_uri(u, None), 35,
                              path=path))
    return out[:5]


# --- Fallbacks -------------------------------------------------------------

def fallback_results(query):
    q = query.strip()
    out = []
    if q.startswith(">"):
        cmd = q[1:].strip()
        if cmd:
            out.append(Result(_("Run “{cmd}”").format(cmd=cmd), _("Command"),
                              "utilities-terminal-symbolic",
                              lambda: apps.spawn_shell(cmd), 300))
        return out
    url = "https://duckduckgo.com/?q=" + urllib.parse.quote(q)
    out.append(Result(_("Search the web for “{q}”").format(q=q), "duckduckgo.com",
                      "web-browser-symbolic",
                      lambda: Gio.AppInfo.launch_default_for_uri(url, None), 1))
    return out


def search(query, open_settings, refresh=None):
    stripped = query.strip()
    if stripped.startswith(">"):
        return fallback_results(query)
    if stripped.lower().startswith(CLIPBOARD_PREFIX):
        return search_clipboard(stripped)
    if stripped.startswith(":") and len(stripped) > 1:
        return search_emoji(stripped)
    if stripped.startswith("?"):
        return search_ai(stripped)
    off = set(settings.get().get_strv("search-disabled")) if settings.get() else set()
    providers = [("calculator", lambda: search_calculator(query)),
                 ("convert", lambda: search_convert(query, refresh)),
                 ("apps", lambda: search_apps(query)),
                 ("settings", lambda: search_settings(query, open_settings)),
                 ("projects", lambda: search_projects(query)),
                 ("files", lambda: search_recent(query)),
                 ("ai", lambda: search_ai(query))]
    results = [r for name, provider in providers if name not in off for r in provider()]
    results.sort(key=lambda r: -r.score)
    return results[:30] + ([] if "web" in off else fallback_results(query))
