"""Migrate from Windows: bring your files over from a Windows installation.

For the person who has just installed Aurora beside Windows, or who still has
the old disk. It finds the Windows installations on the computer's disks, lists
the accounts in each one, and copies the documents, pictures, music, videos,
downloads and desktop of the account you pick into the matching folders here.

It also brings two things people look for afterwards and rarely find: the
bookmarks of Edge, Chrome and Firefox (written out as one bookmarks file that
any browser can import), and the desktop background Windows was using.

Nothing on the Windows side is ever written to: the disk is mounted read-only,
and a file that already exists here is kept, never replaced.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from aurora.i18n import _  # noqa: E402

# A Windows folder and the GLib user directory it belongs in here.
FOLDERS = (
    ("Desktop", GLib.UserDirectory.DIRECTORY_DESKTOP, "user-desktop"),
    ("Documents", GLib.UserDirectory.DIRECTORY_DOCUMENTS, "folder-documents"),
    ("Downloads", GLib.UserDirectory.DIRECTORY_DOWNLOAD, "folder-download"),
    ("Pictures", GLib.UserDirectory.DIRECTORY_PICTURES, "folder-pictures"),
    ("Music", GLib.UserDirectory.DIRECTORY_MUSIC, "folder-music"),
    ("Videos", GLib.UserDirectory.DIRECTORY_VIDEOS, "folder-videos"),
)
# Profiles Windows keeps for itself.
SKIP_PROFILES = {"default", "default user", "public", "all users", "defaultaccount",
                 "wdagutilityaccount", "administrator"}
SIZE_DEADLINE = 25          # seconds spent measuring a profile, at most


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# --- finding Windows ------------------------------------------------------

def _lsblk():
    try:
        out = subprocess.run(["lsblk", "-J", "-o", "NAME,PATH,FSTYPE,LABEL,SIZE,MOUNTPOINT,RM"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout if out.returncode == 0 else "{}"
    except (OSError, subprocess.SubprocessError):
        return "{}"


def ntfs_partitions(listing=None):
    """Every NTFS filesystem on the computer, whatever disk it is on."""
    try:
        tree = json.loads(listing if listing is not None else _lsblk())
    except ValueError:
        return []
    found = []

    def walk(nodes):
        for node in nodes or []:
            if (node.get("fstype") or "").lower() == "ntfs":
                found.append({"path": node.get("path") or "",
                              "label": node.get("label") or "",
                              "size": node.get("size") or "",
                              "mountpoint": node.get("mountpoint") or "",
                              "removable": bool(node.get("rm"))})
            walk(node.get("children"))

    walk(tree.get("blockdevices"))
    return [p for p in found if p["path"]]


def is_windows(root):
    """A Windows installation, not just an NTFS disk with files on it."""
    if not root:
        return False
    system = os.path.join(root, "Windows", "System32")
    return os.path.isdir(system) and os.path.isdir(os.path.join(root, "Users"))


def mount(device):
    """Mount a partition read-only through udisks, or give its mount point if
    it is already mounted. Returns (path, mounted_by_us) or (None, False)."""
    for partition in ntfs_partitions():
        if partition["path"] == device and partition["mountpoint"]:
            return partition["mountpoint"], False
    try:
        out = subprocess.run(["udisksctl", "mount", "-b", device, "--options", "ro"],
                             capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as err:
        print(f"aurora: could not mount {device}: {err}")
        return None, False
    if out.returncode != 0:
        print(f"aurora: could not mount {device}: {out.stderr.strip()}")
        return None, False
    # "Mounted /dev/sdb1 at /media/luca/Windows."
    text = out.stdout.strip().rstrip(".")
    at = text.rsplit(" at ", 1)
    return (at[1], True) if len(at) == 2 else (None, False)


def unmount(device):
    try:
        subprocess.run(["udisksctl", "unmount", "-b", device],
                       capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pass


# --- the accounts on it ---------------------------------------------------

def profiles(root):
    """The real accounts in C:\\Users, newest first by what they hold."""
    users = os.path.join(root, "Users")
    out = []
    try:
        names = sorted(os.listdir(users))
    except OSError:
        return out
    for name in names:
        path = os.path.join(users, name)
        if name.lower() in SKIP_PROFILES or not os.path.isdir(path):
            continue
        folders = []
        for windows_name, target, icon in FOLDERS:
            source = os.path.join(path, windows_name)
            if os.path.isdir(source):
                folders.append({"name": windows_name, "path": source,
                                "target": target, "icon": icon})
        if folders:
            out.append({"name": name, "path": path, "folders": folders})
    return out


def measure(path, deadline=SIZE_DEADLINE, stop=None):
    """How much is in a folder: (bytes, files). Gives up politely on a huge
    tree rather than keeping the window waiting — the number is there to help
    someone choose, not to be exact."""
    total = count = 0
    ends = time.monotonic() + deadline
    for base, _dirs, files in os.walk(path, onerror=lambda _e: None):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                continue
            count += 1
        if time.monotonic() > ends or (stop is not None and stop.is_set()):
            return total, count, False
    return total, count, True


# --- bookmarks ------------------------------------------------------------

def chromium_bookmarks(path):
    """[(title, url)] from a Chrome or Edge Bookmarks file, folders flattened."""
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        return []
    found = []

    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "url" and node.get("url"):
            found.append((node.get("name") or node["url"], node["url"]))
        for child in node.get("children") or []:
            walk(child)

    for root in (data.get("roots") or {}).values():
        walk(root)
    return found


def browser_bookmark_files(profile_path):
    """Where Edge, Chrome and Brave keep their bookmarks in a Windows profile."""
    local = os.path.join(profile_path, "AppData", "Local")
    roaming = os.path.join(profile_path, "AppData", "Roaming")
    candidates = {
        "Microsoft Edge": os.path.join(local, "Microsoft", "Edge", "User Data", "Default",
                                       "Bookmarks"),
        "Google Chrome": os.path.join(local, "Google", "Chrome", "User Data", "Default",
                                      "Bookmarks"),
        "Brave": os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data", "Default",
                              "Bookmarks"),
        "Opera": os.path.join(roaming, "Opera Software", "Opera Stable", "Bookmarks"),
    }
    return {name: path for name, path in candidates.items() if os.path.isfile(path)}


def bookmarks_html(sections):
    """One bookmarks file in the format every browser imports, with a folder
    per browser it came from."""
    def esc(text):
        return (str(text).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    out = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
           '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
           "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks</H1>", "<DL><p>"]
    for name, items in sections.items():
        if not items:
            continue
        out.append(f"    <DT><H3>{esc(name)}</H3>")
        out.append("    <DL><p>")
        for title, url in items:
            out.append(f'        <DT><A HREF="{esc(url)}">{esc(title)}</A>')
        out.append("    </DL><p>")
    out.append("</DL><p>")
    return "\n".join(out) + "\n"


def windows_wallpaper(profile_path):
    """The picture Windows was showing on the desktop, if it is still there."""
    cached = os.path.join(profile_path, "AppData", "Roaming", "Microsoft", "Windows",
                          "Themes", "TranscodedWallpaper")
    return cached if os.path.isfile(cached) else None


# --- copying --------------------------------------------------------------

def copy_plan(profile, chosen, home=None):
    """[(source, destination)] for the folders that were picked."""
    home = home or GLib.get_home_dir()
    plan = []
    for folder in profile["folders"]:
        if folder["name"] not in chosen:
            continue
        target = GLib.get_user_special_dir(folder["target"]) or \
            os.path.join(home, folder["name"])
        plan.append((folder["path"], target))
    return plan


def copy_tree(source, destination, progress=None, stop=None, skipped=None):
    """Copy what isn't there yet. Files already here are left exactly as they
    are: this runs on a home directory someone is already using."""
    copied = 0
    for base, dirs, files in os.walk(source, onerror=lambda _e: None):
        dirs[:] = [d for d in dirs if not d.startswith("$") and d.lower() != "desktop.ini"]
        relative = os.path.relpath(base, source)
        here = destination if relative == "." else os.path.join(destination, relative)
        try:
            os.makedirs(here, exist_ok=True)
        except OSError:
            continue
        for name in files:
            if stop is not None and stop.is_set():
                return copied
            if name.lower() in ("desktop.ini", "thumbs.db") or name.startswith("~$"):
                continue
            src, dst = os.path.join(base, name), os.path.join(here, name)
            if os.path.exists(dst):
                if skipped is not None:
                    skipped.append(dst)
                continue
            try:
                shutil.copy2(src, dst)
                copied += 1
            except (OSError, shutil.Error):
                continue
            if progress is not None:
                progress(copied, name)
    return copied


class Migration(threading.Thread):
    """The copying, off the window's thread."""

    def __init__(self, profile, chosen, extras, progress, done):
        super().__init__(daemon=True)
        self.profile, self.chosen, self.extras = profile, chosen, extras
        self.progress, self.done = progress, done
        self.stop_flag = threading.Event()
        self.copied = 0
        self.skipped = []
        self.notes = []

    def cancel(self):
        self.stop_flag.set()

    def run(self):
        try:
            for source, destination in copy_plan(self.profile, self.chosen):
                if self.stop_flag.is_set():
                    break
                name = os.path.basename(source)
                GLib.idle_add(self.progress, -1, _("Copying {folder}…").format(folder=name))
                self.copied += copy_tree(
                    source, destination,
                    progress=lambda n, f: GLib.idle_add(
                        self.progress, -1, _("Copying {folder}: {file}").format(
                            folder=name, file=f)),
                    stop=self.stop_flag, skipped=self.skipped)
            if "bookmarks" in self.extras and not self.stop_flag.is_set():
                self._bookmarks()
            if "wallpaper" in self.extras and not self.stop_flag.is_set():
                self._wallpaper()
            GLib.idle_add(self.done, not self.stop_flag.is_set(), "")
        except Exception as err:                      # one message, never a traceback
            GLib.idle_add(self.done, False, str(err))

    def _bookmarks(self):
        GLib.idle_add(self.progress, -1, _("Collecting bookmarks…"))
        sections = {}
        for browser, path in browser_bookmark_files(self.profile["path"]).items():
            items = chromium_bookmarks(path)
            if items:
                sections[browser] = items
        if not sections:
            return
        target = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)
                              or GLib.get_home_dir(), "Windows bookmarks.html")
        try:
            with open(target, "w", encoding="utf-8") as stream:
                stream.write(bookmarks_html(sections))
        except OSError as err:
            self.notes.append(str(err))
            return
        total = sum(len(items) for items in sections.values())
        self.notes.append(_("{n} bookmarks from {browsers} are in {file} — open it in your "
                            "browser's bookmark manager to import them.").format(
                                n=total, browsers=", ".join(sections), file=target))

    def _wallpaper(self):
        source = windows_wallpaper(self.profile["path"])
        if source is None:
            return
        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or \
            GLib.get_home_dir()
        target = os.path.join(pictures, "Windows background.jpg")
        try:
            shutil.copy2(source, target)
        except (OSError, shutil.Error) as err:
            self.notes.append(str(err))
            return
        self.notes.append(_("The background Windows was using is in {file}.").format(
            file=target))


