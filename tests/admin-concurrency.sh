#!/bin/bash
# Run only inside a disposable container: this fixture writes logind's config.
set -euo pipefail
if [ "${AURORA_ADMIN_TEST_CONTAINER:-}" != 1 ]; then
    echo 'Run in a disposable container with AURORA_ADMIN_TEST_CONTAINER=1.' >&2
    exit 2
fi
fixture_bin=$(mktemp -d)
trap 'rm -rf "$fixture_bin"' EXIT
printf '#!/bin/sh\nexit 0\n' > "$fixture_bin/systemctl"
chmod 755 "$fixture_bin/systemctl"
export PATH="$fixture_bin:$PATH"
conf=/etc/systemd/logind.conf.d/50-aurora.conf
for _iteration in $(seq 80); do
    rm -f "$conf"
    bash /src/desktop/libexec/aurora-admin power-key suspend &
    power_pid=$!
    bash /src/desktop/libexec/aurora-admin lid ignore &
    lid_pid=$!
    wait "$power_pid"
    wait "$lid_pid"
    grep -qx 'HandlePowerKey=suspend' "$conf"
    grep -qx 'HandleLidSwitch=ignore' "$conf"
done
echo 'PASS: 80 concurrent power-button/lid changes preserved both settings'
