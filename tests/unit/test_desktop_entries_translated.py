"""Every app Aurora ships is named in each language (Launchpad, dock, menus)."""

import configparser
import glob
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PO = os.path.join(ROOT, "desktop", "po")
LANGS = open(os.path.join(PO, "LINGUAS")).read().split()


@pytest.mark.skipif(shutil.which("msgfmt") is None, reason="needs gettext's msgfmt")
@pytest.mark.parametrize("path", sorted(glob.glob(os.path.join(ROOT, "desktop", "data",
                                                               "applications", "*.desktop"))))
def test_desktop_entry_is_translated(path, tmp_path):
    out = tmp_path / os.path.basename(path)
    subprocess.run(["msgfmt", "--desktop", f"--template={path}", "-d", PO, "-o", str(out)],
                   check=True)
    entry = configparser.RawConfigParser(strict=False)
    entry.optionxform = str
    entry.read(out, encoding="utf-8")
    main = entry["Desktop Entry"]
    if main.get("NoDisplay") == "true" and "QuickLook" not in path:
        return
    for lang in LANGS:
        assert f"Name[{lang}]" in main, f"{os.path.basename(path)}: no Name[{lang}]"
        if "Comment" in main:
            assert f"Comment[{lang}]" in main, f"{os.path.basename(path)}: no Comment[{lang}]"