# --- the window -----------------------------------------------------------

class Assistant(Adw.ApplicationWindow):
    """Four steps: the disk, the account, what to bring, and the copying."""

    def __init__(self, app):
        super().__init__(application=app, title=_("Migrate from Windows"),
                         default_width=640, default_height=580)
        self.disk = None            # the partition being read
        self.mounted_by_us = False
        self.root = None
        self.profile = None
        self.worker = None
        self.toasts = Adw.ToastOverlay()
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        view = Adw.ToolbarView(content=self.stack)
        self.header = Adw.HeaderBar()
        self.back = Gtk.Button(icon_name="go-previous-symbolic", visible=False,
                               tooltip_text=_("Back"))
        self.back.connect("clicked", lambda *_a: self._go("disks"))
        self.header.pack_start(self.back)
        view.add_top_bar(self.header)
        self.toasts.set_child(view)
        self.set_content(self.toasts)
        self.connect("close-request", self._closing)

        self.stack.add_named(self._page_disks(), "disks")
        self.stack.add_named(self._page_profiles(), "profiles")
        self.stack.add_named(self._page_choose(), "choose")
        self.stack.add_named(self._page_copy(), "copy")
        self.find_disks()

    # --- step one: the disk ---

    def _page_disks(self):
        self.disks_group = Adw.PreferencesGroup(
            title=_("Windows disks"),
            description=_("Aurora looks for Windows on every disk in this computer, "
                          "including one plugged in over USB. Nothing on it is written to: "
                          "it is opened read-only."))
        self.disks_rows = []
        refresh = Gtk.Button(label=_("Look Again"), css_classes=["pill"],
                             halign=Gtk.Align.CENTER)
        refresh.connect("clicked", lambda *_a: self.find_disks())
        return self._column(self.disks_group, refresh)

    def find_disks(self):
        for row in self.disks_rows:
            self.disks_group.remove(row)
        self.disks_rows = []
        partitions = ntfs_partitions()
        if not partitions:
            row = Adw.ActionRow(title=_("No Windows disk found"),
                                subtitle=_("If Windows is on another disk, plug it in and "
                                           "press Look Again"))
            self.disks_group.add(row)
            self.disks_rows = [row]
            return
        for partition in partitions:
            title = partition["label"] or _("Windows disk")
            row = Adw.ActionRow(title=title, activatable=True,
                                subtitle=f"{partition['path']} · {partition['size']}"
                                + (" · " + _("removable") if partition["removable"] else ""))
            row.add_prefix(Gtk.Image(icon_name="drive-harddisk-symbolic"))
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", lambda _r, p=partition: self._open_disk(p))
            self.disks_group.add(row)
            self.disks_rows.append(row)

    def _open_disk(self, partition):
        self.toasts.add_toast(Adw.Toast(title=_("Opening {disk}…").format(
            disk=partition["path"]), timeout=2))

        def work():
            root, ours = mount(partition["path"])
            GLib.idle_add(opened, root, ours)

        def opened(root, ours):
            if root is None:
                self.toasts.add_toast(Adw.Toast(
                    title=_("That disk could not be opened"), timeout=6))
                return False
            if not is_windows(root):
                if ours:
                    unmount(partition["path"])
                self.toasts.add_toast(Adw.Toast(
                    title=_("There is no Windows installation on that disk"), timeout=6))
                return False
            self.disk, self.root, self.mounted_by_us = partition, root, ours
            self.show_profiles()
            return False

        threading.Thread(target=work, daemon=True).start()

    # --- step two: the account ---

    def _page_profiles(self):
        self.profiles_group = Adw.PreferencesGroup(
            title=_("Accounts on that Windows"),
            description=_("Pick the one whose files you want here."))
        self.profile_rows = []
        return self._column(self.profiles_group)

    def show_profiles(self):
        for row in self.profile_rows:
            self.profiles_group.remove(row)
        self.profile_rows = []
        found = profiles(self.root)
        if not found:
            row = Adw.ActionRow(title=_("No accounts with files on them"))
            self.profiles_group.add(row)
            self.profile_rows = [row]
        for profile in found:
            row = Adw.ActionRow(title=profile["name"], activatable=True,
                                subtitle=", ".join(f["name"] for f in profile["folders"]))
            row.add_prefix(Gtk.Image(icon_name="avatar-default-symbolic"))
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", lambda _r, p=profile: self.show_choices(p))
            self.profiles_group.add(row)
            self.profile_rows.append(row)
        self._go("profiles")

    # --- step three: what to bring ---

    def _page_choose(self):
        self.choose_group = Adw.PreferencesGroup(title=_("What to bring over"))
        self.extras_group = Adw.PreferencesGroup(
            title=_("And these"),
            description=_("Files that are already here are kept, never replaced."))
        self.choose_rows = []
        self.start = Gtk.Button(label=_("Bring My Files"), halign=Gtk.Align.CENTER,
                                css_classes=["suggested-action", "pill"])
        self.start.connect("clicked", lambda *_a: self._start())
        return self._column(self.choose_group, self.extras_group, self.start)

    def show_choices(self, profile):
        self.profile = profile
        for row in self.choose_rows:
            self.choose_group.remove(row)
        self.choose_rows = []
        self.switches = {}
        for folder in profile["folders"]:
            row = Adw.SwitchRow(title=folder["name"], active=True,
                                subtitle=_("Measuring…"))
            row.add_prefix(Gtk.Image(icon_name=folder["icon"]))
            self.choose_group.add(row)
            self.choose_rows.append(row)
            self.switches[folder["name"]] = row
            self._measure(folder, row)
        self.bookmarks = Adw.SwitchRow(
            title=_("Browser bookmarks"), active=True,
            subtitle=_("Edge, Chrome, Brave and Opera, written to one file any browser "
                       "can import"))
        self.bookmarks.add_prefix(Gtk.Image(icon_name="user-bookmarks-symbolic"))
        self.wallpaper = Adw.SwitchRow(
            title=_("Desktop background"), active=True,
            subtitle=_("The picture Windows was showing, copied to Pictures"))
        self.wallpaper.add_prefix(Gtk.Image(icon_name="preferences-desktop-wallpaper-symbolic"))
        for row in (self.bookmarks, self.wallpaper):
            if row.get_parent() is None:
                self.extras_group.add(row)
        self.bookmarks.set_sensitive(bool(browser_bookmark_files(profile["path"])))
        self.wallpaper.set_sensitive(windows_wallpaper(profile["path"]) is not None)
        for row in (self.bookmarks, self.wallpaper):
            if not row.get_sensitive():
                row.set_active(False)
                row.set_subtitle(_("Not found in that account"))
        self._go("choose")

    def _measure(self, folder, row):
        def work():
            size, count, whole = measure(folder["path"])
            GLib.idle_add(show, size, count, whole)

        def show(size, count, whole):
            if count == 0:
                row.set_subtitle(_("Empty"))
                row.set_active(False)
                row.set_sensitive(False)
            else:
                about = "" if whole else _("at least ")
                row.set_subtitle(_("{about}{n} files · {size}").format(
                    about=about, n=count, size=human(size)))
            return False

        threading.Thread(target=work, daemon=True).start()

    # --- step four: the copying ---

    def _page_copy(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                      margin_top=24, margin_bottom=18, margin_start=18, margin_end=18,
                      valign=Gtk.Align.CENTER)
        self.copy_title = Gtk.Label(label=_("Bringing your files over"),
                                    css_classes=["title-2"])
        self.copy_line = Gtk.Label(label="", wrap=True, css_classes=["dim-label"])
        self.copy_bar = Gtk.ProgressBar(show_text=False)
        self.copy_notes = Gtk.Label(label="", wrap=True, xalign=0,
                                    css_classes=["dim-label"], visible=False)
        self.stop_button = Gtk.Button(label=_("Stop"), halign=Gtk.Align.CENTER,
                                      css_classes=["pill"])
        self.stop_button.connect("clicked", lambda *_a: self.worker and self.worker.cancel())
        self.close_button = Gtk.Button(label=_("Done"), halign=Gtk.Align.CENTER,
                                       css_classes=["suggested-action", "pill"], visible=False)
        self.close_button.connect("clicked", lambda *_a: self.close())
        for widget in (self.copy_title, self.copy_line, self.copy_bar, self.copy_notes,
                       self.stop_button, self.close_button):
            box.append(widget)
        return box

    def _start(self):
        chosen = [name for name, row in self.switches.items()
                  if row.get_active() and row.get_sensitive()]
        extras = set()
        if self.bookmarks.get_active():
            extras.add("bookmarks")
        if self.wallpaper.get_active():
            extras.add("wallpaper")
        if not chosen and not extras:
            self.toasts.add_toast(Adw.Toast(title=_("Nothing is chosen")))
            return
        self._go("copy")
        self.back.set_visible(False)
        self._pulse = GLib.timeout_add(120, lambda: (self.copy_bar.pulse(), True)[1])
        self.worker = Migration(self.profile, chosen, extras, self._on_progress, self._on_done)
        self.worker.start()

    def _on_progress(self, _fraction, text):
        self.copy_line.set_label(text)
        return False

    def _on_done(self, ok, message):
        GLib.source_remove(self._pulse)
        worker, self.worker = self.worker, None
        self.copy_bar.set_fraction(1.0 if ok else 0.0)
        self.stop_button.set_visible(False)
        self.close_button.set_visible(True)
        if ok:
            self.copy_title.set_label(_("Your files are here"))
            self.copy_line.set_label(_("{n} files copied. {kept} were already here and were "
                                       "left alone.").format(n=worker.copied,
                                                             kept=len(worker.skipped)))
        else:
            self.copy_title.set_label(_("Stopped") if not message else _("Something went wrong"))
            self.copy_line.set_label(message or _("What had been copied is here."))
        if worker.notes:
            self.copy_notes.set_label("\n".join(worker.notes))
            self.copy_notes.set_visible(True)
        return False

    # --- moving between the steps ---

    def _column(self, *widgets):
        """One scrolling column, which is what every step but the last is."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                      margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        for widget in widgets:
            box.append(widget)
        return Gtk.ScrolledWindow(child=box, hscrollbar_policy=Gtk.PolicyType.NEVER)

    def _go(self, page):
        self.stack.set_visible_child_name(page)
        self.back.set_visible(page in ("profiles", "choose"))

    def _closing(self, *_a):
        if self.worker is not None:
            self.worker.cancel()
        if self.mounted_by_us and self.disk is not None:
            unmount(self.disk["path"])
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Migrate")

    def do_activate(self):
        window = self.props.active_window or Assistant(self)
        window.present()


def main():
    return App().run(sys.argv[:1])
