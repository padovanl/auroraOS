#!/usr/bin/env python3
"""Build Aurora OS's official documentation: docs/manual/.

Pages are written by hand in docs/_manual/*.html: each file is one section, and
holds its pages, each starting with

    <!-- page: slug | Title | One-line description -->

The reference parts are generated from the code itself, so they can't drift
out of date: a page asks for one with <!-- gen:NAME --> (see GENERATORS):
keyboard shortcuts from the labwc configuration, every GSettings key from the
schema, every option of every Settings page, widgets and their options, shell
commands, command-line tools, the Dev Hub and Game Hub catalogs, the default
apps, the languages.

Output: one HTML page per slug, a search index (search.json), manual.css and
manual.js. Run `make manual` (or this script); the static tests fail when the
generated files are stale.
"""

import ast
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "_manual")
OUT = os.path.join(ROOT, "docs", "manual")
DESKTOP = os.path.join(ROOT, "desktop")
sys.path.insert(0, DESKTOP)
REPO_URL = "https://github.com/padovanl/auroraOS"
VERSION = "0.1"


def esc(text):
    return html.escape(str(text), quote=True)


def slugify(text):
    text = re.sub(r"<[^>]+>", "", text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def table(headers, rows, cls=""):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table class="{cls}"><thead><tr>{head}</tr></thead>' \
           f"<tbody>{body}</tbody></table></div>"


# --- keys ---------------------------------------------------------------------------

KEY_NAMES = {"W": "Super", "S": "Shift", "C": "Ctrl", "A": "Alt", "space": "Space",
             "Return": "Enter", "period": ".", "slash": "/", "equal": "=", "minus": "−",
             "Print": "Print Screen", "Escape": "Esc", "Tab": "Tab", "Left": "←",
             "Right": "→", "Up": "↑", "Down": "↓", "Super_L": "Super (tap)",
             "XF86AudioRaiseVolume": "Volume Up", "XF86AudioLowerVolume": "Volume Down",
             "XF86AudioMute": "Mute", "XF86MonBrightnessUp": "Brightness Up",
             "XF86MonBrightnessDown": "Brightness Down"}


def kbd(combo):
    """labwc's "W-S-space" → <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd>."""
    parts = combo.split("-") if combo not in KEY_NAMES else [combo]
    keys = []
    for part in parts:
        name = KEY_NAMES.get(part, part.upper() if len(part) == 1 else part)
        keys.append(f"<kbd>{esc(name)}</kbd>")
    return "+".join(keys)


def gtk_accel(accel):
    """GTK's "<Ctrl><Shift>z" → <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>."""
    mods = re.findall(r"<(\w+)>", accel)
    key = re.sub(r"<\w+>", "", accel)
    names = {"Primary": "Ctrl", "Control": "Ctrl", "Ctrl": "Ctrl", "Shift": "Shift",
             "Alt": "Alt", "Super": "Super"}
    keys = [names.get(m, m) for m in mods] + [KEY_NAMES.get(key, key.upper() if len(key) == 1
                                                              else key)]
    return "+".join(f"<kbd>{esc(k)}</kbd>" for k in keys)


def describe_dicts():
    """The words Settings uses for each shortcut (settingsapp/inputs.py)."""
    tree = ast.parse(read("desktop", "aurora", "settingsapp", "inputs.py"))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) and \
                isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("commands",
                                                                                  "actions"):
            d = {}
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Call) and v.args:
                    d[k.value] = v.args[0].value
            found[node.targets[0].id] = d
    return found.get("commands", {}), found.get("actions", {})


def describe(action, command, attrs, commands, actions):
    if action == "Execute":
        return commands.get(command, f"Run <code>{esc(command)}</code>")
    if action == "SnapToEdge":
        return f"Snap the window to the {attrs.get('direction')} half"
    if action == "SnapToRegion":
        region = attrs.get("region", "")
        if region.endswith("third"):
            return f"Move the window to the {region.split('-')[0]} third"
        return f"Move the window to the {region.replace('-', ' ')} quarter"
    if action == "GoToDesktop":
        to = attrs.get("to")
        return {"left": "Previous workspace", "right": "Next workspace"}.get(
            to, f"Go to workspace {to}")
    if action == "SendToDesktop":
        return f"Move the window to workspace {attrs.get('to')}"
    return actions.get(action, action)


