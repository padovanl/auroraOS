"""Drive actual pointer drags and modifier keys in Aurora's QEMU desktop."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vm import VM, quote

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('iso')
parser.add_argument('--out', default='work/files-drag-tests')
parser.add_argument('--push', action='store_true')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
root = '/home/aurora/DragFixture'
vm = VM(args.iso, args.out)


def exists(path):
    return vm.user(f'test -e {quote(path)}')[0] == 0


def modifier(key, down):
    vm._events([{'type':'key', 'data':{'down':down, 'key':{'type':'qcode','data':key}}}])


def drag(start, end, key=None):
    vm.click(*start, pause=.5)
    vm.move(*start)
    time.sleep(.2)
    if key:
        modifier(key, True)
    vm.button('left', True)
    try:
        for step in range(1, 13):
            vm.move(start[0] + (end[0]-start[0])*step/12,
                    start[1] + (end[1]-start[1])*step/12)
            time.sleep(.06)
        time.sleep(.3)
    finally:
        vm.button('left', False)
        if key:
            modifier(key, False)
    time.sleep(.8)


try:
    if args.push:
        for name in ('window.py','operations.py','clipboard.py','bookmarks.py'):
            vm.push(str(repo / 'desktop/aurora/files' / name), '/usr/lib/aurora/aurora/files/'+name)
        vm.push(str(repo / 'desktop/aurora/dnd.py'), '/usr/lib/aurora/aurora/dnd.py')
    code, text = vm.user(f'mkdir -p {root}/Target; printf copy > {root}/copy.txt; '
                         f'printf move > {root}/move.txt; '
                         f'setsid -f aurora-files {root} >/tmp/drag-files.log 2>&1')
    assert code == 0, text
    assert vm.wait_for(lambda: (vm.window('org.aurora.Files') or {}).get('title') == 'DragFixture')
    time.sleep(2)
    vm.shot('before-drags')
    drag((890,370), (765,370), 'ctrl')
    vm.shot('after-ctrl-copy')
    assert vm.wait_for(lambda: exists(root+'/Target/copy.txt')), 'Ctrl-drag did not copy'
    assert exists(root+'/copy.txt'), 'Ctrl-drag removed its source'
    print('ok: real Ctrl-drag copies into a folder and preserves its source',flush=True)
    drag((1015,370), (765,370), 'shift')
    vm.shot('after-shift-move')
    assert vm.wait_for(lambda: exists(root+'/Target/move.txt')), 'Shift-drag did not move'
    assert not exists(root+'/move.txt'), 'Shift-drag left its source behind'
    print('ok: real Shift-drag moves into a folder',flush=True)
    vm.keys('ctrl','z',pause=.8)
    assert vm.wait_for(lambda: exists(root+'/move.txt') and not exists(root+'/Target/move.txt'))
    print('ok: Undo restores the file after a real drag move',flush=True)
    drag((1015,370), (765,370))
    assert vm.wait_for(lambda: exists(root+'/Target/move.txt') and not exists(root+'/move.txt'))
    print('ok: default folder drag moves when the source supports it',flush=True)
    vm.user(f'printf rubber > {root}/rubber.txt')
    time.sleep(1)
    vm.move(1250,500)
    time.sleep(.3)
    vm.button('left', True)
    try:
        for step in range(1,13):
            vm.move(1250-(1250-836)*step/12,500-(500-342)*step/12)
            time.sleep(.06)
    finally:
        vm.button('left',False)
    vm.shot('empty-space-selection')
    vm.keys('ctrl','c',pause=.3)
    vm.keys('ctrl','l',pause=.3)
    vm.type(root+'/Target')
    vm.keys('ret',pause=.5)
    vm.keys('ctrl','v',pause=.8)
    assert vm.wait_for(lambda: exists(root+'/Target/rubber.txt') and exists(root+'/Target/copy (2).txt'))
    assert exists(root+'/rubber.txt') and exists(root+'/copy.txt')
    print('ok: dragging empty space still selects multiple files for copying',flush=True)
    vm.keys('alt','up',pause=.5)
    vm.keys('ctrl','1',pause=.7)
    vm.shot('list-before-drag')
    drag((815,398), (815,363), 'ctrl')
    vm.shot('list-after-drag')
    assert vm.wait_for(lambda: exists(root+'/Target/copy (3).txt'))
    assert exists(root+'/copy.txt')
    print('ok: real Ctrl-drag also copies from list view',flush=True)
    print('ALL POINTER DRAG CHECKS PASSED',flush=True)
except Exception:
    print(vm.user('cat /tmp/drag-files.log; find /home/aurora/DragFixture -maxdepth 2 -type f')[1],flush=True)
    raise
finally:
    vm.close()
