"""Search providers for the launcher."""

import ast
import math
import operator
import os
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable

from gi.repository import Gdk, Gio

from aurora import apps
from aurora.i18n import N_, _


@dataclass
class Result:
    title: str
    subtitle: str = ""
    icon: object = "application-x-executable"   # icon name or Gio.Icon
    activate: Callable = field(default=lambda: None)
    score: float = 0.0


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
                              lambda a=app: apps.launch(a), score))
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
            out.append(Result(name, _("Recent file"), info.get_gicon() or "text-x-generic",
                              lambda u=uri: Gio.AppInfo.launch_default_for_uri(u, None), 35))
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


def search(query, open_settings):
    if query.strip().startswith(">"):
        return fallback_results(query)
    results = (search_calculator(query) + search_apps(query)
               + search_settings(query, open_settings) + search_recent(query))
    results.sort(key=lambda r: -r.score)
    return results[:30] + fallback_results(query)