LABWC_ONLY = {"ShowMenu", "ToggleMagnify", "ZoomIn", "ZoomOut"}


def gen_shortcuts():
    commands, actions = describe_dicts()
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(read("desktop", "data", "labwc", "rc.xml"), parser=parser)
    keyboard = root.find("keyboard")
    groups, current = [], None
    for child in keyboard:
        if child.tag is ET.Comment:
            title = child.text.strip().split(":")[0].split("(")[0].strip().rstrip(".")
            current = (title, [])
            groups.append(current)
            continue
        if child.tag != "keybind":
            continue
        if current is None:
            current = ("General", [])
            groups.append(current)
        action = child.find("action")
        name = action.get("name")
        text = describe(name, action.get("command"), action.attrib, commands, actions)
        if name in LABWC_ONLY:
            text += ' <span class="badge">Compatibility session</span>'
        current[1].append((child.get("key"), text))
    out = []
    for title, binds in groups:
        # Several keys for the same thing share a row.
        merged = {}
        for key, text in binds:
            merged.setdefault(text, []).append(key)
        rows = [(" or ".join(kbd(k) for k in keys), text) for text, keys in merged.items()]
        out.append(f'<h3 id="keys-{slugify(title)}">{esc(title)}</h3>')
        out.append(table(["Keys", "What it does"], rows, "keys"))
    return "\n".join(out)


FILES_ACTIONS = {
    "back": "Back", "forward": "Forward", "up": "Parent folder", "home": "Home folder",
    "location": "Type a location", "open": "Open the selection",
    "copy": "Copy", "new-tab": "New tab", "close-tab": "Close tab", "next-tab": "Next tab",
    "previous-tab": "Previous tab", "duplicate": "Duplicate", "cut": "Cut", "paste": "Paste",
    "undo": "Undo the last file operation", "redo": "Redo", "rename": "Rename",
    "trash": "Move to the Trash", "delete": "Delete permanently (asks first)",
    "new-folder": "New folder", "properties": "Properties", "select-all": "Select all",
    "reload": "Reload", "show-hidden": "Show or hide hidden files",
    "list-view": "List or grid view", "search": "Search in this folder",
}


def gen_files_shortcuts():
    tree = ast.parse(read("desktop", "aurora", "files", "window.py"))
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "add" and \
                len(node.args) >= 3 and isinstance(node.args[2], ast.List):
            name = node.args[0].value
            accels = [e.value for e in node.args[2].elts]
            if accels:
                rows.append((" or ".join(gtk_accel(a) for a in accels),
                             FILES_ACTIONS.get(name, name)))
    rows.append(("<kbd>Space</kbd>", "Quick Look the selection"))
    return table(["Keys", "What it does"], rows, "keys")


# --- shell, tools -------------------------------------------------------------------

SHELL_COMMANDS = {
    "launcher": ("[spotlight|grid]", "Open Spotlight search, or Launchpad with <code>grid</code>."),
    "search": ("TEXT", "Open Spotlight with TEXT already typed."),
    "dictate": ("", "Start or stop dictation."),
    "read-aloud": ("", "Read the selected text aloud."),
    "assistant": ("", "Open the Aurora Assistant with the keyboard."),
    "writing": ("", "Writing Tools for the selected text."),
    "overview": ("", "Show all open windows."),
    "snap-layouts": ("", "Show Snap Layouts for the focused window."),
    "always-on-top": ("", "Keep the focused window above the others, or stop."),
    "snap": ("ZONE", "Put the focused window in a zone: <code>left</code>, <code>right</code>, "
             "<code>left-third</code>, <code>center-third</code>, <code>right-third</code>, "
             "<code>top-left</code> … <code>bottom-right</code>."),
    "clipboard": ("", "Clipboard history in Spotlight."),
    "emoji": ("", "The emoji picker in Spotlight."),
    "volume": ("up|down|mute", "Change the volume, with the on-screen indicator."),
    "brightness": ("up|down", "Change the screen brightness."),
    "screenshot": ("[area|text|pin]", "Screenshot of the screen or of an area, copy the text in an area, or pin an area to the screen."),
    "record": ("", "Start or stop screen recording."),
    "colorpick": ("", "Pick a color from the screen; its hex code is copied."),
    "shortcuts": ("", "Show every keyboard shortcut."),
    "edit-widgets": ("", "Edit the desktop widgets."),
    "keep-awake": ("", "Turn Keep Awake on or off."),
    "quick-settings": ("", "Open the Control Center."),
    "logout": ("", "Log out."),
    "focus": ("", "Start or stop a focus session."),
    "windows": ("", "Print the open windows as JSON, one per line (for scripts and tests)."),
}


