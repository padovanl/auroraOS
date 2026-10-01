#!/usr/bin/env python3
"""Build gtklock.mo catalogs with Aurora's wording for the lock screen's
messages: gtklock-catalogs.py po/gtklock.json build/locale"""

import json
import os
import subprocess
import sys

MESSAGES = ("Login failed", "Caps Lock is on")
PAD = "\u00a0" * 3


def quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    source, out = sys.argv[1], sys.argv[2]
    with open(source, encoding="utf-8") as f:
        data = json.load(f)
    for lang, texts in data.items():
        if lang.startswith("_"):
            continue
        po = 'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n'
        for msgid, msgstr in zip(MESSAGES, texts):
            # Room inside the pill the lock screen draws around it (lock.css).
            msgstr = PAD + msgstr + PAD
            po += f"\nmsgid {quote(msgid)}\nmsgstr {quote(msgstr)}\n"
        target = os.path.join(out, lang, "LC_MESSAGES")
        os.makedirs(target, exist_ok=True)
        subprocess.run(["msgfmt", "-o", os.path.join(target, "gtklock.mo"), "-"],
                       input=po.encode(), check=True)


if __name__ == "__main__":
    main()
