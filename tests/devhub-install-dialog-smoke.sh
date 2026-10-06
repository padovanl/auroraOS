#!/bin/bash
set -euo pipefail
PYTHONPATH=/src/desktop python3 /src/tests/devhub-install-dialog.py
PYTHONPATH=/src/desktop python3 /src/tests/devhub-install-dialog.py --fail-after-install
