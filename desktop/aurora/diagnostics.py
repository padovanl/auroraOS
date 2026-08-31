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
}

DETAILS = {
    "install": (("journalctl", "-b", "-p", "err", "-n", "100", "--no-pager"),),
    "boot": (("journalctl", "-b", "-u", "greetd", "-n", "100", "--no-pager"),
             ("journalctl", "-b", "-p", "err", "-n", "100", "--no-pager")),
    "apps": (("journalctl", "--user", "-b", "-p", "err", "-n", "100", "--no-pager"),),
}


def redact(text):
    home = os.path.expanduser("~")
    if home and home != "/":
        text = text.replace(home, "[HOME]")
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?i)(password|token|secret|api[_-]?key)(\s*[=:]\s*)\S+",
                  r"\1\2[REDACTED]", text)
    return text


def collect(category, include_logs=False):
    if category not in COMMANDS:
        raise ValueError("unknown diagnostic category")
    lines = ["Aurora OS diagnostic report", f"Category: {category}",
             "No data has been uploaded. Review before saving or sharing."]
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