def gen_shell_commands():
    text = read("desktop", "aurora", "shell", "app.py")
    found = re.findall(r'cmd == "([a-z-]+)"', text) + ["windows"]
    rows = []
    for name in found:
        args, what = SHELL_COMMANDS.get(name, ("", ""))
        rows.append((f"<code>aurora-shell {esc(name)} {esc(args)}</code>".replace(" </code>",
                                                                             "</code>"), what))
    return table(["Command", "What it does"], rows)


CLI_TOOLS = {
    "aurora-session": "Starts a desktop session (used by the login screen): Aurora (Wayfire) or Aurora Compatibility (labwc).",
    "aurora-shell": "The desktop shell: top bar, dock, desktop, Spotlight, notifications. With a command, talks to the running shell (see Shell commands).",
    "aurora-settings": "Settings. <code>--page NAME</code> opens a page (for example <code>display</code>, <code>storage</code>).",
    "aurora-files": "Files. Takes folders or locations (<code>aurora-files ~/Downloads</code>, <code>aurora-files smb://nas/share</code>).",
    "aurora-taskmanager": "Task Manager.",
    "aurora-assistant": "The Aurora Assistant. <code>--focus</code>, <code>--ask TEXT</code>, <code>--file PATH [--summarize]</code>, <code>--writing</code>.",
    "aurora-ai": "Aurora AI from the terminal (the <code>ask</code> and <code>why</code> helpers use it).",
    "aurora-devhub": "Dev Hub.",
    "aurora-gamehub": "Game Hub.",
    "aurora-welcome": "The first-run tour.",
    "aurora-quicklook": "Quick Look a file: <code>aurora-quicklook FILE</code>.",
    "aurora-clipboard": "Clipboard history store (fed by <code>wl-paste --watch</code>).",
    "aurora-lock": "Lock the screen.",
    "aurora-idle": "Screen blanking, locking and suspend on inactivity (started by the session).",
    "aurora-idle-suspend": "Suspends on inactivity when allowed (battery or plugged in).",
    "aurora-autostart": "Starts the apps registered in XDG autostart, honoring OnlyShowIn, NotShowIn, Hidden and TryExec.",
    "aurora-look": "Writes the GTK stylesheet imports for the chosen window style.",
    "aurora-greeter": "The login screen (run by greetd).",
    "aurora-installer": "Opens the installer in the live session.",
    "aurora-wayfire-config": "Renders <code>~/.config/aurora/wayfire.ini</code> from your settings.",
}


def gen_cli():
    names = sorted(n for n in os.listdir(os.path.join(DESKTOP, "bin"))
                   if not n.startswith((".", "__")))
    rows = [(f"<code>{esc(n)}</code>", CLI_TOOLS.get(n, "")) for n in names]
    rows += [("<code>ask</code>", "Ask Aurora AI for a command: <code>ask \"find big files\"</code>; it runs the command only if you answer y."),
             ("<code>why</code>", "Explain an error: <code>make 2&gt;&amp;1 | why</code>."),
             ("<code>portop</code>", "Which process holds a port, and stop it with one key."),
             ("<code>pkgtui</code>", "Search, install, remove and upgrade apt, Flatpak and Snap packages in one terminal UI.")]
    return table(["Command", "What it does"], rows)


# --- settings and schema --------------------------------------------------------------

