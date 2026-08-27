#!/bin/bash
# Runs as a headless session scenario; a second compositor starts after logout.
set -eu
aurora-shell logout || true
for i in $(seq 100); do
    test -e "$XDG_RUNTIME_DIR/aurora-logging-out" && exit 0
    sleep .1
done
echo LOGOUT_FAILED > /out/logout-result
exit 1
