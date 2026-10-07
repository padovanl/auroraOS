"""Processes, grouped into apps, for the Task Manager. Pure where it can be:
everything reads text from /proc through small functions that tests feed.

A process belongs to an app when it (or an ancestor) was started from the app's
.desktop file: GLib records that in GIO_LAUNCHED_DESKTOP_FILE, and systemd and
Flatpak name the app in the process's cgroup. Everything else of yours is a
background process; other users' processes are the system's.
"""

import os
import re
import signal

PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
CLOCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
SCOPE = re.compile(r"app-(?:flatpak-|gnome-|aurora-)?([A-Za-z0-9._-]+?)(?:@\w+)?(?:-\d+)?\.scope")


def _read(path, mode="r"):
    try:
        with open(path, mode) as f:
            return f.read()
    except OSError:
        return None


def parse_stat(text):
    """(name, state, ppid, cpu ticks, threads, start ticks) from /proc/PID/stat
    (the name may hold spaces and parentheses)."""
    head, _sep, rest = text.rpartition(")")
    name = head.split("(", 1)[1]
    fields = rest.split()
    # fields[0] is the state (3rd field of stat); utime/stime are the 14th/15th.
    return (name, fields[0], int(fields[1]), int(fields[11]) + int(fields[12]),
            int(fields[17]), int(fields[19]))


def parse_io(text):
    """Bytes read and written to storage, from /proc/PID/io."""
    values = {}
    for line in (text or "").splitlines():
        key, _sep, value = line.partition(":")
        if key in ("read_bytes", "write_bytes"):
            values[key] = int(value)
    return values.get("read_bytes", 0) + values.get("write_bytes", 0)


def app_from_environ(data):
    """The desktop file id GLib launched this process from, or None."""
    for entry in (data or b"").split(b"\0"):
        if entry.startswith(b"GIO_LAUNCHED_DESKTOP_FILE="):
            path = entry.split(b"=", 1)[1].decode("utf-8", "replace")
            return os.path.basename(path) or None
    return None


def app_from_cgroup(text):
    """The app id systemd or Flatpak gave this process's scope, or None."""
    match = SCOPE.search(text or "")
    if not match:
        return None
    return match.group(1) + ".desktop"


def total_ticks(stat_text):
    for line in stat_text.splitlines():
        if line.startswith("cpu "):
            return sum(int(v) for v in line.split()[1:9])
    return 0


class Process:
    __slots__ = ("pid", "ppid", "name", "state", "uid", "ticks", "threads", "rss", "io",
                 "app", "cmdline", "exe", "cpu", "disk")

    def __init__(self, pid):
        self.pid = pid
        self.cpu = 0.0
        self.disk = 0.0


def read_process(pid, root="/proc"):
    base = f"{root}/{pid}"
    stat = _read(f"{base}/stat")
    if stat is None:
        return None
    try:
        name, state, ppid, ticks, threads, _start = parse_stat(stat)
    except (IndexError, ValueError):
        return None
    p = Process(pid)
    p.name, p.state, p.ppid, p.ticks, p.threads = name, state, ppid, ticks, threads
    statm = _read(f"{base}/statm") or "0 0"
    parts = statm.split()
    p.rss = int(parts[1]) * PAGE if len(parts) > 1 else 0
    try:
        p.uid = os.stat(base).st_uid
    except OSError:
        p.uid = -1
    p.io = parse_io(_read(f"{base}/io"))
    p.app = app_from_environ(_read(f"{base}/environ", "rb")) or \
        app_from_cgroup(_read(f"{base}/cgroup"))
    raw = _read(f"{base}/cmdline", "rb") or b""
    p.cmdline = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
    try:
        p.exe = os.readlink(f"{base}/exe")
    except OSError:
        p.exe = ""
    return p


class Sampler:
    """Reads every process each time it's called and works out CPU and disk use
    since the previous call."""

    def __init__(self, root="/proc"):
        self.root = root
        self._ticks = {}
        self._io = {}
        self._total = 0
        self.cpus = os.cpu_count() or 1

    def sample(self, interval):
        total = total_ticks(_read(f"{self.root}/stat") or "")
        elapsed = max(total - self._total, 1)
        procs = {}
        for name in os.listdir(self.root):
            if not name.isdigit():
                continue
            p = read_process(int(name), self.root)
            if p is None:
                continue
            before = self._ticks.get(p.pid)
            if before is not None and self._total:
                # A share of the whole machine, as Windows shows it.
                p.cpu = max(0.0, 100.0 * (p.ticks - before) / elapsed)
            io_before = self._io.get(p.pid)
            if io_before is not None and interval > 0:
                p.disk = max(0.0, (p.io - io_before) / interval)
            procs[p.pid] = p
        self._ticks = {pid: p.ticks for pid, p in procs.items()}
        self._io = {pid: p.io for pid, p in procs.items()}
        self._total = total
        return procs


INTERPRETERS = ("python", "python3", "perl", "ruby", "node", "sh", "bash", "gjs",
                "gjs-console", "java")


