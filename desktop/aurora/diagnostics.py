"""User-reviewed diagnostic bundles; no uploads and no raw logs by default."""

import os
import re
import subprocess


COMMANDS = {
    "install": (("findmnt", "-no", "SOURCE,FSTYPE", "/"),
                ("lsblk", "-o", "NAME,TYPE,FSTYPE,SIZE"),
                ("systemctl", "--failed", "--plain", "--no-legend")),
    "boot": (("systemctl", "show", "greetd", "-p", "ActiveState", "-p", "SubState",
              "-p", "Result"),
             ("findmnt", "-no", "SOURCE,FSTYPE", "/boot/efi"),
             ("systemctl", "--failed", "--plain", "--no-legend")),
    "apps": (("systemctl", "--user", "--failed", "--plain", "--no-legend"),
             ("flatpak", "remotes", "--columns=name,options")),
    # What a maintainer asks for first when a screen, a card or a disk
    # misbehaves: the machine itself.
    "hardware": (("lspci", "-nn"),
                 ("lsblk", "-o", "NAME,TYPE,FSTYPE,SIZE,MODEL,ROTA"),
                 ("free", "-h"),
                 ("systemctl", "--failed", "--plain", "--no-legend")),
}

DETAILS = {
    "install": (("journalctl", "-b", "-p", "err", "-n", "100", "--no-pager"),),
    "boot": (("journalctl", "-b", "-u", "greetd", "-n", "100", "--no-pager"),
             ("journalctl", "-b", "-p", "err", "-n", "100", "--no-pager")),
    "apps": (("journalctl", "--user", "-b", "-p", "err", "-n", "100", "--no-pager"),),
    "hardware": (("journalctl", "-b", "-k", "-p", "warning", "-n", "120", "--no-pager"),),
}


def redact(text):
    home = os.path.expanduser("~")
    if home and home != "/":
        text = text.replace(home, "[HOME]")
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?i)(password|token|secret|api[_-]?key)(\s*[=:]\s*)\S+",
                  r"\1\2[REDACTED]", text)
    # Numbers that name this computer and nothing else: machine and boot ids,
    # disk and partition UUIDs, a serial number printed by a tool.
    text = re.sub(r"(?i)\b[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}\b",
                  "[ID]", text)
    text = re.sub(r"(?i)(serial(?: number)?)(\s*[=:]\s*)\S+", r"\1\2[REDACTED]", text)
    return text


def machine():
    """The few lines about this computer that every report should open with."""
    import platform

    def first_line(path, fallback="?"):
        try:
            with open(path, encoding="utf-8", errors="replace") as stream:
                return stream.readline().strip() or fallback
        except OSError:
            return fallback

    def cpu():
        try:
            with open("/proc/cpuinfo") as stream:
                for line in stream:
                    if line.startswith("model name"):
                        return re.sub(r"\s+", " ", line.split(":", 1)[1].strip())
        except OSError:
            pass
        return platform.processor() or "?"

    def memory():
        try:
            with open("/proc/meminfo") as stream:
                return f"{int(stream.readline().split()[1]) / 1048576:.1f} GiB"
        except (OSError, ValueError, IndexError):
            return "?"

    vendor = first_line("/sys/class/dmi/id/sys_vendor", "")
    model = first_line("/sys/class/dmi/id/product_name", "")
    from aurora import VERSION
    return "\n".join([
        f"Computer: {' '.join(part for part in (vendor, model) if part) or '?'}",
        f"Processor: {cpu()} × {os.cpu_count()}",
        f"Memory: {memory()}",
        f"Kernel: {platform.release()}",
        f"Aurora OS: {VERSION}",
        f"Session: {os.environ.get('AURORA_COMPOSITOR', '?')} "
        f"({os.environ.get('XDG_SESSION_TYPE', '?')})",
        f"Renderer: {os.environ.get('WLR_RENDERER', 'default')}",
    ])


def collect(category, include_logs=False):
    if category not in COMMANDS:
        raise ValueError("unknown diagnostic category")
    lines = ["Aurora OS diagnostic report", f"Category: {category}",
             "No data has been uploaded. Review before saving or sharing.",
             "", redact(machine())]
    if category == "boot":
        path = os.path.join(os.environ.get("XDG_STATE_HOME") or
                            os.path.expanduser("~/.local/state"), "aurora",
                            "compositor-failure.log")
        try:
            with open(path, encoding="utf-8", errors="replace") as stream:
                excerpt = stream.read(65536).splitlines()[-30:]
            lines.extend(["\nCompositor startup failure (last 30 lines):",
                          redact("\n".join(excerpt))])
        except OSError:
            pass
    commands = COMMANDS[category] + (DETAILS[category] if include_logs else ())
    for argv in commands:
        lines.append("\n$ " + " ".join(argv))
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=12,
                                    check=False)
            output = (result.stdout or result.stderr or "(no output)")[:16000]
            lines.append(redact(output))
        except (OSError, subprocess.TimeoutExpired) as err:
            lines.append(str(err))
    if include_logs:
        lines.insert(3, "Detailed logs may contain personal information despite redaction.")
    return "\n".join(lines)
