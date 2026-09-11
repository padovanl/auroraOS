"""Keep Awake: no screen blanking, locking or automatic suspend while it's on
(a presentation, a film, a long download). A toggle in the Control Center.

aurora-idle reads the flag file and drops its timeouts; a systemd-inhibit lock
also tells logind and other programs not to idle or sleep. It lasts until it's
turned off or the session ends (a new shell starts with it off).
"""

import os
import subprocess

from gi.repository import GLib, GObject


def flag_path():
    return os.path.join(GLib.get_user_runtime_dir(), "aurora-keep-awake")


def restart_idle():
    subprocess.run(["pkill", "-x", "swayidle"], check=False)
    subprocess.Popen(["aurora-idle"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class KeepAwake(GObject.Object):
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self):
        super().__init__()
        self._inhibitor = None
        try:
            os.remove(flag_path())  # left over from an earlier session or shell
        except OSError:
            pass

    @property
    def active(self):
        return self._inhibitor is not None

    def set_active(self, on):
        if on == self.active:
            return
        if on:
            try:
                self._inhibitor = subprocess.Popen(
                    ["systemd-inhibit", "--what=idle:sleep", "--who=Aurora",
                     "--why=Keep Awake is on", "--mode=block", "sleep", "infinity"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                return
            with open(flag_path(), "w"):
                pass
        else:
            self._inhibitor.terminate()
            self._inhibitor = None
            try:
                os.remove(flag_path())
            except OSError:
                pass
        restart_idle()
        self.emit("changed")
