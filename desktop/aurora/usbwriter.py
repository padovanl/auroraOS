"""USB Stick Writer: put a disk image on a stick, the way Rufus or Etcher do.

Pick the image, pick the stick, confirm once, watch the bar. Compressed images
(.gz, .xz, .bz2, .zst, and a .zip holding a single image) are decompressed as
they are written, so there is no need to unpack a 5 GB download first. When the
write is done the stick is read back and compared, byte for byte, with what was
sent — a stick that quietly drops writes is the usual reason an installer boots
to a corrupt file.

Only removable and USB disks are offered, the disk this system runs from is
never among them, and the actual writing is done by
/usr/libexec/aurora-usb-write through pkexec, which checks all of that again on
its own side: a program asking for a disk to be overwritten cannot be trusted to
have asked the right questions.
"""

import hashlib
import os
import re
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from aurora.i18n import _  # noqa: E402

HELPER = "/usr/libexec/aurora-usb-write"
BLOCK = 4 * 1024 * 1024
# Mount points that mean a disk is this running system, not a spare stick.
SYSTEM_PATHS = ("/", "/boot", "/boot/efi", "/efi", "/usr", "/var", "/home",
                "/run/live/medium", "/run/live/rootfs", "/lib/live/mount/medium")


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# --- the sticks -----------------------------------------------------------

def _read(path):
    try:
        with open(path, encoding="utf-8") as stream:
            return stream.read().strip()
    except OSError:
        return ""


def system_disks(mountinfo=None):
    """The disks this system is running from: never offered as a target."""
    busy = set()
    if mountinfo is None:
        try:
            with open("/proc/self/mountinfo", encoding="utf-8") as stream:
                mountinfo = stream.read()
        except OSError:
            return busy
    for line in mountinfo.splitlines():
        fields = line.split()
        if " - " not in line or len(fields) < 10:
            continue
        point = fields[4].replace("\\040", " ")
        source = line.split(" - ", 1)[1].split()[1]
        if point in SYSTEM_PATHS and source.startswith("/dev/"):
            name = os.path.basename(os.path.realpath(source))
            # sda1 -> sda, nvme0n1p2 -> nvme0n1, mmcblk0p1 -> mmcblk0
            busy.add(re.sub(r"(p?\d+)$", "", name) if not os.path.isdir(
                f"/sys/block/{name}") else name)
    return busy


class Stick:
    def __init__(self, name):
        self.name = name
        self.path = f"/dev/{name}"
        self.size = int(_read(f"/sys/block/{name}/size") or 0) * 512
        vendor = _read(f"/sys/block/{name}/device/vendor")
        model = _read(f"/sys/block/{name}/device/model")
        self.label = " ".join(part for part in (vendor, model) if part) or self.name

    @property
    def title(self):
        return f"{self.label} — {human(self.size)}"

    def mount_points(self):
        points = []
        try:
            with open("/proc/self/mountinfo", encoding="utf-8") as stream:
                for line in stream:
                    fields = line.split()
                    if " - " not in line or len(fields) < 10:
                        continue
                    source = line.split(" - ", 1)[1].split()[1]
                    if source.startswith(self.path):
                        points.append(fields[4].replace("\\040", " "))
        except OSError:
            pass
        return points


def removable_disks():
    """Removable or USB whole disks, smallest first, system disks left out."""
    busy = system_disks()
    out = []
    try:
        names = sorted(os.listdir("/sys/block"))
    except OSError:
        return out
    for name in names:
        if name in busy or name.startswith(("loop", "ram", "zram", "dm-", "sr", "md")):
            continue
        usb = False
        try:
            usb = "/usb" in os.readlink(f"/sys/block/{name}") or \
                "/mmc_host/" in os.readlink(f"/sys/block/{name}")
        except OSError:
            pass
        if _read(f"/sys/block/{name}/removable") != "1" and not usb:
            continue
        stick = Stick(name)
        if stick.size <= 0:
            continue                      # a card reader with no card in it
        out.append(stick)
    out.sort(key=lambda s: s.size)
    return out


# --- the image ------------------------------------------------------------

