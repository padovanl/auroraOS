#!/bin/bash
set -euo pipefail
export PYTHONPATH=/opt/aurora/lib/aurora
GTK_A11Y=none python3 /src/tests/window-style-preview.py > /out/window-style.log 2>&1