def gen_gsettings():
    root = ET.fromstring(read("desktop", "data", "schemas", "org.aurora.desktop.gschema.xml"))
    rows = []
    for key in root.iter("key"):
        default = (key.findtext("default") or "").strip()
        summary = (key.findtext("summary") or "").strip()
        description = (key.findtext("description") or "").strip()
        choices = [c.get("value") for c in key.iter("choice")]
        rng = key.find("range")
        extra = []
        if choices:
            extra.append("One of " + ", ".join(f"<code>{esc(c or '(empty)')}</code>" for c in choices))
        if rng is not None:
            extra.append(f"From {rng.get('min')} to {rng.get('max')}")
        text = esc(summary) + (f"<br><span class=\"muted\">{esc(description)}</span>"
                               if description else "")
        if extra:
            text += f"<br><span class=\"muted\">{'; '.join(extra)}.</span>"
        rows.append((f"<code>{esc(key.get('name'))}</code>", f"<code>{esc(key.get('type'))}</code>",
                     f"<code>{esc(default)}</code>", text))
    intro = ("<p>All in the schema <code>org.aurora.desktop</code> "
             f"({len(rows)} keys). Read one with <code>gsettings get org.aurora.desktop KEY</code>, "
             "change it with <code>gsettings set org.aurora.desktop KEY VALUE</code>, and go "
             "back to the default with <code>gsettings reset org.aurora.desktop KEY</code>.</p>")
    return intro + table(["Key", "Type", "Default", "Meaning"], rows, "gsettings")


ROW_CALLS = {"switch_row", "combo_row"}
ROW_CLASSES = {"ActionRow", "SwitchRow", "ButtonRow", "ComboRow", "SpinRow", "EntryRow",
               "PasswordEntryRow", "ExpanderRow"}


def _string(node):
    """The English text in _("…"), N_("…") or a plain string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("_", "N_") and node.args \
            and isinstance(node.args[0], ast.Constant):
        return node.args[0].value
    return None


HELPER_ROW = re.compile(r"^_?(combo|switch|scale|spin|entry|toggle|row|choice|slider)")


def _choices(node):
    """The labels of a choice list: [_("A"), _("B")] or [("a", _("A")), …]."""
    out = []
    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            text = _string(elt)
            if text is None and isinstance(elt, ast.Tuple) and len(elt.elts) >= 2:
                text = _string(elt.elts[1])
            if text:
                out.append(text)
    return out


class _PageVisitor(ast.NodeVisitor):
    """Walks a page class in source order, collecting groups and their rows."""

    def __init__(self, helpers=None):
        self.groups = []
        self.loop_labels = []
        # Classes a page builds parts of itself with (Appearance → BackgroundSection).
        self.helpers = helpers or {}
        self.seen = set()

    def _add(self, label, help_=None, choices=()):
        if not self.groups:
            self.groups.append(("", []))
        row = (label, help_, tuple(choices))
        if row not in self.groups[-1][1]:
            self.groups[-1][1].append(row)

    def visit_For(self, node):
        labels = _choices(node.iter)
        self.loop_labels.append(labels)
        self.generic_visit(node)
        self.loop_labels.pop()

    def visit_Call(self, node):
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None) or ""
        args = node.args
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        if name in self.helpers and name not in self.seen:
            self.seen.add(name)
            for stmt in self.helpers[name].body:
                self.visit(stmt)
        if name == "group" and args:
            text = _string(args[0])
            if text and "not installed" not in text:
                self.groups.append((text, []))
        elif name in ROW_CALLS or name in ROW_CLASSES or (
                isinstance(func, ast.Attribute) and HELPER_ROW.match(name)):
            label, help_, choices = None, None, []
            if name in ROW_CLASSES:
                label = _string(kw.get("title")) if "title" in kw else None
                help_ = _string(kw["subtitle"]) if "subtitle" in kw else None
            else:
                # combo_row(title, labels, …), switch_row(title, …), or a page's own
                # helper self._combo(group, title, key, options).
                for index, arg in enumerate(args[:2]):
                    label = _string(arg)
                    if label:
                        rest = args[index + 1:]
                        break
                else:
                    rest = []
                    if args and isinstance(args[0], ast.Name) and self.loop_labels \
                            and self.loop_labels[-1]:
                        for text in self.loop_labels[-1]:
                            self._add(text)
                help_ = _string(kw["subtitle"]) if "subtitle" in kw else None
                for arg in rest:
                    found = _choices(arg)
                    if found:
                        choices = found
                        break
            if label:
                self._add(label, help_, choices)
        self.generic_visit(node)


def settings_pages():
    """[(module, class, page title, [(group, [(option, help, choices)])])] in the
    sidebar's order."""
    folder = os.path.join(DESKTOP, "aurora", "settingsapp")
    app_src = read("desktop", "aurora", "settingsapp", "app.py")
    order = re.findall(r"\b([A-Z]\w+)\b", app_src[app_src.index("SECTIONS = ["):
                                                  app_src.index("PAGES =")])
    found = {}
    trees = {name: ast.parse(read("desktop", "aurora", "settingsapp", name))
             for name in os.listdir(folder) if name.endswith(".py")}
    helpers = {cls.name: cls for tree in trees.values() for cls in tree.body
               if isinstance(cls, ast.ClassDef)}
    for name, tree in trees.items():
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            title = None
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and getattr(stmt.targets[0], "id", "") == "title":
                    title = _string(stmt.value)
            if not title:
                continue
            visitor = _PageVisitor({k: v for k, v in helpers.items() if k != cls.name})
            for stmt in cls.body:
                visitor.visit(stmt)
            found[cls.name] = (name, cls.name, title, visitor.groups)
    return [found[c] for c in order if c in found]