def opener(path):
    """A function returning a fresh byte stream over the image, and the number
    of bytes it will yield (None when a compressed image doesn't say)."""
    lower = path.lower()
    if lower.endswith(".gz"):
        import gzip
        return (lambda: gzip.open(path, "rb")), _gzip_size(path)
    if lower.endswith(".xz"):
        import lzma
        return (lambda: lzma.open(path, "rb")), None
    if lower.endswith(".bz2"):
        import bz2
        return (lambda: bz2.open(path, "rb")), None
    if lower.endswith(".zst"):
        # Debian has no zstd module in the standard library; the command is there.
        return (lambda: _piped(["zstd", "-dc", path])), None
    if lower.endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(path) as archive:
            members = [i for i in archive.infolist() if not i.is_dir()]
        if len(members) != 1:
            raise ValueError(_("The zip file holds more than one file"))
        member = members[0]
        return (lambda: zipfile.ZipFile(path).open(member.filename)), member.file_size
    return (lambda: open(path, "rb", buffering=0)), os.path.getsize(path)


def _piped(argv):
    """The output of a decompressor, as a readable stream."""
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE)
    return proc.stdout


def _gzip_size(path):
    """gzip stores the uncompressed size in the last four bytes — right for
    anything under 4 GB, which is most images that come gzipped."""
    try:
        with open(path, "rb") as stream:
            stream.seek(-4, os.SEEK_END)
            return int.from_bytes(stream.read(4), "little")
    except OSError:
        return None


# --- writing --------------------------------------------------------------

