#!/bin/bash
# Run with desktop/dev/run-headless.sh tests/animated-wallpapers.sh OUTPUT_DIR.
set -euo pipefail
export PYTHONPATH=/opt/aurora/lib/aurora
python3 /src/tests/animated-wallpapers.py
