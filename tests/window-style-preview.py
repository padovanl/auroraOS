"""Validate shared GTK CSS and capture Aurora windows in light/dark and narrow layouts."""
import subprocess
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib
from aurora import data_path
from aurora.settingsapp.app import SettingsApp, SettingsWindow
from aurora.files.app import FilesApp
from aurora.files.window import FilesWindow
from aurora.taskmanager import App as TaskApp, TaskManager


def settle(seconds=1):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)


Adw.init()
errors = []
for relative in ('gtk/gtk4-base.css', 'gtk/gtk4-palette-light.css',
                 'gtk/gtk4-palette-dark.css', 'style/settings.css'):
    provider = Gtk.CssProvider()
    provider.connect('parsing-error', lambda _p, _section, error:
                     errors.append(error.message) if error.domain == 'gtk-css-parser-error-quark' else None)
    provider.load_from_path(data_path(*relative.split('/')))
assert not errors, errors

apps = [SettingsApp(), FilesApp(), TaskApp()]
for app in apps:
    app.register(None)
manager = Adw.StyleManager.get_default()
for mode, scheme in [('light', Adw.ColorScheme.FORCE_LIGHT), ('dark', Adw.ColorScheme.FORCE_DARK)]:
    manager.set_color_scheme(scheme)
    windows = [('settings', SettingsWindow(apps[0])),
               ('files', FilesWindow(apps[1])), ('task-manager', TaskManager(apps[2]))]
    for name, window in windows:
        if name == 'settings':
            window.show_page('users')
        window.present()
        settle()
        subprocess.run(['grim', f'/out/{name}-{mode}.png'], check=True)
        assert not errors, errors
        if name == 'settings':
            window.set_default_size(480, 680)
            settle()
            assert window.split.get_collapsed()
            subprocess.run(['grim', f'/out/settings-narrow-{mode}.png'], check=True)
        window.close()
        settle(.1)
print('PASS: GTK CSS, three app windows in light/dark and narrow Settings layouts')
