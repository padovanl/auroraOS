"""Fingerprint enrollment for Settings → Users (fprintd command-line tools).

A fingerprint unlocks sudo, pkexec and admin prompts. The login and lock
screens keep asking for the password: see overlay/usr/share/pam-configs.
"""

import re
import shutil

from gi.repository import Adw, Gio, GLib, Gtk

from aurora.i18n import _
from aurora.settingsapp.util import run

STAGE_MESSAGES = {
    "enroll-stage-passed": _("Good. Lift your finger and touch the reader again."),
    "enroll-retry-scan": _("Try again."),
    "enroll-swipe-too-short": _("Swipe was too short. Try again."),
    "enroll-finger-not-centered": _("Center your finger on the reader and try again."),
    "enroll-remove-and-retry": _("Lift your finger and try again."),
    "enroll-duplicate": _("This finger is already enrolled."),
}


def status(user):
    """('none' | 'no-device' | 'enrolled' | 'unavailable', list of fingers)."""
    if not shutil.which("fprintd-list"):
        return "unavailable", []
    out = run(["fprintd-list", user])
    if not out or "No devices" in out:
        return "no-device", []
    fingers = re.findall(r"#\d+:\s*(\S+)", out)
    return ("enrolled" if fingers else "none"), fingers


def finger_label(name):
    return name.replace("-", " ").replace(" finger", "").capitalize()


def add_rows(group, user, refresh):
    state, fingers = status(user)
    if state == "unavailable":
        return
    if state == "no-device":
        group.add(Adw.ActionRow(title=_("Fingerprint"),
                                subtitle=_("No fingerprint reader found")))
        return
    subtitle = (", ".join(finger_label(f) for f in fingers) if fingers
                else _("Use your finger instead of the password for sudo and admin prompts"))
    row = Adw.ActionRow(title=_("Fingerprint"), subtitle=subtitle)
    enroll = Gtk.Button(label=_("Add Finger…") if fingers else _("Set Up…"),
                        valign=Gtk.Align.CENTER)
    enroll.connect("clicked", lambda b: EnrollDialog(user, refresh).present(b.get_root()))
    row.add_suffix(enroll)
    if fingers:
        delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                            css_classes=["flat"], tooltip_text=_("Delete Fingerprints"))
        delete.connect("clicked", lambda *_: (run(["fprintd-delete", user]), refresh()))
        row.add_suffix(delete)
    group.add(row)


class EnrollDialog(Adw.Dialog):
    FINGERS = ["right-index-finger", "left-index-finger", "right-thumb", "left-thumb",
               "right-middle-finger", "left-middle-finger"]

    def __init__(self, user, on_done):
        super().__init__(title=_("Fingerprint"), content_width=380)
        self.user = user
        self.on_done = on_done
        self.proc = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin_top=24,
                      margin_bottom=24, margin_start=24, margin_end=24)
        self.icon = Gtk.Image(icon_name="auth-fingerprint-symbolic", pixel_size=96)
        box.append(self.icon)
        self.finger = Adw.ComboRow(title=_("Finger"), model=Gtk.StringList.new(
            [finger_label(f) for f in self.FINGERS]))
        lb = Gtk.ListBox(css_classes=["boxed-list"])
        lb.append(self.finger)
        box.append(lb)
        self.label = Gtk.Label(label=_("Choose a finger, then press Start and touch the reader "
                                       "several times."), wrap=True,
                               justify=Gtk.Justification.CENTER)
        box.append(self.label)
        self.progress = Gtk.LevelBar(min_value=0, max_value=1, value=0)
        box.append(self.progress)
        self.button = Gtk.Button(label=_("Start"), css_classes=["suggested-action", "pill"],
                                 halign=Gtk.Align.CENTER)
        self._start_handler = self.button.connect("clicked", lambda *_: self.start())
        box.append(self.button)
        view = Adw.ToolbarView(content=box)
        view.add_top_bar(Adw.HeaderBar())
        self.set_child(view)
        self.connect("closed", lambda *_: self._stop())
        self.stages = 0

    def start(self):
        finger = self.FINGERS[self.finger.get_selected()]
        self.finger.set_sensitive(False)
        self.button.set_sensitive(False)
        self.label.set_label(_("Touch the fingerprint reader."))
        self.proc = Gio.Subprocess.new(["fprintd-enroll", "-f", finger, self.user],
                                       Gio.SubprocessFlags.STDOUT_PIPE
                                       | Gio.SubprocessFlags.STDERR_MERGE)
        self.stream = Gio.DataInputStream.new(self.proc.get_stdout_pipe())
        self._read()

    def _read(self):
        self.stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line)

    def _on_line(self, stream, res):
        try:
            line, _len = stream.read_line_finish_utf8(res)
        except GLib.Error:
            line = None
        if line is None:
            self._finished()
            return
        m = re.search(r"Enroll result:\s*(\S+)", line)
        if m:
            result = m.group(1)
            if result == "enroll-completed":
                self.progress.set_value(1)
                self.label.set_label(_("Fingerprint saved."))
                self.icon.set_from_icon_name("emblem-ok-symbolic")
            elif result == "enroll-failed":
                self.label.set_label(_("Enrollment failed. Please try again."))
            else:
                if result == "enroll-stage-passed":
                    self.stages += 1
                    # Most readers need 5 to 10 touches; approach 90 % until done.
                    self.progress.set_value(min(0.9, self.stages / 8))
                self.label.set_label(STAGE_MESSAGES.get(result, result))
        self._read()

    def _finished(self):
        self.proc = None
        self.button.set_label(_("Done"))
        self.button.set_sensitive(True)
        self.button.disconnect(self._start_handler)
        self.button.connect("clicked", lambda *_: self.close())
        self.on_done()

    def _stop(self):
        if self.proc is not None:
            self.proc.force_exit()
            self.proc = None
