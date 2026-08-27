#!/bin/bash
# Run inside desktop/dev/run-headless.sh.
set -euo pipefail
export PYTHONPATH=/src/desktop
python3 /src/tests/file-interactions.py > /out/file-interactions.log 2>&1