def gen_settings_pages():
    out = []
    for module, _cls, title, groups in settings_pages():
        out.append(f'<h3 id="page-{slugify(title)}">{esc(title)}</h3>')
        items = []
        for group, rows in groups:
            if not rows and not group:
                continue
            opts = "".join(f"<li><strong>{esc(label)}</strong>"
                           + (f" <span class=\"muted\">({esc(', '.join(choices))})</span>"
                              if choices else "")
                           + (f" — {esc(help_)}" if help_ else "") + "</li>"
                           for label, help_, choices in rows)
            head = f"<p class=\"group\">{esc(group)}</p>" if group else ""
            items.append(head + (f"<ul>{opts}</ul>" if opts else ""))
        out.append("".join(items) or "<p class=\"muted\">This page shows information only.</p>")
        out.append(f'<p class="source">Source: <code>desktop/aurora/settingsapp/{esc(module)}</code></p>')
    return "\n".join(out)


def gen_settings_list():
    rows = []
    app_src = read("desktop", "aurora", "settingsapp", "app.py")
    for module, cls, title, _groups in settings_pages():
        tree = ast.parse(read("desktop", "aurora", "settingsapp", module))
        page_id = ""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == cls:
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and getattr(stmt.targets[0], "id", "") == "page_id":
                        page_id = stmt.value.value
        rows.append((esc(title), f"<code>aurora-settings --page {esc(page_id)}</code>"))
    del app_src
    return table(["Page", "Open it directly"], rows)


# --- widgets ----------------------------------------------------------------------------

def gen_widgets():
    sources = {}
    for name in ("widgets.py", "devwidgets.py", "morewidgets.py"):
        sources[name] = ast.parse(read("desktop", "aurora", "shell", name))
    titles, sections, options, classes = {}, [], {}, {}
    for node in ast.walk(sources["widgets.py"]):
        if isinstance(node, ast.FunctionDef) and node.name == "kinds":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Dict):
                    for k, v in zip(sub.keys, sub.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Tuple):
                            titles[k.value] = _string(v.elts[0])
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SECTIONS":
            for t in node.value.elts:
                sections.append((t.elts[0].value, [e.value for e in t.elts[1].elts]))
    for tree in sources.values():
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            kind, opts, doc = None, [], ast.get_docstring(cls)
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and getattr(stmt.targets[0], "id", "") == "kind":
                    kind = stmt.value.value
                if isinstance(stmt, ast.Assign) and getattr(stmt.targets[0], "id", "") == "OPTIONS":
                    for opt in stmt.value.elts:
                        label = _string(opt.elts[1])
                        kindname = opt.elts[2].value
                        choices = []
                        if kindname == "choice" and isinstance(opt.elts[4], ast.List):
                            choices = [_string(c.elts[1]) for c in opt.elts[4].elts]
                        opts.append((label, kindname, choices))
            if kind:
                options[kind] = opts
                classes[kind] = doc
    names = {"everyday": "Everyday", "productivity": "Productivity", "system": "System",
             "developers": "Developers", "gamers": "Gamers"}
    out = []
    for section, kinds_ in sections:
        rows = []
        for kind in kinds_:
            opts = options.get(kind, [])
            text = "; ".join(
                f"<strong>{esc(label)}</strong>"
                + (f" ({esc(', '.join(c for c in choices if c))})" if choices else
                   " (on/off)" if k == "switch" else " (a folder)" if k == "folder" else
                   " (text)" if k == "text" else " (a date)" if k == "date" else "")
                for label, k, choices in opts) or "—"
            desc = (classes.get(kind) or "").split("\n")[0]
            rows.append((esc(titles.get(kind, kind)), esc(desc), text))
        out.append(f'<h3 id="widgets-{section}">{names.get(section, section)}</h3>')
        out.append(table(["Widget", "What it shows", "Customize…"], rows))
    return "\n".join(out)


