#!/bin/bash
# Static checks on the sources. Runs in the dev container (make test-static).
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
step() { printf '\n\033[1;35m== %s\033[0m\n' "$*"; }
check() { if "$@"; then echo "ok"; else echo "FAILED: $*"; fail=1; fi; }

step "Python syntax"
py_bins=$(grep -l '^#!/usr/bin/python3' desktop/bin/* 2>/dev/null)
check python3 -m py_compile $(find desktop/aurora branding tests overlay -name '*.py') $py_bins

step "Shell syntax"
sh_files=$(grep -lE '^#!/bin/(ba)?sh' build/*.sh build/stages/*.sh desktop/bin/* desktop/libexec/* \
    desktop/dev/*.sh tests/*.sh tests/image/*.sh overlay/usr/libexec/* 2>/dev/null)
for f in $sh_files; do
    bash -n "$f" || { echo "FAILED: $f"; fail=1; }
done
if command -v shellcheck >/dev/null; then
    step "shellcheck (errors only)"
    check shellcheck -S error $sh_files
fi

step "Desktop entries"
check desktop-file-validate desktop/data/applications/*.desktop
# Session files use DesktopNames (session spec), which the validator flags.
check grep -q "^Exec=aurora-session$" desktop/data/wayland-sessions/aurora.desktop

step "GSettings schemas"
tmp=$(mktemp -d)
cp desktop/data/schemas/* "$tmp/"
check glib-compile-schemas --strict --targetdir="$tmp" "$tmp"
rm -rf "$tmp"

step "XML (labwc, greeter, polkit)"
check xmllint --noout desktop/data/labwc/*.xml desktop/data/greeter/*.xml \
    overlay/usr/share/polkit-1/actions/*.policy

step "Installer configuration (YAML)"
check python3 - <<'EOF'
import glob, sys, yaml
files = glob.glob("overlay/etc/calamares/**/*.conf", recursive=True) + \
        glob.glob("overlay/usr/lib/calamares/modules/*/module.desc") + \
        ["branding/calamares/branding.desc"]
for f in files:
    yaml.safe_load(open(f))
settings = yaml.safe_load(open("overlay/etc/calamares/settings.conf"))
execs = [m for step in settings["sequence"] for k, v in step.items() if k == "exec" for m in v]
for custom in ("aurora-finalize", "aurora-sources"):
    assert custom in execs, f"{custom} not in exec sequence"
print(f"{len(files)} files parsed")
EOF

step "Translations"
for po in desktop/po/*.po; do
    [ -e "$po" ] || continue
    msgfmt --check -o /dev/null "$po" || { echo "FAILED: $po"; fail=1; }
done
echo "ok"

step "Theme generator"
tmp=$(mktemp -d)
check python3 desktop/data/themes/generate.py "$tmp"
test -f "$tmp/Aurora/openbox-3/close-active.svg" || { echo "FAILED: traffic buttons"; fail=1; }
rm -rf "$tmp"

step "App manifest is consistent"
check python3 - <<'PY'
import re
rows = [l.split("|") for l in open("config/apps.manifest") if l.strip() and not l.startswith("#")]
ids = [r[2].strip() for r in rows]
assert all(len(r) == 4 and r[3].strip() in ("yes", "no") for r in rows), "bad manifest row"
assert len(ids) == len(set(ids)), "duplicate ids in manifest"
hidden = {l.strip() for l in open("config/hidden-apps.list") if l.strip() and not l.startswith("#")}
assert not hidden & set(ids), f"manifest apps are hidden: {hidden & set(ids)}"
print(f"{len(ids)} default apps")
PY

step "Package lists have no duplicates"
dups=$(sed -e 's/#.*//' -e '/^\s*$/d' config/packages/*.list | sort | uniq -d)
if [ -n "$dups" ]; then echo "FAILED: duplicated packages: $dups"; fail=1; else echo "ok"; fi

exit $fail
