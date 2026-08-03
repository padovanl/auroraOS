"""aurora-ai: Aurora AI from the terminal.

    ask "find files bigger than 1 GB"      suggest a command; run it only if you say so
    why                                     explain why the last command failed
    some-command 2>&1 | why                 …using its output
    aurora-ai chat "question"               a plain answer
    aurora-ai index                         update the index for search by meaning
    aurora-ai status                        what is installed and running
    aurora-ai stop                          stop the local model now

`ask` and `why` are shell functions (/etc/aurora/bashrc) around
`aurora-ai ask` and `aurora-ai why`.
"""

import os
import subprocess
import sys

from aurora import settings
from aurora.i18n import _
from aurora.ai import components, enabled, feature, provider
from aurora.ai.providers import SYSTEM_PROMPT, ProviderError, chat, first_code_block

ASK_SYSTEM = (
    "You turn requests into ONE bash command for Debian 13 (Aurora OS). Reply with the "
    "command in a single ```bash code block, then one short sentence explaining it. Prefer "
    "safe, standard tools. If the request is destructive, add a warning in the sentence.")

WHY_SYSTEM = (
    "You explain why a shell command failed on Debian 13 (Aurora OS), in the user's "
    "language, in at most 5 short lines, and suggest the fix as a command in a ```bash "
    "code block when there is one.")

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


def _check():
    if not enabled():
        sys.exit(_("Aurora AI is off. Turn it on in Settings → AI."))
    if not feature("terminal"):
        sys.exit(_("The terminal assistant is off (Settings → AI)."))


def _stream(messages, system):
    out = []
    try:
        for piece in chat(messages, system=system, max_tokens=600):
            out.append(piece)
            sys.stdout.write(piece)
            sys.stdout.flush()
    except ProviderError as e:
        sys.exit(f"\nAurora AI: {e}")
    print()
    return "".join(out)


def ask(request):
    _check()
    print(f"{DIM}Aurora AI · {provider()}{RESET}")
    reply = _stream([{"role": "user", "content": request}], ASK_SYSTEM)
    command = first_code_block(reply)
    if not command or not sys.stdin.isatty():
        return 0
    try:
        answer = input(f"{BOLD}" + _("Run it?") + f"{RESET} " + _("[y/N/e = edit]") + " ").strip().lower()
    except EOFError:
        return 0
    if answer == "e":
        try:
            import readline
            readline.set_startup_hook(lambda: readline.insert_text(command))
            command = input("$ ")
        finally:
            readline.set_startup_hook()
        answer = "y"
    if answer == "y":
        # Printed for the shell function, which adds it to the history.
        with open(os.environ.get("AURORA_AI_HISTORY", os.devnull), "w") as f:
            f.write(command + "\n")
        return subprocess.call(["bash", "-c", command])
    return 0


def why(command, status, output):
    _check()
    parts = [f"Command: {command or '(unknown)'}", f"Exit status: {status}"]
    if output.strip():
        parts.append("Output (last lines):\n" + "\n".join(output.strip().splitlines()[-40:]))
    else:
        parts.append("No output was captured.")
    _stream([{"role": "user", "content": "\n".join(parts)}], WHY_SYSTEM)
    return 0


def status():
    from aurora.ai import catalog, server
    s = settings.get()
    print(f"Aurora AI: {'on' if enabled() else 'off'} · provider: {provider()}")
    print(f"runtime:   {'installed' if components.runtime_installed() else 'not installed'}")
    for mid, m in catalog()["chat"].items():
        mark = "*" if s and s.get_string("ai-model") == mid else " "
        print(f" {mark} {mid:12} {m['name']:14} "
              f"{'installed' if components.model_installed('chat', mid) else '-'}")
    print(f"embeddings: {'installed' if components.model_installed('embed') else '-'}")
    print(f"speech:    {'installed' if components.speech_installed() else '-'}")
    for kind in server.PORTS:
        print(f"server {kind}: {'running' if server.running(kind) else 'stopped'}")
    print(f"disk used: {components.disk_usage() / 1e9:.2f} GB")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv.pop(0) if argv else "status"
    if cmd == "ask":
        return ask(" ".join(argv))
    if cmd == "why":
        command = os.environ.get("AURORA_LAST_COMMAND", "")
        stat = os.environ.get("AURORA_LAST_STATUS", "?")
        output = "" if sys.stdin.isatty() else sys.stdin.read()
        return why(command, stat, output)
    if cmd == "chat":
        if not enabled():
            sys.exit("Aurora AI is off. Turn it on in Settings → AI.")
        _stream([{"role": "user", "content": " ".join(argv)}], SYSTEM_PROMPT)
        return 0
    if cmd == "status":
        return status()
    if cmd == "index":
        if not feature("semantic-search"):
            sys.exit(_("Search by meaning is off (Settings → AI)."))
        from aurora.ai.index import run_indexer
        run_indexer()
        return 0
    if cmd == "stop":
        from aurora.ai import server
        for kind in server.PORTS:
            server.stop(kind)
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2
