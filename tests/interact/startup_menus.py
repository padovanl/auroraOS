"""Real desktop clicks: startup feedback, repeated launches and menu dismissal."""
import argparse
from pathlib import Path
import time

from vm import VM, quote
from newfeatures import difference

parser = argparse.ArgumentParser()
parser.add_argument("iso")
parser.add_argument("--out", default="work/startup-menu-test")
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
vm = VM(args.iso, args.out)
try:
    vm.push_desktop(str(repo))
    vm.restart_shell()
    vm.push(str(repo / "tests/helpers/startup-app.py"), "/tmp/aurora-startup-audit.py")
    desktop = "[Desktop Entry]\nType=Application\nName=Startup Audit\nIcon=system-run\nExec=python3 /tmp/aurora-startup-audit.py\nStartupWMClass=org.aurora.StartupAudit\n"
    vm.user("printf %s " + quote(desktop) + " > ~/Desktop/startup-audit.desktop")
    time.sleep(2)
    before = vm.shot("before-launch")
    vm.click(70, 210, double=True, pause=.2)
    feedback = vm.shot("launch-feedback")
    assert difference(before, feedback, (600, 850, 1320, 1000)) > .3, "startup OSD missing"
    time.sleep(.5)
    vm.click(70, 210, double=True, pause=.1)
    assert vm.wait_for(lambda: vm.window("org.aurora.StartupAudit"), timeout=15)
    assert vm.user("wc -l < /tmp/aurora-startup-audit-count")[1].strip() == "1"
    vm.shot("ready-once")
    print("ok: desktop launches immediately show feedback; repeated clicks launch once", flush=True)
    vm.root("pkill -f '[/]tmp/aurora-startup-audit.py'")
    assert vm.wait_for(lambda: not vm.window("org.aurora.StartupAudit"), timeout=10)
    vm.right_click(1200, 400)
    menu = vm.shot("desktop-menu")
    vm.keys("esc", pause=.3)
    closed = vm.shot("menu-escape")
    assert difference(menu, closed, (1100, 350, 1600, 950)) > .5
    vm.right_click(1200, 400)
    vm.click(800, 400, pause=.3)
    outside = vm.shot("menu-outside")
    assert difference(closed, outside, (1100, 350, 1600, 950)) < .5
    vm.user("gsettings set org.aurora.desktop window-animations false")
    vm.right_click(1200, 400)
    vm.keys("esc", pause=.2)
    vm.shot("reduced-motion-menu")
    code, log = vm.user("cat $XDG_RUNTIME_DIR/aurora-shell.log")
    assert code == 0 and "Traceback" not in log and "Gtk-CRITICAL" not in log, log[-2000:]
    print("ok: Escape, outside click and reduced motion leave no exceptions or GTK criticals", flush=True)
finally:
    vm.close()