class Writer(threading.Thread):
    """Writes the image, then reads the stick back and compares the two."""

    def __init__(self, image, stick, verify, progress, done):
        super().__init__(daemon=True)
        self.image, self.stick, self.verify = image, stick, verify
        self.progress, self.done = progress, done
        self.cancelled = threading.Event()
        self.written = 0
        self.digest = None

    def cancel(self):
        self.cancelled.set()

    def _report(self, fraction, text):
        GLib.idle_add(self.progress, fraction, text)

    def run(self):
        try:
            self._write()
            if self.cancelled.is_set():
                GLib.idle_add(self.done, False, _("Stopped. The stick is half written."))
                return
            if self.verify:
                self._check()
                if self.cancelled.is_set():
                    GLib.idle_add(self.done, False, _("Stopped before checking finished."))
                    return
            GLib.idle_add(self.done, True, "")
        except Exception as err:                      # one message, never a traceback
            GLib.idle_add(self.done, False, str(err))

    def _write(self):
        make_stream, total = opener(self.image)
        proc = subprocess.Popen(["pkexec", HELPER, "write", self.stick.path],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        digest = hashlib.sha256()
        try:
            with make_stream() as stream:
                while not self.cancelled.is_set():
                    chunk = stream.read(BLOCK)
                    if not chunk:
                        break
                    proc.stdin.write(chunk)
                    digest.update(chunk)
                    self.written += len(chunk)
                    if total:
                        self._report(min(0.99, self.written / total * (0.8 if self.verify else 1.0)),
                                     _("Writing {done} of {total}").format(
                                         done=human(self.written), total=human(total)))
                    else:
                        self._report(-1, _("Writing {done}").format(done=human(self.written)))
        except BrokenPipeError:
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
        self._report(0.8 if self.verify else 0.99, _("Finishing the write…"))
        out, err = proc.communicate()
        if proc.returncode == 126 or proc.returncode == 127:
            raise RuntimeError(_("Authorization was cancelled"))
        if proc.returncode != 0:
            raise RuntimeError((err.decode(errors="replace").strip() or
                                _("The stick could not be written")))
        if self.cancelled.is_set():
            return
        landed = int((out.decode().strip() or "0") or 0)
        if landed != self.written:
            raise RuntimeError(_("The stick took {landed} of {sent}").format(
                landed=human(landed), sent=human(self.written)))
        self.digest = digest.hexdigest()

    def _check(self):
        """Read the stick back and compare: a stick that drops writes is the
        usual reason a freshly written installer won't boot."""
        self._report(0.82, _("Checking the stick…"))
        proc = subprocess.Popen(["pkexec", HELPER, "read", self.stick.path, str(self.written)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        digest = hashlib.sha256()
        read = 0
        while read < self.written and not self.cancelled.is_set():
            chunk = proc.stdout.read(min(BLOCK, self.written - read))
            if not chunk:
                break
            digest.update(chunk)
            read += len(chunk)
            self._report(0.8 + 0.19 * read / self.written,
                         _("Checking {done} of {total}").format(
                             done=human(read), total=human(self.written)))
        proc.stdout.close()
        _o, err = proc.communicate()
        if self.cancelled.is_set():
            return
        if proc.returncode in (126, 127):
            raise RuntimeError(_("Authorization was cancelled"))
        if proc.returncode != 0:
            raise RuntimeError(err.decode(errors="replace").strip() or
                               _("The stick could not be read back"))
        if read != self.written or digest.hexdigest() != self.digest:
            raise RuntimeError(_("The stick does not hold what was written to it. "
                                 "It may be worn out or counterfeit — try another one."))


# --- the window -----------------------------------------------------------

class WriterWindow(Adw.ApplicationWindow):
    def __init__(self, app, image=None):
        super().__init__(application=app, title=_("USB Stick Writer"),
                         default_width=560, default_height=440)
        self.image = None
        self.sticks = []
        self.worker = None
        self.toasts = Adw.ToastOverlay()

        self.image_row = Adw.ActionRow(title=_("No image chosen"),
                                       subtitle=_("An .iso or .img file, compressed or not"))
        choose = Gtk.Button(label=_("Choose…"), valign=Gtk.Align.CENTER)
        choose.connect("clicked", lambda *_a: self._choose_image())
        self.image_row.add_suffix(choose)
        self.image_row.set_activatable_widget(choose)
        images = Adw.PreferencesGroup(title=_("Image"))
        images.add(self.image_row)

        self.sticks_group = Adw.PreferencesGroup(
            title=_("Stick"),
            description=_("Only removable and USB disks are listed. Everything on the one "
                          "you pick is erased."))
        self.stick_rows = []

        self.verify = Adw.SwitchRow(title=_("Check the stick afterwards"),
                                    subtitle=_("Reads it back and compares it with the image"),
                                    active=True)
        options = Adw.PreferencesGroup()
        options.add(self.verify)

        self.progress = Gtk.ProgressBar(show_text=True, text=" ", visible=False,
                                        margin_start=12, margin_end=12, margin_bottom=6)
        self.start = Gtk.Button(label=_("Write"), css_classes=["suggested-action", "pill"],
                                halign=Gtk.Align.CENTER, sensitive=False,
                                margin_top=6, margin_bottom=14)
        self.start.connect("clicked", lambda *_a: self._confirm())
        self.stop = Gtk.Button(label=_("Stop"), css_classes=["destructive-action", "pill"],
                               halign=Gtk.Align.CENTER, visible=False,
                               margin_top=6, margin_bottom=14)
        self.stop.connect("clicked", lambda *_a: self._cancel())

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                       margin_top=14, margin_bottom=8, margin_start=14, margin_end=14)
        for widget in (images, self.sticks_group, options):
            body.append(widget)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        column.append(Gtk.ScrolledWindow(child=body, vexpand=True,
                                         hscrollbar_policy=Gtk.PolicyType.NEVER))
        column.append(self.progress)
        column.append(self.start)
        column.append(self.stop)
        view = Adw.ToolbarView(content=column)
        header = Adw.HeaderBar()
        refresh = Gtk.Button(icon_name="view-refresh-symbolic",
                             tooltip_text=_("Look for sticks again"))
        refresh.connect("clicked", lambda *_a: self.refresh_sticks())
        header.pack_end(refresh)
        view.add_top_bar(header)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        self.refresh_sticks()
        if image:
            self._set_image(image)
        # Plugging a stick in while the window is open should show it.
        self._monitor = Gio.VolumeMonitor.get()
        for signal in ("drive-connected", "drive-disconnected", "drive-changed"):
            self._monitor.connect(signal, lambda *_a: self.refresh_sticks())

    # --- choosing ---

    def _choose_image(self):
        chooser = Gtk.FileDialog(title=_("Choose a disk image"))
        images = Gtk.FileFilter(name=_("Disk images"))
        for suffix in ("iso", "img", "raw", "bin", "dd", "gz", "xz", "bz2", "zst", "zip"):
            images.add_pattern(f"*.{suffix}")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(images)
        every = Gtk.FileFilter(name=_("All files"))
        every.add_pattern("*")
        filters.append(every)
        chooser.set_filters(filters)
        chooser.set_default_filter(images)

        def picked(dialog, result):
            try:
                file = dialog.open_finish(result)
            except GLib.Error:
                return
            if file is not None and file.get_path():
                self._set_image(file.get_path())
        chooser.open(self, None, picked)

    def _set_image(self, path):
        self.image = path
        try:
            size = os.path.getsize(path)
        except OSError as err:
            self.toasts.add_toast(Adw.Toast(title=str(err)))
            return
        self.image_row.set_title(os.path.basename(path))
        self.image_row.set_subtitle(f"{human(size)} · {os.path.dirname(path)}")
        self._update_start()

    def refresh_sticks(self):
        for row in self.stick_rows:
            self.sticks_group.remove(row)
        self.stick_rows = []
        self.sticks = removable_disks()
        if not self.sticks:
            row = Adw.ActionRow(title=_("No stick found"),
                                subtitle=_("Plug one in, then press the refresh button"))
            self.sticks_group.add(row)
            self.stick_rows = [row]
            self._update_start()
            return
        group = None
        for stick in self.sticks:
            row = Adw.ActionRow(title=stick.title, subtitle=stick.path)
            button = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            if group is None:
                group = button
                button.set_active(True)
            else:
                button.set_group(group)
            button.connect("toggled", lambda *_a: self._update_start())
            row.add_prefix(button)
            row.set_activatable_widget(button)
            stick.button = button
            points = stick.mount_points()
            if points:
                row.set_subtitle(f"{stick.path} · " +
                                 _("in use at {where}").format(where=", ".join(points)))
            self.sticks_group.add(row)
            self.stick_rows.append(row)
        self._update_start()

    def _chosen(self):
        for stick in self.sticks:
            if getattr(stick, "button", None) is not None and stick.button.get_active():
                return stick
        return None

    def _update_start(self):
        self.start.set_sensitive(bool(self.image) and self._chosen() is not None
                                 and self.worker is None)

    # --- writing ---

    def _confirm(self):
        stick = self._chosen()
        if stick is None or not self.image:
            return
        try:
            _stream, total = opener(self.image)
        except (OSError, ValueError) as err:
            self.toasts.add_toast(Adw.Toast(title=str(err)))
            return
        if total and total > stick.size:
            self.toasts.add_toast(Adw.Toast(
                title=_("The image needs {needed}; the stick holds {has}").format(
                    needed=human(total), has=human(stick.size))))
            return
        dialog = Adw.AlertDialog(
            heading=_("Erase {stick}?").format(stick=stick.label),
            body=_("Everything on {path} ({size}) is replaced by {image}. "
                   "There is no undo.").format(path=stick.path, size=human(stick.size),
                                               image=os.path.basename(self.image)))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("write", _("Erase and Write"))
        dialog.set_response_appearance("write", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.connect("response", lambda _d, response: response == "write" and self._go(stick))
        dialog.present(self)

    def _go(self, stick):
        self.progress.set_visible(True)
        self.progress.set_fraction(0)
        self.progress.set_text(_("Starting…"))
        self.start.set_visible(False)
        self.stop.set_visible(True)
        self.set_deletable(False)
        self.worker = Writer(self.image, stick, self.verify.get_active(),
                             self._on_progress, self._on_done)
        self.worker.start()

    def _on_progress(self, fraction, text):
        if fraction < 0:
            self.progress.pulse()
        else:
            self.progress.set_fraction(fraction)
        self.progress.set_text(text)
        return False

    def _on_done(self, ok, message):
        self.worker = None
        self.set_deletable(True)
        self.stop.set_visible(False)
        self.start.set_visible(True)
        self.progress.set_fraction(1.0 if ok else 0.0)
        self.progress.set_text(_("Done — the stick is ready") if ok else message)
        self.toasts.add_toast(Adw.Toast(
            title=_("The stick is ready") if ok else message,
            timeout=3 if ok else 8))
        self.refresh_sticks()
        self._update_start()
        return False

    def _cancel(self):
        if self.worker is not None:
            self.worker.cancel()
            self.progress.set_text(_("Stopping…"))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.UsbWriter",
                         flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.image = None

    def do_open(self, files, _n, _hint):
        """Files → Open With → USB Stick Writer, with the image already chosen."""
        paths = [f.get_path() for f in files if f.get_path()]
        self.image = paths[0] if paths else None
        self.do_activate()

    def do_activate(self):
        window = self.props.active_window
        if window is None:
            window = WriterWindow(self, self.image)
        elif self.image:
            window._set_image(self.image)
        window.present()


def main():
    return App().run(sys.argv)