# --- catalogs, apps, languages --------------------------------------------------------

def gen_devhub():
    from aurora.devhub import recipes
    out = []
    by_cat = {}
    for r in recipes.RECIPES:
        by_cat.setdefault(r.get("cat"), []).append(r)
    for cat, title in recipes.CATEGORIES:
        rows = [(esc(r.get("name", r.get("id"))), esc(r.get("desc", ""))) for r in by_cat.get(cat, [])]
        if rows:
            out.append(f'<h3 id="devhub-{cat}">{esc(title)}</h3>')
            out.append(table(["Tool", "What it is"], rows))
    return "\n".join(out)


def gen_gamehub():
    from aurora.devhub import games
    rows = []
    titles = dict(games.CATEGORIES)
    for r in games.RECIPES:
        rows.append((esc(titles.get(r.get("cat"), "")), esc(r.get("name")), esc(r.get("desc", ""))))
    return table(["Group", "App", "What it is"], rows)


def gen_apps():
    rows = []
    for line in read("config", "apps.manifest").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) >= 3:
            rows.append((esc(cols[0]), esc(cols[1]), f"<code>{esc(cols[2])}</code>"))
    return table(["Group", "App", "Desktop file"], rows)


def gen_locales():
    rows = []
    for line in read("config", "locales.list").splitlines():
        line = line.split("#")[0].strip()
        if line:
            rows.append((f"<code>{esc(line.split()[0])}</code>",))
    return "<p>" + ", ".join(r[0] for r in rows) + "</p>"


def gen_sessions():
    rows = []
    folder = os.path.join(DESKTOP, "data", "wayland-sessions")
    for name in sorted(os.listdir(folder)):
        fields = dict(line.split("=", 1) for line in read("desktop", "data", "wayland-sessions",
                                                           name).splitlines() if "=" in line)
        rows.append((esc(fields.get("Name", "")), esc(fields.get("Comment", "")),
                     f"<code>{esc(fields.get('Exec', ''))}</code>"))
    return table(["Session", "What it is", "Command"], rows)


def gen_env():
    rows = []
    for line in read("desktop", "bin", "aurora-session").splitlines():
        m = re.match(r'\s*export (\w+)="?([^"]*)"?$', line)
        if m and "$" not in m.group(2):
            rows.append((f"<code>{esc(m.group(1))}</code>", f"<code>{esc(m.group(2))}</code>"))
    return table(["Variable", "Value in an Aurora session"], rows)


def gen_hotcorners():
    text = read("desktop", "aurora", "settingsapp", "inputs.py")
    block = text[text.index('actions = [("none"'):]
    block = block[:block.index("]") + 1]
    pairs = re.findall(r'\("([a-z-]+)", _\("([^"]+)"\)\)', block)
    return table(["Setting", "Action"], [(f"<code>{esc(a)}</code>", esc(b)) for a, b in pairs])


GENERATORS = {
    "shortcuts": gen_shortcuts, "files-shortcuts": gen_files_shortcuts,
    "shell-commands": gen_shell_commands, "cli": gen_cli, "gsettings": gen_gsettings,
    "settings-pages": gen_settings_pages, "settings-list": gen_settings_list,
    "widgets": gen_widgets, "devhub": gen_devhub, "gamehub": gen_gamehub, "apps": gen_apps,
    "locales": gen_locales, "sessions": gen_sessions, "env": gen_env,
    "hotcorners": gen_hotcorners,
}


# --- pages ------------------------------------------------------------------------------

PAGE_RE = re.compile(r"<!--\s*page:\s*([a-z0-9-]+)\s*\|\s*([^|]+?)\s*\|\s*(.*?)\s*-->")
SECTION_RE = re.compile(r"<!--\s*section:\s*(.+?)\s*-->")


