"""Shell hardware services must never stop the shell on unusual hardware."""

import subprocess
from types import SimpleNamespace

from aurora.shell import services
from aurora.shell.app import Shell, _service


def battery_with(props):
    b = services.Battery.__new__(services.Battery)
    services.GObject.Object.__init__(b)
    b._device = SimpleNamespace(props=props)
    b._update()
    return b


def test_battery_reads_upower_kind():
    b = battery_with(SimpleNamespace(is_present=True, kind=2, percentage=73.0,
                                     icon_name="battery-good-symbolic", state=2,
                                     time_to_full=0, time_to_empty=3600))
    assert b.present and b.percentage == 73.0 and not b.charging and b.remaining == 3600


def test_battery_ignores_a_non_battery_display_device():
    # Hyper-V exposes a display device that is not a battery (kind 0).
    b = battery_with(SimpleNamespace(is_present=True, kind=0, percentage=0.0, icon_name="",
                                     state=0, time_to_full=0, time_to_empty=0))
    assert not b.present


def test_battery_survives_unreadable_properties():
    b = battery_with(SimpleNamespace(is_present=True))  # everything else missing
    assert not b.present


def test_a_failing_service_becomes_unavailable():
    class Broken(services.Audio):
        def __init__(self):
            raise RuntimeError("no audio stack on this machine")

    s = _service(Broken)
    assert s.available is False and s.volume == 0.0
    assert s.icon_name == "audio-volume-muted-symbolic"


def test_a_stubborn_recorder_is_killed_and_reaped():
    class Process:
        def __init__(self):
            self.waits = 0
            self.killed = False
            self.signals = []

        def poll(self):
            return None

        def send_signal(self, value):
            self.signals.append(value)

        def wait(self, timeout=None):
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("wf-recorder", timeout)
            return -9

        def kill(self):
            self.killed = True

    recorder = services.Recorder.__new__(services.Recorder)
    services.GObject.Object.__init__(recorder)
    recorder.proc, recorder.path = Process(), "/tmp/recording.mp4"
    process = recorder.proc
    recorder.stop()
    assert process.signals == [services.signal.SIGINT]
    assert process.killed and process.waits == 2
    assert recorder.proc is None


def test_capture_paths_do_not_replace_files_from_the_same_second(tmp_path, monkeypatch):
    class Date:
        def format(self, _pattern):
            return "2026-10-05_12-34-56"

    monkeypatch.setattr(services.GLib.DateTime, "new_now_local", lambda: Date())
    first = services.unique_capture_path(str(tmp_path), "Screenshot", ".png")
    assert first.endswith("Screenshot_2026-10-05_12-34-56.png")
    open(first, "w").close()
    second = services.unique_capture_path(str(tmp_path), "Screenshot", ".png")
    assert second.endswith("Screenshot_2026-10-05_12-34-56_2.png")


def test_opening_a_shell_surface_closes_the_others():
    class Surface:
        def __init__(self):
            self.visible = True
            self.closed = False

        def get_visible(self):
            return self.visible

        def hide_launcher(self):
            self.closed = True

        def hide_overview(self):
            self.closed = True

        def set_visible(self, value):
            self.visible = value
            self.closed = not value

        def close_menus(self):
            self.closed = True

    shell = SimpleNamespace()
    shell.launcher, shell.overview, shell.shortcuts_overlay = Surface(), Surface(), Surface()
    panel, keep = Surface(), Surface()
    shell.panels = SimpleNamespace(windows=lambda: [panel, keep])
    Shell.close_overlays(shell, keep)
    assert shell.launcher.closed and shell.overview.closed and shell.shortcuts_overlay.closed
    assert panel.closed and not keep.closed


def test_cancelling_pin_selection_does_not_start_another_selection():
    callbacks = []
    shell = SimpleNamespace(
        _finish_pin_screenshot=lambda path: None,
        _grab_area_async=lambda callback, folder=None: callbacks.append(callback),
    )
    Shell.pin_screenshot(shell)
    assert callbacks == [shell._finish_pin_screenshot]
    callbacks[0](None)  # cancellation is a no-op, not a new selection
    assert len(callbacks) == 1


def test_lock_closes_keyboard_overlays_before_starting_lock_screen():
    events = []
    shell = SimpleNamespace(
        close_overlays=lambda: events.append("close"),
        power=SimpleNamespace(lock=lambda: events.append("lock")),
    )
    Shell.lock(shell)
    assert events == ["close", "lock"]
