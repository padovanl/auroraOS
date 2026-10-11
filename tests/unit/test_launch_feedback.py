"""Launching shows feedback before GIO runs and repeated clicks stay bounded."""
from types import SimpleNamespace

import pytest
from aurora import apps
from aurora.shell import launchfeedback as feedback


class Surface:
    def __init__(self):
        self.cursor = "original"

    def get_cursor(self):
        return self.cursor

    def set_cursor_from_name(self, value):
        self.cursor = value

    def set_cursor(self, value):
        self.cursor = value


@pytest.fixture
def launch(monkeypatch):
    callbacks, calls, messages = [], [], []
    surface = Surface()
    group = SimpleNamespace(windows=lambda: [surface])
    shell = SimpleNamespace(wallpapers=group, panels=group, docks=group,
                            launcher=surface, toplevels=SimpleNamespace(toplevels=[]),
                            osd=SimpleNamespace(show_message=lambda *a, **k: messages.append(a)))
    monkeypatch.setattr(feedback.GLib, "timeout_add", lambda delay, cb:
                        callbacks.append((delay, cb)) or len(callbacks))
    monkeypatch.setattr(apps, "launch_direct", lambda app, **kw: calls.append(kw) or True)
    app = SimpleNamespace(get_id=lambda: "org.example.Editor.desktop",
                          get_commandline=lambda: "editor",
                          get_executable=lambda: "editor", get_display_name=lambda: "Editor",
                          get_startup_wm_class=lambda: "editor")
    return feedback.LaunchFeedback(shell), app, callbacks, calls, messages, surface


def test_feedback_is_immediate_and_repeated_clicks_launch_once(launch):
    control, app, callbacks, calls, messages, surface = launch
    assert control.launch(app) and control.launch(app)
    assert surface.cursor == "progress" and len(messages) == 1 and calls == []
    assert len(control.pending) == 1
    next(cb for delay, cb in callbacks if delay == 45)()
    assert len(calls) == 1
    control.shell.toplevels.toplevels.append(SimpleNamespace(
        app_id="org.example.Editor", activated=True))
    assert not control._poll()
    assert surface.cursor == "original" and not control.pending


def test_documents_and_explicit_new_windows_remain_independent(launch):
    control, app, callbacks, calls, messages, surface = launch
    control.launch(app, files=["/a"])
    control.launch(app, files=["/b"])
    control.launch(app, action="new-window")
    control.launch(app, action="new-window")
    for delay, callback in callbacks:
        if delay == 45:
            callback()
    assert len(calls) == len(control.pending) == 4


def test_failed_launch_and_timeout_restore_cursor(launch, monkeypatch):
    control, app, callbacks, calls, messages, surface = launch
    monkeypatch.setattr(apps, "launch_direct", lambda *a, **kw: False)
    control.launch(app)
    next(cb for delay, cb in callbacks if delay == 45)()
    assert not control.pending and surface.cursor == "original"
    assert messages[-1][0] == "dialog-error-symbolic"
    control.launch(app)
    monkeypatch.setattr(feedback.time, "monotonic", lambda: float("inf"))
    assert not control._poll()
    assert not control.pending and surface.cursor == "original"


def test_existing_inactive_window_does_not_end_feedback(launch):
    control, app, callbacks, calls, messages, surface = launch
    window = SimpleNamespace(app_id="editor", activated=False)
    control.shell.toplevels.toplevels.append(window)
    control.launch(app)
    next(cb for delay, cb in callbacks if delay == 45)()
    assert control._poll() and surface.cursor == "progress"
    window.activated = True
    assert not control._poll() and surface.cursor == "original"


def test_common_launch_path_uses_shell_handler(monkeypatch):
    calls = []
    monkeypatch.setattr(apps, "_launch_handler", lambda *a, **kw: calls.append(kw) or True)
    assert apps.launch(object(), files=["/document"], action="open")
    assert calls == [{"files": ["/document"], "action": "open"}]


def test_new_window_action_waits_for_a_new_window(launch):
    control, app, callbacks, calls, messages, surface = launch
    control.shell.toplevels.toplevels.append(SimpleNamespace(app_id="editor", activated=True))
    control.launch(app, action="new-window")
    next(cb for delay, cb in callbacks if delay == 45)()
    assert control._poll() and surface.cursor == "progress"
    control.shell.toplevels.toplevels.append(SimpleNamespace(app_id="editor", activated=False))
    assert not control._poll() and surface.cursor == "original"


def test_alias_desktop_entry_matches_the_same_launch_command(launch, monkeypatch):
    control, app, callbacks, calls, messages, surface = launch
    monkeypatch.setattr(apps, "find_app", lambda identifier: SimpleNamespace(
        get_id=lambda: "another-entry.desktop", get_commandline=lambda: "editor"))
    assert control._matches(app, SimpleNamespace(app_id="actual-window-id"))


def test_different_flatpak_commands_do_not_share_feedback(launch, monkeypatch):
    control, app, callbacks, calls, messages, surface = launch
    app.get_commandline = lambda: "flatpak run org.example.Editor"
    monkeypatch.setattr(apps, "find_app", lambda identifier: SimpleNamespace(
        get_id=lambda: "another-entry.desktop", get_commandline=lambda: "flatpak run org.example.Viewer"))
    assert not control._matches(app, SimpleNamespace(app_id="org.example.Viewer"))
