#!/usr/bin/env python3
"""Write desktop/po/LANG.po from translations kept as JSON.

Usage: tools/po-from-json.py LANG [FILE.json…]   (default: desktop/po/sources/LANG.json)

Each JSON file maps an English message (as in the code) to its translation;
plural messages map to a list with one form per plural category of the
language. Messages missing from the JSON stay untranslated (English). A translation whose {placeholders}
differ from the English original is rejected (left untranslated) and
reported, so a typo can't crash a format() call at runtime.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POT = os.path.join(ROOT, "desktop", "po", "aurora.pot")

PLURALS = {
    "es": "nplurals=2; plural=(n != 1);",
    "de": "nplurals=2; plural=(n != 1);",
    "pt": "nplurals=2; plural=(n != 1);",
    "hi": "nplurals=2; plural=(n != 1);",
    "fr": "nplurals=2; plural=(n > 1);",
    "ru": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && "
          "(n%100<10 || n%100>=20) ? 1 : 2);",
    "zh_CN": "nplurals=1; plural=0;",
    "ja": "nplurals=1; plural=0;",
    "ar": "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : "
          "n%100>=11 ? 4 : 5);",
}
NAMES = {"es": "Spanish", "de": "German", "pt": "Portuguese", "hi": "Hindi", "fr": "French",
         "ru": "Russian", "zh_CN": "Chinese (Simplified)", "ja": "Japanese", "ar": "Arabic"}
FIELD = re.compile(r"\{[a-z_]+(?::[^}]*)?\}")


def unquote(chunk):
    raw = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', chunk))
    return raw


def pot_entries():
    """[(comments, msgid_raw, msgid_plural_raw or None)] in template order."""
    out = []
    for block in open(POT).read().split("\n\n"):
        m = re.search(r'(?:^|\n)msgid ((?:"[^\n]*"\n?)+)(?:msgid_plural ((?:"[^\n]*"\n?)+))?msgstr',
                      block, re.S)
        if not m:
            continue
        mid = unquote(m.group(1))
        if not mid:
            continue
        # Aurora formats with str.format(), never %: drop xgettext's python-format
        # guess, which would make msgfmt reject a translated "50%".
        comments = "\n".join(ln for ln in block.splitlines()
                              if ln.startswith("#") and "python-format" not in ln)
        out.append((comments, mid, unquote(m.group(2)) if m.group(2) else None))
    return out


def quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def fields(raw):
    return sorted(FIELD.findall(raw))


def main():
    lang, files = sys.argv[1], sys.argv[2:]
    if not files:
        files = [os.path.join(ROOT, "desktop", "po", "sources", f"{lang}.json")]
    tr = {}
    for f in files:
        with open(f) as fh:
            tr.update(json.load(fh))
    entries = pot_entries()
    nplurals = int(re.search(r"nplurals=(\d)", PLURALS[lang]).group(1))
    lines = [
        f"# {NAMES[lang]} translation of Aurora OS.",
        "# This file is distributed under the same license as Aurora OS (GPL-3.0-or-later).",
        'msgid ""', 'msgstr ""',
        '"Project-Id-Version: aurora\\n"',
        f'"Language: {lang}\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        f'"Plural-Forms: {PLURALS[lang]}\\n"', "",
    ]
    missing, bad = 0, []
    for i, (comments, mid, plural) in enumerate(entries):
        # The English text, unescaped: the key in the JSON, and for placeholders.
        english = mid.encode().decode("unicode_escape").encode("latin-1").decode("utf-8")
        value = tr.get(english)
        if comments:
            lines.append(comments)
        if plural is None:
            ok = isinstance(value, str) and value.strip() and fields(value) == fields(english)
            if value is not None and not ok:
                bad.append(i)
            missing += value is None
            lines += [f'msgid "{mid}"', f"msgstr {quote(value) if ok else chr(34) * 2}", ""]
        else:
            forms = value if isinstance(value, list) else None
            ok = (forms is not None and len(forms) == nplurals
                  and all(fields(f) == fields(english) or fields(f) == [] and nplurals > 1
                          for f in forms))
            if value is not None and not ok:
                bad.append(i)
            missing += value is None
            lines += [f'msgid "{mid}"', f'msgid_plural "{plural}"']
            for k in range(nplurals):
                lines.append(f"msgstr[{k}] {quote(forms[k]) if ok else chr(34) * 2}")
            lines.append("")
    out = os.path.join(ROOT, "desktop", "po", f"{lang}.po")
    with open(out, "w") as f:
        f.write("\n".join(lines))
    print(f"{lang}: {len(entries) - missing - len(bad)}/{len(entries)} translated"
          + (f", rejected {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
