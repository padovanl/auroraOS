"""Real greetd/PAM and logind sessions in a disposable QEMU live system.

--push stages current desktop sources in an older ISO; it is not an ISO release test.
The test creates disposable accounts only inside the guest.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vm import VM, quote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('iso')
parser.add_argument('--out', default='work/users-session-vm')
parser.add_argument('--push', action='store_true')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
vm = VM(args.iso, args.out)


def check(command, timeout=60):
    code, output = vm.root(command, timeout=timeout)
    assert code == 0, output
    return output


def desktop_command(user, command):
    uid = check(f'id -u {user}').strip()
    return f'runuser -u {user} -- env XDG_RUNTIME_DIR=/run/user/{uid} ' + \
           f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus ' + \
           f'PYTHONPATH=/usr/lib/aurora bash -c {quote(command)}'


def greeter_ready():
    check('for i in $(seq 60); do pgrep -u _greetd -x labwc >/dev/null && exit 0; sleep 1; done; exit 1', 70)


def login(user, wrong=False):
    secret = 'wrong-fixture-password' if wrong else 'temporary-test-password'
    code = f'''
import subprocess
from pathlib import Path
from aurora.greeter.greetd import Greetd
pid = subprocess.check_output(['pgrep', '-u', '_greetd', '-x', 'labwc']).split()[0].decode()
environment = dict(entry.split(b'=', 1) for entry in Path('/proc/' + pid + '/environ').read_bytes().split(b'\\0') if b'=' in entry)
g = Greetd(environment[b'GREETD_SOCK'].decode())
try:
    reply = g.create_session({user!r})
    assert reply['type'] == 'auth_message', reply
    reply = g.respond({secret!r})
    while reply['type'] == 'auth_message':
        assert reply['auth_message_type'] not in ('secret', 'visible'), reply
        reply = g.respond(None)
    if {wrong!r}:
        assert reply['type'] == 'error', reply
        g.cancel()
        print('PASS: incorrect password rejected by real PAM')
    else:
        assert reply['type'] == 'success', reply
        assert g.start_session(['aurora-session', 'labwc'])['type'] == 'success'
finally:
    g.close()
'''
    output = check('runuser -u _greetd -- env PYTHONPATH=/usr/lib/aurora python3 - <<\'PY\'\n' + code + '\nPY', 45)
    if wrong:
        print(output, flush=True)
        return
    # This IPC client replaces the greeter's login action; end its compositor
    # exactly as Greeter._done does after a successful start_session reply.
    check('pkill -u _greetd -x labwc')
    uid = check(f'id -u {user}').strip()
    check(f'for i in $(seq 60); do test -e /run/user/{uid}/aurora-shell.ready && exit 0; sleep 1; done; exit 1', 70)
    check(desktop_command(user, 'gdbus call --session --dest org.freedesktop.DBus '
                          '--object-path /org/freedesktop/DBus --method '
                          'org.freedesktop.DBus.NameHasOwner org.aurora.Shell | grep -q true'))
    check(f'loginctl list-sessions --no-legend | grep -w {user}')
    log = check(f'cat /run/user/{uid}/aurora-shell.log')
    (Path(args.out) / f'{user}-shell.log').write_text(log)
    assert 'Traceback' not in log and 'Gtk-CRITICAL' not in log, log
    vm.shot('login-' + user)
    print('PASS: real graphical login for ' + user, flush=True)


try:
    if args.push:
        staged = vm.push_desktop(str(repo))
        assert vm.push(str(repo / 'desktop/libexec/aurora-admin'), '/usr/libexec/aurora-admin') == 0
        print('Staged current desktop sources in the old live image:', staged, flush=True)
    check("printf '%s\\n' 'temporary-test-password' | /usr/libexec/aurora-admin add-user audit-a 'Account A' no")
    check("printf '%s\\n' 'temporary-test-password' | /usr/libexec/aurora-admin add-user audit-b 'Account B' yes")
    check('id -nG audit-b | tr " " "\\n" | grep -qx sudo')
    check('/usr/libexec/aurora-admin autologin off')
    code, output = vm.user('aurora-shell logout')
    assert code == 0, output
    greeter_ready()
    login('audit-a', wrong=True)
    login('audit-a')
    code, _output = vm.root('/usr/libexec/aurora-admin delete-user audit-a')
    assert code != 0, 'an active account was deleted'
    check('getent passwd audit-a >/dev/null')
    print('PASS: removing the active account is refused', flush=True)
    check(desktop_command('audit-a', 'gsettings set org.aurora.desktop clock-show-seconds true'))
    # A second PAM session keeps the same user's bus/runtime alive across logout.
    check('systemd-run --unit=aurora-audit-other-session --uid=audit-a '
          '--property=PAMName=login /usr/bin/sleep 300')
    sessions = check("sleep 1; loginctl list-sessions --no-legend | awk '$3 == \"audit-a\" {print; if ($6 == \"user\") graphical++; if ($6 == \"background\") background++} END {exit !(graphical && background)}'")
    print('Concurrent logind sessions for audit-a:\n' + sessions, flush=True)
    check(desktop_command('audit-a', 'aurora-shell logout'))
    greeter_ready()
    check('systemctl is-active --quiet aurora-audit-other-session.service')
    login('audit-b')
    check(desktop_command('audit-b', 'gsettings get org.aurora.desktop clock-show-seconds | grep -qx false'))
    print('PASS: independent preferences and another account session survives logout', flush=True)
    check(desktop_command('audit-b', 'aurora-shell logout'))
    greeter_ready()
    login('audit-a')
    check(desktop_command('audit-a', 'gsettings get org.aurora.desktop clock-show-seconds | grep -qx true'))
    check('systemctl is-active --quiet aurora-audit-other-session.service')
    print('PASS: repeated same-account login with a surviving PAM session and user bus', flush=True)
    check(desktop_command('audit-a', 'aurora-shell logout'))
    greeter_ready()
    check('systemctl stop aurora-audit-other-session.service')
    print('USERS AND SESSIONS PASSED', flush=True)
finally:
    vm.close()