def load_pages():
    sections = []
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".html"):
            continue
        text = read("docs", "_manual", name)
        title = SECTION_RE.search(text).group(1)
        pages = []
        marks = list(PAGE_RE.finditer(text))
        for i, m in enumerate(marks):
            body = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
            pages.append({"slug": m.group(1), "title": m.group(2), "desc": m.group(3),
                          "body": body.strip(), "section": title})
        sections.append((title, pages))
    return sections


def expand(body):
    def run(m):
        name = m.group(1)
        if name not in GENERATORS:
            raise SystemExit(f"unknown generator: {name}")
        return f'<div class="generated" data-from="{name}">' + GENERATORS[name]() + "</div>"
    return re.sub(r"<!--\s*gen:([a-z-]+)\s*-->", run, body)


def add_ids(body):
    """Give every h2/h3 an id (for links and the page's table of contents)."""
    seen = set()

    def repl(m):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        if "id=" in attrs:
            ident = re.search(r'id="([^"]+)"', attrs).group(1)
        else:
            ident = slugify(inner)
            while ident in seen:
                ident += "-2"
            attrs += f' id="{ident}"'
        seen.add(ident)
        return f'<{tag}{attrs}><a class="anchor" href="#{ident}" aria-hidden="true">#</a>{inner}</{tag}>'
    return re.sub(r"<(h[23])([^>]*)>(.*?)</\1>", repl, body, flags=re.S)


def toc(body):
    items = re.findall(r'<(h[23])[^>]*id="([^"]+)"[^>]*>(?:<a[^>]*>#</a>)?(.*?)</\1>', body, re.S)
    if len(items) < 2:
        return ""
    lis = "".join(f'<li class="{tag}"><a href="#{ident}">{re.sub(r"<[^>]+>", "", text)}</a></li>'
                  for tag, ident, text in items)
    return f'<nav class="toc" aria-label="On this page"><p>On this page</p><ul>{lis}</ul></nav>'


def plain(body):
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


ICON = ('<svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true"><defs><linearGradient '
        'id="lg" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#ff6f91"/><stop '
        'offset="1" stop-color="#a970ff"/></linearGradient></defs><path d="M6 26 16 5l10 21" '
        'fill="none" stroke="url(#lg)" stroke-width="3.2" stroke-linecap="round" '
        'stroke-linejoin="round"/><circle cx="16" cy="21" r="2.2" fill="#ffb86b"/></svg>')


def nav_html(sections, current):
    out = []
    for title, pages in sections:
        open_ = any(p["slug"] == current for p in pages)
        links = "".join(
            f'<li><a href="{p["slug"]}.html"{" aria-current=\"page\"" if p["slug"] == current else ""}>'
            f'{esc(p["title"])}</a></li>' for p in pages)
        out.append(f'<details{" open" if open_ or current == "index" else ""}><summary>'
                   f'{esc(title)}</summary><ul>{links}</ul></details>')
    return "".join(out)


