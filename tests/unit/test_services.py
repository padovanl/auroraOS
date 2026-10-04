"""Shell hardware services must never stop the shell on unusual hardware."""

import subprocess
from types import SimpleNamespace

from aurora.shell import services
from aurora.shell.app import _service


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
