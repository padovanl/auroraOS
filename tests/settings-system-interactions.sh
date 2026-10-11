#!/bin/bash
# Run with AURORA_HEADLESS_OUTPUTS=2 desktop/dev/run-headless.sh.
set -euo pipefail
export PYTHONPATH=/src/desktop
test "$(stat -c %a /opt/aurora/lib/aurora/aurora/shell/app.py)" = 644
test -z "$(find /opt/aurora/lib/aurora \( -type f -o -type d \) -perm /022 -print -quit)"
python3 -m pytest -q -p no:cacheprovider /src/tests/unit > /out/unit.log 2>&1
python3 -X faulthandler /src/tests/menu-interactions.py > /out/menus.log 2>&1
python3 -X faulthandler /src/tests/settings-system-interactions.py > /out/settings-system.log 2>&1
python3 -X faulthandler /src/tests/daily-interactions.py > /out/daily-interactions.log 2>&1
python3 -X faulthandler /src/tests/file-interactions.py > /out/file-interactions.log 2>&1
python3 -X faulthandler /src/tests/assistant-interactions.py > /out/assistant-interactions.log 2>&1
