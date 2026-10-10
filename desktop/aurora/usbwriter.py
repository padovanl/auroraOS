"""USB Stick Writer: put a disk image on a stick, the way Rufus or Etcher do.

Pick the image, pick the stick, confirm once, watch the bar. Compressed images
(.gz, .xz, .bz2, .zst, and a .zip holding a single image) are decompressed as
they are written, so there is no need to unpack a 5 GB download first. When the
write is done the stick is read back and compared, byte for byte, with what was
sent — a stick that quietly drops writes is the usual reason an installer boots
to a corrupt file.

It also does the two things people go looking for afterwards: checking that the
download itself is sound before it goes anywhere (the SHA-256 beside it, or one
pasted in), and giving a stick its life back as a plain empty disk once the
installer on it has done its job.

Only removable and USB disks are offered, the disk this system runs from is
never among them, and the actual work is done by /usr/libexec/aurora-usb-write
through pkexec, which checks all of that again on its own side: a program
asking for a disk to be overwritten cannot be trusted to have asked the right
questions.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from aurora.i18n import _  # noqa: E402

HELPER = "/usr/libexec/aurora-usb-write"
BLOCK = 4 * 1024 * 1024
# Where a stick goes back to being a stick. exFAT first: FAT32 stops at 4 GB
# per file, and every other computer reads exFAT too.
FILESYSTEMS = (("exfat", "exFAT"), ("fat32", "FAT32"), ("ext4", "Ext4"))
# Mount points that mean a disk is this running system, not a spare stick.
SYSTEM_PATHS = ("/", "/boot", "/boot/efi", "/efi", "/usr", "/var", "/home",
                "/run/live/medium", "/run/live/rootfs", "/lib/live/mount/medium")


def partition_of(device):
    """The first partition's node: /dev/sdb -> /dev/sdb1, /dev/mmcblk0 -> p1."""
    return device + ("p1" if device[-1].isdigit() else "1")


def prefs_path():
    return os.path.join(GLib.get_user_config_dir(), "aurora", "usb-writer.json")


def prefs():
    """What was chosen last time: the checks and the format of an erased stick."""
    try:
        with open(prefs_path(), encoding="utf-8") as stream:
            saved = json.load(stream)
    except (OSError, ValueError):
        saved = {}
    known = [name for name, _label in FILESYSTEMS]
    return {"verify": bool(saved.get("verify", True)),
            "eject": bool(saved.get("eject", True)),
            "filesystem": saved.get("filesystem") if saved.get("filesystem") in known
            else known[0]}


def save_prefs(values):
    target = prefs_path()
    try:
        os.makedirs(os.path.dirname(target), mode=0o700, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".usb-writer-", dir=os.path.dirname(target))
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(values, stream)
        os.replace(name, target)
    except OSError as err:
        print(f"aurora: USB Stick Writer settings not saved: {err}")


# --- checking the image itself --------------------------------------------

SHA256 = re.compile(r"\b([0-9a-fA-F]{64})\b")


def stated_checksum(image):
    """The SHA-256 the download came with: <image>.sha256, .sha256sum, or a
    line naming this file in a SHA256SUMS next to it. None when there is none."""
    directory, name = os.path.split(image)
    for candidate in (image + ".sha256", image + ".sha256sum", image + ".sha256.txt"):
        text = _read_text(candidate)
        found = SHA256.search(text or "")
        if found:
            return found.group(1).lower(), os.path.basename(candidate)
    for listing in ("SHA256SUMS", "sha256sums.txt", "SHA256SUMS.txt"):
        text = _read_text(os.path.join(directory, listing))
        for line in (text or "").splitlines():
            if name in line:
                found = SHA256.search(line)
                if found:
                    return found.group(1).lower(), listing
    return None


def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as stream:
            return stream.read(64 * 1024)
    except OSError:
        return None


