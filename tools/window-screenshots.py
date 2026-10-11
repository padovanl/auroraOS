#!/usr/bin/env python3
"""Capture current window documentation in a disposable QEMU live session.

Usage: tools/window-screenshots.py ISO [--push] [--out docs/screenshots]
--push stages current sources in an older ISO; it is not release validation.
Uses the same QEMU driver as the interaction tests. Account and activity data
remain inside the disposable guest. Activity rows are demonstration data.
"""
import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/interact'))
from vm import VM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('iso')
    parser.add_argument('--push', action='store_true')
    parser.add_argument('--guides-only', action='store_true', help='Only background galleries and activity menu')
    parser.add_argument('--workflow-only', action='store_true', help='Only account controls and Files context menu')
    parser.add_argument('--out', default=str(ROOT / 'docs/screenshots'))
    args = parser.parse_args()
    vm = VM(args.iso, args.out)

    def command(text):
        code, output = vm.user(text)
        if code:
            raise RuntimeError(output or text)

    def capture(name):
        from PIL import Image
        vm.move(1750, 750)
        time.sleep(1)
        source = Path(vm.shot(name))
        source.replace(Path(args.out) / f'{name}.png')
        with Image.open(Path(args.out) / f'{name}.png') as image:
            # Guide images focus on the controls; the PNG preserves the full desktop.
            bounds = ((450, 195, 1470, 915) if name.startswith('settings-') else
                      (440, 215, 1480, 895) if name.startswith('files') else
                      (490, 215, 1430, 895) if name.startswith('task-manager') else
                      (1280, 0, 1920, 260))
            image.crop(bounds).save(Path(args.out) / f'{name}.webp', lossless=True, method=6)
        print(f'Saved {name}.png', flush=True)

    try:
        if args.push:
            print('Staged files:', len(vm.push_desktop(str(ROOT))), flush=True)
            vm.restart_shell()
        command('mkdir -p ~/Documents ~/Pictures ~/Downloads; '
                "printf 'Aurora screenshot demonstration\n' > ~/Documents/Welcome.txt")
        for mode in ('light', 'dark'):
            if args.guides_only or args.workflow_only:
                break
            command(f'gsettings set org.gnome.desktop.interface color-scheme prefer-{mode}')
            time.sleep(2)
            pages = ('desktop', 'appearance', 'keyboard', 'accessibility', 'power',
                     'health', 'ai', 'users') if mode == 'light' else ('users',)
            for page in pages:
                command(f'setsid -f aurora-settings --page {page} >/dev/null 2>&1')
                time.sleep(5 if page == 'health' else 2)
                capture(f'settings-{page}' if mode == 'light' else 'settings-users-dark')
            command("pkill -f '[a]urora-settings' || true")
            time.sleep(1)
            command('setsid -f aurora-files >/dev/null 2>&1')
            time.sleep(3)
            capture('files' if mode == 'light' else 'files-dark')
            command("pkill -f '[a]urora-files' || true")
            command('setsid -f aurora-taskmanager >/dev/null 2>&1')
            time.sleep(3)
            capture('task-manager' if mode == 'light' else 'task-manager-dark')
            command("pkill -f '[a]urora-taskmanager' || true")
        if not args.guides_only:
            command('gsettings set org.gnome.desktop.interface color-scheme prefer-light; '
                    'setsid -f aurora-settings --page users >/dev/null 2>&1')
            time.sleep(3)
            vm.scroll(1200, 750, 10)
            capture('settings-users-accounts')
            command("pkill -f '[a]urora-settings' || true")
            command('setsid -f aurora-files >/dev/null 2>&1')
            time.sleep(3)
            vm.click(1150, 480, button='right')
            capture('files-context-menu')
            command("pkill -f '[a]urora-files' || true")
        if args.workflow_only:
            return
        command('gsettings set org.gnome.desktop.interface color-scheme prefer-light; '
                'setsid -f aurora-settings --page appearance >/dev/null 2>&1')
        time.sleep(3)
        vm.click(890, 485)
        time.sleep(2)
        capture('settings-background-static')
        vm.click(1090, 485)
        time.sleep(2)
        capture('settings-background-animated')
        command("pkill -f '[a]urora-settings' || true")
        # Keep the transfer's owner alive while its demonstration row is shown.
        sample = Path(args.out) / 'activity-demo.py'
        sample.write_text("from aurora import activities\nimport time\n"
                          "job = activities.create('Copying project files', 'copy')\n"
                          "activities.update(job, progress=.42, item='Documents → USB drive')\n"
                          "done = activities.create('Downloading a wallpaper', 'download')\n"
                          "activities.update(done, status='finished')\n"
                          "time.sleep(60)\n")
        if vm.push(str(sample), '/tmp/aurora-shot-activities.py'):
            raise RuntimeError('Could not stage activity demonstration')
        command('setsid -f env PYTHONPATH=/usr/lib/aurora python3 '
                '/tmp/aurora-shot-activities.py >/dev/null 2>&1')
        time.sleep(3)
        vm.click(1619, 14)
        capture('activity-center')
        sample.unlink()
        print('WINDOW SCREENSHOTS COMPLETE', flush=True)
    finally:
        vm.close()


if __name__ == '__main__':
    main()
