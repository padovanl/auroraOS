"""Exercise a real SFTP server in an isolated Aurora QEMU VM.

Use --push to apply current Files sources to an older ISO. --install-dependency
installs gvfs-fuse inside that test VM; omit it to check the rebuilt ISO itself.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vm import VM, quote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('iso')
parser.add_argument('--out', default='work/network-files-tests')
parser.add_argument('--push', action='store_true')
parser.add_argument('--install-dependency', action='store_true')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
vm=VM(args.iso,args.out)
try:
    for name in ('window.py', 'operations.py', 'clipboard.py', 'bookmarks.py') if args.push else ():
        vm.push(str(repo / 'desktop/aurora/files' / name),'/usr/lib/aurora/aurora/files/'+name)
    if args.push:
        vm.push(str(repo / 'desktop/aurora/dnd.py'), '/usr/lib/aurora/aurora/dnd.py')
    vm.push(str(repo / 'tests/network-files.py'),'/tmp/network-files.py')
    code, data=vm.root("dpkg-query -W -f='${db:Status-Abbrev}' gvfs-fuse 2>/dev/null")
    print('baseline gvfs-fuse:',code,repr(data),flush=True)
    if args.install_dependency:
        code,data=vm.root('apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gvfs-fuse',timeout=240)
        print(data,flush=True)
        assert code==0, 'installing standard GVFS FUSE dependency failed'
    else:
        assert code == 0 and data.strip() == 'ii', 'ISO is missing gvfs-fuse'
    code,data=vm.root('''mkdir -p /run/sshd
cat > /tmp/network-sshd.conf <<'EOF'
Port 2223
ListenAddress 127.0.0.1
HostKey /etc/ssh/ssh_host_ed25519_key
PidFile /tmp/network-sshd.pid
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
UsePAM yes
AuthorizedKeysFile .ssh/network_authorized_keys
Subsystem sftp internal-sftp
EOF
ssh-keygen -A
/usr/sbin/sshd -f /tmp/network-sshd.conf -E /tmp/network-sshd.log
''')
    assert code==0,data
    code,data=vm.user('''mkdir -p ~/.ssh ~/NetworkFixture/remote
chmod 700 ~/.ssh
ssh-keygen -q -t ed25519 -N '' -f ~/.ssh/id_ed25519
cp ~/.ssh/id_ed25519.pub ~/.ssh/network_authorized_keys
chmod 600 ~/.ssh/network_authorized_keys
ssh-keyscan -p 2223 -t ed25519 127.0.0.1 > ~/.ssh/known_hosts
ssh -p 2223 -o BatchMode=yes aurora@127.0.0.1 true
pkill -x gvfsd || true
gio mount sftp://aurora@127.0.0.1:2223/home/aurora/NetworkFixture/remote
''',timeout=45)
    print('mount:',code,data,flush=True)
    assert code==0,data
    code,data=vm.user('G_DEBUG=fatal-criticals PYTHONPATH=/usr/lib/aurora python3 -X faulthandler /tmp/network-files.py sftp://aurora@127.0.0.1:2223/home/aurora/NetworkFixture/remote /home/aurora/NetworkFixture',timeout=90)
    print(data,flush=True)
    assert code==0,data
    vm.shot('sftp-files-tested')
finally:
    vm.close()