def checksum(path, progress=None, stop=None):
    """The image's own SHA-256, read in blocks so a 5 GB file can be stopped."""
    digest = hashlib.sha256()
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb", buffering=0) as stream:
        while stop is None or not stop.is_set():
            chunk = stream.read(BLOCK)
            if not chunk:
                break
            digest.update(chunk)
            done += len(chunk)
            if progress is not None and total:
                progress(done / total)
    return digest.hexdigest()


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
                         default_width=580, default_height=660)
        self.image = None
        self.sticks = []
        self.worker = None
        self.hasher = None
        self.settings = prefs()
        self.toasts = Adw.ToastOverlay()

        self.image_row = Adw.ActionRow(title=_("No image chosen"),
                                       subtitle=_("An .iso or .img file, compressed or not"))
        choose = Gtk.Button(label=_("Choose…"), valign=Gtk.Align.CENTER)
        choose.connect("clicked", lambda *_a: self._choose_image())
        self.image_row.add_suffix(choose)
        self.image_row.set_activatable_widget(choose)
        # Checking the download before it goes anywhere: the SHA-256 that came
        # with it, or one pasted from the page it was downloaded from.
        self.sum_row = Adw.ActionRow(title=_("Check the download"), visible=False,
                                     subtitle=_("Compares the file with its SHA-256"))
        self.sum_entry = Gtk.Entry(placeholder_text=_("Paste the SHA-256 here"),
                                   valign=Gtk.Align.CENTER, width_chars=18, hexpand=True)
        self.sum_entry.connect("activate", lambda *_a: self._check_image())
        self.sum_button = Gtk.Button(label=_("Check"), valign=Gtk.Align.CENTER)
        self.sum_button.connect("clicked", lambda *_a: self._check_image())
        self.sum_row.add_suffix(self.sum_entry)
        self.sum_row.add_suffix(self.sum_button)
        images = Adw.PreferencesGroup(title=_("Image"))
        images.add(self.image_row)
        images.add(self.sum_row)

        self.sticks_group = Adw.PreferencesGroup(
            title=_("Stick"),
            description=_("Only removable and USB disks are listed. Everything on the one "
                          "you pick is erased."))
        self.stick_rows = []

        self.verify = Adw.SwitchRow(title=_("Check the stick afterwards"),
                                    subtitle=_("Reads it back and compares it with the image"),
                                    active=self.settings["verify"])
        self.eject = Adw.SwitchRow(title=_("Eject when finished"),
                                   subtitle=_("Flushes it and powers it down, so it can be "
                                              "pulled out straight away"),
                                   active=self.settings["eject"])
        for row in (self.verify, self.eject):
            row.connect("notify::active", lambda *_a: self._remember())
        options = Adw.PreferencesGroup(title=_("Options"))
        options.add(self.verify)
        options.add(self.eject)

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
        menu = Gio.Menu()
        menu.append(_("Erase the Stick…"), "win.erase")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       tooltip_text=_("Menu")))
        for name, callback in (("erase", self._ask_erase),):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_a, cb=callback: cb())
            self.add_action(action)
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
        self.sum_row.set_visible(True)
        stated = stated_checksum(path)
        if stated is not None:
            self.sum_entry.set_text(stated[0])
            self.sum_row.set_subtitle(_("The SHA-256 from {file}").format(file=stated[1]))
        else:
            self.sum_entry.set_text("")
            self.sum_row.set_subtitle(_("Paste the SHA-256 from the download page, if you "
                                        "have it"))
        self.sum_row.remove_css_class("success")
        self.sum_row.remove_css_class("error")
        self._update_start()

    # --- checking the download ---

    def _check_image(self):
        wanted = SHA256.search(self.sum_entry.get_text() or "")
        if self.image is None:
            return
        if wanted is None:
            self.toasts.add_toast(Adw.Toast(title=_("That is not a SHA-256")))
            return
        if self.hasher is not None:
            return
        wanted = wanted.group(1).lower()
        self.sum_button.set_sensitive(False)
        self.progress.set_visible(True)
        self.progress.set_text(_("Checking the download…"))
        stop = threading.Event()

        def work():
            try:
                got = checksum(self.image, lambda f: GLib.idle_add(self._sum_progress, f), stop)
            except OSError as err:
                GLib.idle_add(self._sum_done, None, wanted, str(err))
                return
            GLib.idle_add(self._sum_done, got, wanted, "")

        self.hasher = threading.Thread(target=work, daemon=True)
        self.hasher.start()

    def _sum_progress(self, fraction):
        self.progress.set_fraction(fraction)
        return False

    def _sum_done(self, got, wanted, error):
        self.hasher = None
        self.sum_button.set_sensitive(True)
        self.progress.set_visible(False)
        self.sum_row.remove_css_class("success")
        self.sum_row.remove_css_class("error")
        if error:
            self.toasts.add_toast(Adw.Toast(title=error))
            return False
        if got == wanted:
            self.sum_row.add_css_class("success")
            self.sum_row.set_subtitle(_("The download matches its SHA-256"))
            self.toasts.add_toast(Adw.Toast(title=_("The download is sound"), timeout=3))
        else:
            self.sum_row.add_css_class("error")
            self.sum_row.set_subtitle(_("The file's SHA-256 is {got}").format(got=got))
            self.toasts.add_toast(Adw.Toast(
                title=_("The download does not match — download it again"), timeout=8))
        return False

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
        self.stick = stick
        self.worker = Writer(self.image, stick, self.verify.get_active(),
                             self._on_progress, self._on_done)
        self.worker.start()

    # --- erasing a stick back to a plain disk ---

    def _ask_erase(self):
        stick = self._chosen()
        if stick is None or self.worker is not None:
            return
        dialog = Adw.AlertDialog(
            heading=_("Erase {stick}?").format(stick=stick.label),
            body=_("Everything on {path} ({size}) is removed and the stick becomes one "
                   "empty disk again — which is what it takes to use a stick for files "
                   "after an installer has been written to it.").format(
                       path=stick.path, size=human(stick.size)))
        name = Adw.EntryRow(title=_("Name"), text="USB")
        kinds = Adw.ComboRow(title=_("Format"),
                             model=Gtk.StringList.new([label for _id, label in FILESYSTEMS]),
                             subtitle=_("exFAT is read by Windows and macOS too, and holds "
                                        "files larger than 4 GB"))
        chosen = [name for name, _label in FILESYSTEMS].index(self.settings["filesystem"])
        kinds.set_selected(chosen)
        group = Adw.PreferencesGroup()
        group.add(name)
        group.add(kinds)
        dialog.set_extra_child(group)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("erase", _("Erase"))
        dialog.set_response_appearance("erase", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def answered(_dialog, response):
            if response != "erase":
                return
            filesystem = FILESYSTEMS[kinds.get_selected()][0]
            self.settings["filesystem"] = filesystem
            save_prefs(self.settings)
            self._erase(stick, filesystem, name.get_text().strip() or "USB")
        dialog.connect("response", answered)
        dialog.present(self)

    def _erase(self, stick, filesystem, name):
        self.progress.set_visible(True)
        self.progress.set_fraction(0)
        self.progress.set_text(_("Erasing {stick}…").format(stick=stick.label))
        self.start.set_sensitive(False)
        self.set_deletable(False)
        pulse = GLib.timeout_add(120, lambda: (self.progress.pulse(), True)[1])

        def work():
            try:
                proc = subprocess.run(["pkexec", HELPER, "format", stick.path,
                                       filesystem, name], capture_output=True, timeout=600)
            except (OSError, subprocess.SubprocessError) as err:
                GLib.idle_add(done, False, str(err))
                return
            if proc.returncode in (126, 127):
                GLib.idle_add(done, False, _("Authorization was cancelled"))
                return
            GLib.idle_add(done, proc.returncode == 0,
                          proc.stderr.decode(errors="replace").strip() or
                          _("The stick could not be erased"))

        def done(ok, message):
            GLib.source_remove(pulse)
            self.set_deletable(True)
            self.start.set_sensitive(True)
            self.progress.set_fraction(1.0 if ok else 0.0)
            self.progress.set_text(_("The stick is empty and ready for files") if ok
                                   else message)
            self.toasts.add_toast(Adw.Toast(
                title=_("{stick} is empty and ready for files").format(stick=stick.label)
                if ok else message, timeout=4 if ok else 8))
            self.refresh_sticks()
            self._update_start()
            return False

        threading.Thread(target=work, daemon=True).start()

    def _remember(self):
        self.settings["verify"] = self.verify.get_active()
        self.settings["eject"] = self.eject.get_active()
        save_prefs(self.settings)

    def _eject(self, stick):
        """Flush it and power it down, so it can be pulled out straight away.
        udisks lets the person at the keyboard do this without a password."""
        for argv in (["udisksctl", "unmount", "-b", partition_of(stick.path)],
                     ["udisksctl", "power-off", "-b", stick.path]):
            try:
                subprocess.run(argv, capture_output=True, timeout=30)
            except (OSError, subprocess.SubprocessError):
                return False
        return True

    def _on_progress(self, fraction, text):
        if fraction < 0:
            self.progress.pulse()
        else:
            self.progress.set_fraction(fraction)
        self.progress.set_text(text)
        return False

    def _on_done(self, ok, message):
        stick = getattr(self, "stick", None)
        self.worker = None
        self.set_deletable(True)
        self.stop.set_visible(False)
        self.start.set_visible(True)
        self.progress.set_fraction(1.0 if ok else 0.0)
        ejected = ok and self.eject.get_active() and stick is not None and self._eject(stick)
        if ok:
            text = (_("Done — you can unplug the stick") if ejected
                    else _("Done — the stick is ready"))
        else:
            text = message
        self.progress.set_text(text)
        self.toasts.add_toast(Adw.Toast(title=text if ok else message,
                                        timeout=4 if ok else 8))
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
