#!/bin/bash
# Native desktop scenario: disposable real Unix accounts, separate buses/Wayland.
set -euo pipefail
if [ "${AURORA_MULTIUSER_TEST_CONTAINER:-}" != 1 ] || [ ! -e /.dockerenv ]; then
    echo 'Run only through the headless development container.' >&2
    exit 2
fi
export PYTHONPATH=/src/desktop
admin=/src/desktop/libexec/aurora-admin
getent group sudo >/dev/null || groupadd sudo
printf '%s\n' 'temporary-test-password' | bash "$admin" add-user audit-a 'Account A' no
printf '%s\n' 'temporary-test-password' | bash "$admin" add-user audit-b 'Account B' yes
id -nG audit-b | tr ' ' '\n' | grep -qx sudo
if id -nG audit-a | tr ' ' '\n' | grep -qx sudo; then exit 1; fi
bash "$admin" set-admin audit-a yes
id -nG audit-a | tr ' ' '\n' | grep -qx sudo
bash "$admin" set-admin audit-a no
if id -nG audit-a | tr ' ' '\n' | grep -qx sudo; then exit 1; fi
echo 'PASS: real account creation, standard/admin roles and role changes'
# The root headless compositor creates this without an Xorg display manager.
# Real multi-user X11 needs the usual shared sticky directory.
install -d -m 1777 /tmp/.X11-unix

for user in audit-a audit-b; do
    runtime="/tmp/aurora-multi-$user"
    install -d -m 700 -o "$user" -g "$user" "$runtime"
    runuser -u "$user" -- env XDG_RUNTIME_DIR="$runtime" \
        WAYLAND_DISPLAY= DISPLAY= DBUS_SESSION_BUS_ADDRESS= \
        PYTHONPATH=/src/desktop GTK_A11Y=none \
        dbus-run-session -- labwc -C /tmp/labwc \
        -s 'bash /src/tests/multiuser-session-inner.sh' > "/out/$user-compositor.log" 2>&1 &
    if test "$user" = audit-a; then session_a=$!; else session_b=$!; fi
done
cleanup() {
    for user in audit-a audit-b; do
        for name in shell files; do
            test ! -f "/tmp/aurora-multi-$user/$name.log" ||
                cp "/tmp/aurora-multi-$user/$name.log" "/out/$user-$name.log"
        done
    done
    kill "$session_a" "$session_b" 2>/dev/null || true
}
trap cleanup EXIT
for _ in $(seq 200); do
    if test -e /tmp/aurora-multi-audit-a/session-ready && \
       test -e /tmp/aurora-multi-audit-b/session-ready; then break; fi
    sleep .1
done
for user in audit-a audit-b; do
    runtime="/tmp/aurora-multi-$user"
    test -e "$runtime/session-ready"
    grep -q "/home/$user/private-background.png" "$runtime/preference"
    test "$(find "$runtime/aurora-activities" -name '*.json' | wc -l)" = 1
done
if runuser -u audit-b -- cat /tmp/aurora-multi-audit-a/job.id >/dev/null 2>&1; then
    echo 'FAIL: private runtime crossed user boundary'; exit 1
fi
touch /tmp/aurora-multi-audit-a/logout-now
wait "$session_a"
kill -0 "$session_b"
test -e /tmp/aurora-multi-audit-a/aurora-logging-out
test ! -e /tmp/aurora-multi-audit-b/aurora-logging-out
runuser -u audit-b -- env XDG_RUNTIME_DIR=/tmp/aurora-multi-audit-b \
    PYTHONPATH=/src/desktop python3 -c \
    'from aurora import activities; assert activities.list_recent()[0]["status"] == "running"'
echo 'PASS: concurrent desktops, separate preferences/journals, logout isolation'
touch /tmp/aurora-multi-audit-b/logout-now
wait "$session_b"
trap - EXIT
for user in audit-a audit-b; do
    cp "/tmp/aurora-multi-$user/shell.log" "/out/$user-shell.log"
    cp "/tmp/aurora-multi-$user/files.log" "/out/$user-files.log"
    # Closing the compositor does not end a PAM session in this test container.
    pkill -u "$user" || true
done
sleep .3
bash "$admin" delete-user audit-a
bash "$admin" delete-user audit-b
if getent passwd audit-a || getent passwd audit-b; then exit 1; fi
echo 'PASS: account removal in isolated container'