def page_html(title, desc, body, sections, current, crumbs, prev_page, next_page, updated, src):
    pager = '<nav class="pager">'
    if prev_page:
        pager += f'<a class="prev" href="{prev_page["slug"]}.html"><span>Previous</span>{esc(prev_page["title"])}</a>'
    if next_page:
        pager += f'<a class="next" href="{next_page["slug"]}.html"><span>Next</span>{esc(next_page["title"])}</a>'
    pager += "</nav>"
    edit = f'{REPO_URL}/edit/main/docs/_manual/{src}' if src else REPO_URL
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Aurora OS Documentation</title>
<meta name="description" content="{esc(desc)}">
<link rel="stylesheet" href="manual.css">
<script>try{{var t=localStorage.getItem("aurora-docs-theme");if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
</head>
<body>
<!-- Generated by tools/build-manual.py from docs/_manual/. Edit those, not this file. -->
<header class="top">
  <button class="menu" aria-label="Contents" aria-expanded="false">☰</button>
  <a class="brand" href="index.html">{ICON}<span>Aurora OS <b>Documentation</b></span></a>
  <span class="version">v{VERSION}</span>
  <div class="search"><input type="search" id="q" placeholder="Search the documentation" autocomplete="off" aria-label="Search"><kbd class="hint">/</kbd><div id="results" role="listbox"></div></div>
  <nav class="links"><a href="../index.html">Website</a><a href="{REPO_URL}">Source</a>
  <button class="theme" aria-label="Light or dark">◐</button></nav>
</header>
<div class="layout">
  <aside class="sidebar"><nav aria-label="Documentation">{nav_html(sections, current)}</nav></aside>
  <main>
    <article>
      <p class="crumbs">{crumbs}</p>
      <h1>{esc(title)}</h1>
      {f'<p class="lead">{esc(desc)}</p>' if desc else ""}
      {body}
      <footer class="meta">{f"Last updated {updated} · " if updated else ""}<a href="{edit}">Edit this page</a> · Aurora OS {VERSION} · GPL-3.0-or-later</footer>
      {pager}
    </article>
    {toc(body)}
  </main>
</div>
<script src="manual.js"></script>
</body>
</html>
"""


def build():
    sections = load_pages()
    flat = [p for _t, pages in sections for p in pages]
    slugs = [p["slug"] for p in flat]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    if dupes:
        raise SystemExit(f"duplicate page slugs: {dupes}")
    os.makedirs(OUT, exist_ok=True)
    index = []
    files = {}
    for src_name in sorted(os.listdir(SRC)):
        if src_name.endswith(".html"):
            text = read("docs", "_manual", src_name)
            for m in PAGE_RE.finditer(text):
                files[m.group(1)] = src_name
    for i, page in enumerate(flat):
        body = add_ids(expand(page["body"]))
        # Links between pages: href="#slug" style shortcuts are written as page.html.
        missing = [s for s in re.findall(r'href="([a-z0-9-]+)\.html', body) if s not in slugs
                   and s != "index"]
        if missing:
            raise SystemExit(f"{page['slug']}: links to missing pages {missing}")
        crumbs = f'<a href="index.html">Documentation</a> › {esc(page["section"])}'
        html_out = page_html(page["title"], page["desc"], body, sections, page["slug"], crumbs,
                             flat[i - 1] if i else None, flat[i + 1] if i + 1 < len(flat) else None,
                             "", files.get(page["slug"]))
        with open(os.path.join(OUT, f"{page['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(html_out)
        heads = [re.sub(r"<[^>]+>", "", h) for h in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", body, re.S)]
        index.append({"u": f"{page['slug']}.html", "t": page["title"], "s": page["section"],
                      "d": page["desc"], "h": [h.lstrip("#") for h in heads],
                      "x": plain(body)[:6000]})
    # The home page: every section and its pages.
    cards = []
    for title, pages in sections:
        lis = "".join(f'<li><a href="{p["slug"]}.html">{esc(p["title"])}</a><span>{esc(p["desc"])}</span></li>'
                      for p in pages)
        cards.append(f'<section class="area"><h2 id="{slugify(title)}">{esc(title)}</h2><ul>{lis}</ul></section>')
    home = ('<p>This is the reference documentation for Aurora OS: how to install it, how '
            'every part of the desktop works, every setting, every keyboard shortcut, the '
            'sessions and services behind it, and what to do when something goes wrong. '
            'Use the search box (press <kbd>/</kbd>) or browse by topic.</p>'
            '<div class="areas">' + "".join(cards) + "</div>")
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page_html("Aurora OS Documentation", f"The official documentation for Aurora OS {VERSION}.",
                          home, sections, "index", '<a href="index.html">Documentation</a>',
                          None, flat[0] if flat else None, "", None))
    with open(os.path.join(OUT, "search.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    for asset in ("manual.css", "manual.js"):
        with open(os.path.join(SRC, asset), encoding="utf-8") as src, \
                open(os.path.join(OUT, asset), "w", encoding="utf-8") as dst:
            dst.write(src.read())
    print(f"manual: {len(flat)} pages in {len(sections)} sections → docs/manual/")


def check():
    """Exit 1 when docs/manual/ differs from what the sources and the code give."""
    import filecmp
    import tempfile
    global OUT
    real = OUT
    with tempfile.TemporaryDirectory() as tmp:
        OUT = tmp
        build()
        OUT = real
        stale = [name for name in sorted(os.listdir(tmp))
                 if not os.path.exists(os.path.join(real, name))
                 or not filecmp.cmp(os.path.join(tmp, name), os.path.join(real, name), shallow=False)]
        extra = [name for name in os.listdir(real) if not os.path.exists(os.path.join(tmp, name))]
    if stale or extra:
        print(f"docs/manual is out of date ({', '.join((stale + extra)[:8])}…): run `make manual`")
        sys.exit(1)
    print("documentation is up to date")


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
