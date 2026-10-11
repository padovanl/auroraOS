"""SSH helper and firewall application profiles on an isolated live system."""
import argparse
from pathlib import Path
from vm import VM

parser = argparse.ArgumentParser()
parser.add_argument('iso')
parser.add_argument('--out', default='work/sharing-test')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
vm = VM(args.iso, args.out)
try:
    vm.push(str(repo / 'desktop/libexec/aurora-admin'), '/usr/libexec/aurora-admin')
    vm.push(str(repo / 'overlay/etc/ufw/applications.d/aurora-ssh'),
            '/etc/ufw/applications.d/aurora-ssh')
    for service in ('ssh.service', 'sshd@.service'):
        path = f'etc/systemd/system/{service}.d/aurora-host-keys.conf'
        vm.push(str(repo / 'overlay' / path), '/' + path)
    assert vm.root('systemctl daemon-reload')[0] == 0
    # Simulate an independently configured rule; Aurora must preserve it.
    assert vm.root('ufw allow OpenSSH')[0] == 0
    code, output = vm.root('/usr/libexec/aurora-admin ssh on')
    assert code == 0, output
    assert vm.root('systemctl is-active --quiet ssh.service')[0] == 0
    code, output = vm.root('ufw status')
    assert code == 0 and 'Aurora SSH' in output and 'OpenSSH' in output, output
    code, output = vm.root("python3 -c 'import socket; s=socket.create_connection((\"127.0.0.1\",22),5); assert s.recv(128).startswith(b\"SSH-2.0\"); s.close()'")
    assert code == 0, output
    print('ok: enabling SSH opens its firewall profile and serves an SSH handshake', flush=True)
    code, output = vm.root('/usr/libexec/aurora-admin ssh off')
    assert code == 0, output
    assert vm.root('! systemctl is-active --quiet ssh.service ssh.socket')[0] == 0
    code, output = vm.root('ufw status')
    assert code == 0 and 'Aurora SSH' not in output and 'OpenSSH' in output, output
    vm.shot('ssh-disabled')
    print('ok: disabling SSH stops service/socket and preserves independent firewall rules', flush=True)
finally:
    vm.close()