def display_name(p):
    """A readable name: the kernel cuts names at 15 characters, and for a
    script the interpreter's name says nothing (python3 → aurora-shell)."""
    args = p.cmdline.split()
    base = os.path.basename(args[0]) if args else ""
    if (p.name in INTERPRETERS or base.split(".")[0] in INTERPRETERS) and len(args) > 1:
        for i, arg in enumerate(args[1:], 1):
            if arg == "-m" and i + 1 < len(args):     # python3 -m http.server
                return args[i + 1]
            if arg in ("-c", "-e"):     # code follows ("sh -c 'while …'"), not a name
                return p.name
            if not arg.startswith("-"):
                return os.path.basename(arg)
    if len(p.name) >= 15 and base.startswith(p.name):
        return base
    return p.name


def window_owner_matcher(open_apps):
    """For compositors that don't say which process owns a window (labwc):
    open_apps is [(desktop id, executable name)] of the apps with a window.
    A process belongs to one if it was started from that app's .desktop file or
    runs its executable. Returns {pid-independent key: desktop id} lookups."""
    by_desktop = {d: d for d, _exe in open_apps if d}
    by_exe = {exe: d for d, exe in open_apps if exe}

    def owner(p):
        if p.app in by_desktop:
            return p.app
        for name in (display_name(p), os.path.basename(p.exe or ""), p.name):
            if name in by_exe:
                return by_exe[name]
        return None
    return owner


def group(procs, uid=None, windows=None, open_apps=None):
    """{"apps": {app id: [processes]}, "background": [...], "system": [...]}.

    Apps are what has a window, as in Windows' Task Manager: `windows` maps a
    window's process id to its app id; the process's children join it. Without
    window process ids, `open_apps` (see window_owner_matcher) tells the apps
    with a window; without either, processes started from an app's .desktop
    file count as that app (agents started at login too)."""
    uid = os.getuid() if uid is None else uid
    apps, background, system = {}, [], []
    match = window_owner_matcher(open_apps) if windows is None and open_apps is not None \
        else None

    def owner(p, seen=0):
        while p is not None and seen < 64:
            if windows is not None:
                if p.pid in windows:
                    return windows[p.pid]
            elif match is not None:
                found = match(p)
                if found:
                    return found
            elif p.app:
                return p.app
            p = procs.get(p.ppid)
            seen += 1
        return None

    for p in procs.values():
        if p.uid != uid:
            system.append(p)
            continue
        app = owner(p)
        if app:
            apps.setdefault(app, []).append(p)
        else:
            background.append(p)
    return {"apps": apps, "background": background, "system": system}


def end(pids, force=False):
    """Ask processes to quit (or kill them). Returns the pids that refused."""
    failed = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            failed.append(pid)
    return failed


# --- startup apps ------------------------------------------------------------------

def _desktop_fields(text):
    fields, section = {}, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line
            continue
        if section == "[Desktop Entry]" and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            fields.setdefault(key.strip(), value.strip())
    return fields


def startup_entries(user_dir, system_dirs, desktop="Aurora"):
    """Apps that start when you log in: [{"id", "name", "exec", "icon", "enabled",
    "user"}]. A file of the same name in the user's folder overrides the system's;
    Hidden=true or X-GNOME-Autostart-enabled=false turns it off."""
    found = {}
    for folder, is_user in [(d, False) for d in system_dirs] + [(user_dir, True)]:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            if not name.endswith(".desktop"):
                continue
            text = _read(os.path.join(folder, name))
            if text is None:
                continue
            f = _desktop_fields(text)
            only = [d for d in f.get("OnlyShowIn", "").split(";") if d]
            never = [d for d in f.get("NotShowIn", "").split(";") if d]
            if (only and desktop not in only) or desktop in never:
                found.pop(name, None)
                continue
            enabled = f.get("Hidden", "false").lower() != "true" and \
                f.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
            base = found.get(name, {})
            found[name] = {"id": name, "name": f.get("Name") or base.get("name") or name[:-8],
                           "exec": f.get("Exec") or base.get("exec", ""),
                           "icon": f.get("Icon") or base.get("icon", ""),
                           "enabled": enabled, "user": is_user or base.get("user", False),
                           "system": base.get("system", False) or not is_user}
    return sorted(found.values(), key=lambda e: e["name"].lower())


def set_startup(entry, enabled, user_dir, system_dirs):
    """Turn a startup app on or off, the freedesktop way: an override in the
    user's autostart folder (the system's file is never touched)."""
    path = os.path.join(user_dir, entry["id"])
    source = None
    for folder in [user_dir] + list(system_dirs):
        candidate = os.path.join(folder, entry["id"])
        if os.path.exists(candidate):
            source = candidate
            break
    text = _read(source) if source else ""
    lines = [line for line in (text or "[Desktop Entry]\nType=Application\n").splitlines()
             if not line.startswith(("Hidden=", "X-GNOME-Autostart-enabled="))]
    out = []
    for line in lines:
        out.append(line)
        if line.strip() == "[Desktop Entry]":
            out.append(f"Hidden={'false' if enabled else 'true'}")
            out.append(f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}")
    os.makedirs(user_dir, exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
