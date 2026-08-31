"""Settings → System Health ("Aurora Doctor"): checks the things that go wrong
on real computers and offers the fix, one click each.

Every check is a small function returning (status, summary, fix) where status
is "ok", "warn" or "bad" and fix is (label, callable) or None. Checks run in a
thread so the page opens instantly; none of them needs the admin password.
"""

import json
import os
import shutil
import subprocess
import threading

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from aurora import apps
from aurora.i18n import _, ngettext
from aurora.settingsapp.util import Page, toast

ICONS = {"ok": ("object-select-symbolic", "success"), "warn": ("dialog-warning-symbolic", "warning"),
         "bad": ("dialog-error-symbolic", "error")}


def _run(argv, timeout=20):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _open(argv):
    return lambda: apps.spawn(argv)


# --- checks ------------------------------------------------------------------

def check_disk_space():
    worst = None
    for path, label in (("/", _("System")), (os.path.expanduser("~"), _("Home"))):
        try:
            u = shutil.disk_usage(path)
        except OSError:
            continue
        free = u.free / u.total
        if worst is None or free < worst[0]:
            worst = (free, label, u.free)
    if worst is None:
        return "ok", _("Unknown"), None
    free, label, free_bytes = worst
    text = _("{label}: {free} free ({pct:.0f}%)").format(label=label,
                                                        free=GLib.format_size(free_bytes),
                                                        pct=free * 100)
    fix = (_("See What Uses Space"), _open(["baobab"]))
    if free < 0.05:
        return "bad", text, fix
    if free < 0.12:
        return "warn", text, fix
    return "ok", text, None


def smart_status(objects):
    """[(drive name, problem or None)] from UDisks2's managed objects."""
    out = []
    for _path, ifaces in objects.items():
        drive = ifaces.get("org.freedesktop.UDisks2.Drive")
        if not drive:
            continue
        name = " ".join(x for x in (drive.get("Vendor", ""), drive.get("Model", "")) if x) \
            or _("Disk")
        ata = ifaces.get("org.freedesktop.UDisks2.Drive.Ata")
        nvme = ifaces.get("org.freedesktop.UDisks2.NVMe.Controller")
        problem = None
        if ata and ata.get("SmartSupported") and ata.get("SmartEnabled"):
            if ata.get("SmartFailing"):
                problem = _("the disk reports that it is failing")
            elif ata.get("SmartNumBadSectors", 0) > 0:
                problem = _("{n} bad sectors").format(n=ata["SmartNumBadSectors"])
        if nvme and nvme.get("SmartCriticalWarning"):
            warnings = nvme["SmartCriticalWarning"]
            problem = _("critical warning: {w}").format(w=", ".join(warnings)) \
                if isinstance(warnings, list) else _("critical warning")
        if ata or nvme:
            out.append((name, problem))
    return out


def check_disk_health():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        res = bus.call_sync("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2",
                            "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None,
                            None, Gio.DBusCallFlags.NONE, 5000, None)
        drives = smart_status(res.unpack()[0])
    except GLib.Error:
        return "ok", _("Disk health isn't available on this computer"), None
    if not drives:
        return "ok", _("No disks report health data (normal in virtual machines)"), None
    failing = [f"{n}: {p}" for n, p in drives if p]
    if failing:
        return "bad", _("Back up your files now. ") + "; ".join(failing), \
            (_("Open Disks"), _open(["gnome-disks"]))
    return "ok", ngettext("{n} disk healthy", "{n} disks healthy", len(drives)).format(
        n=len(drives)), None


def check_updates():
    out = _run(["apt", "list", "--upgradable"], timeout=60)
    n = len([ln for ln in out.splitlines() if "/" in ln and "upgradable" in ln])
    if n:
        return "warn", ngettext("{n} update available", "{n} updates available", n).format(n=n), \
            (_("Update"), _open(["gnome-software", "--mode=updates"]))
    return "ok", _("Software is up to date"), None


def check_firmware():
    if not shutil.which("fwupdmgr"):
        return "ok", _("Firmware updates aren't supported here"), None
    out = _run(["fwupdmgr", "get-updates", "--json", "--no-unreported-check"], timeout=30)
    try:
        devices = json.loads(out).get("Devices", [])
    except ValueError:
        devices = []
    devices = [d for d in devices if d.get("Releases")]
    if devices:
        names = ", ".join(d.get("Name", "?") for d in devices[:3])
        return "warn", _("Firmware updates for {names}").format(names=names), \
            (_("Open Firmware"), _open(["gnome-firmware"]))
    return "ok", _("Firmware is up to date"), None


def check_services():
    out = _run(["systemctl", "--failed", "--plain", "--no-legend"])
    failed = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    if failed:
        return "warn", _("Stopped with an error: {names}").format(names=", ".join(failed[:4])), \
            (_("Open Logs"), _open(["gnome-logs"]))
    return "ok", _("All system services are running"), None


def check_drivers():
    if not shutil.which("nvidia-detect"):
        return "ok", _("No extra drivers needed"), None
    out = _run(["nvidia-detect"])
    if "It is recommended to install" in out:
        pkg = out.split("It is recommended to install the")[-1].split("package")[0].strip()
        if _run(["dpkg-query", "-W", "-f=${Status}", pkg]).startswith("install ok"):
            return "ok", _("The NVIDIA driver is installed"), None
        return "warn", _("An NVIDIA graphics card could use its own driver ({pkg})").format(
            pkg=pkg), (_("Additional Drivers"), _open(["aurora-settings", "--page", "updates"]))
    return "ok", _("No extra drivers needed"), None


def check_firewall():
    try:
        with open("/etc/ufw/ufw.conf") as f:
            on = "ENABLED=yes" in f.read()
    except OSError:
        on = False
    if on:
        return "ok", _("The firewall is on"), None
    return "warn", _("The firewall is off"), \
        (_("Privacy & Security"), _open(["aurora-settings", "--page", "privacy"]))


def check_snapshots():
    btrfs = _run(["findmnt", "-no", "FSTYPE", "/"]).strip() == "btrfs"
    if not btrfs:
        return "ok", _("Snapshots need btrfs; this system uses another file system"), None
    if not os.path.exists("/etc/timeshift/timeshift.json"):
        return "warn", _("Automatic snapshots aren't set up"), \
            (_("Open Timeshift"), _open(["timeshift-launcher"]))
    if os.path.exists("/etc/aurora/snapshots-disabled"):
        return "warn", _("Snapshots before updates are turned off"), \
            (_("Software Updates"), _open(["aurora-settings", "--page", "updates"]))
    return "ok", _("A snapshot is taken before every update"), None


def check_battery():
    out = _run(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"])
    for line in out.splitlines():
        k, sep, v = line.strip().partition(":")
        if sep and k.strip() == "capacity":
            try:
                pct = float(v.strip().rstrip("%"))
            except ValueError:
                return None
            text = _("The battery holds {pct:.0f}% of its original charge").format(pct=pct)
            if pct < 60:
                return "warn", text + " " + _("(consider replacing it)"), None
            return "ok", text, None
    return None


def check_memory():
    try:
        with open("/proc/meminfo") as f:
            info = {ln.split(":")[0]: int(ln.split()[1]) for ln in f if ":" in ln}
    except (OSError, ValueError, IndexError):
        return None
    avail = info.get("MemAvailable", 0) / max(1, info.get("MemTotal", 1))
    text = _("{free} of {total} free").format(free=GLib.format_size(info.get("MemAvailable", 0) * 1024),
                                              total=GLib.format_size(info.get("MemTotal", 0) * 1024))
    if avail < 0.08:
        return "warn", text, (_("See What Uses Memory"), _open(["gnome-system-monitor", "-p"]))
    return "ok", text, None


CHECKS = [
    (_("Disk space"), "drive-harddisk-symbolic", check_disk_space),
    (_("Disk health"), "drive-harddisk-system-symbolic", check_disk_health),
    (_("Software updates"), "software-update-available-symbolic", check_updates),
    (_("Firmware"), "application-x-firmware-symbolic", check_firmware),
    (_("System services"), "system-run-symbolic", check_services),
    (_("Graphics drivers"), "video-display-symbolic", check_drivers),
    (_("Firewall"), "security-high-symbolic", check_firewall),
    (_("System snapshots"), "document-open-recent-symbolic", check_snapshots),
    (_("Battery"), "battery-good-symbolic", check_battery),
    (_("Memory"), "memory-symbolic", check_memory),
]


def format_report(results):
    """A concise, pasteable report with no command output or account secrets."""
    marks = {"ok": "✓", "warn": "⚠", "bad": "✕"}
    lines = [_("Aurora Doctor")]
    for title, _icon, (status, summary, _fix) in results:
        lines.append(f"{marks[status]} {title}: {summary}")
    return "\n".join(lines)


class Health(Page):
    page_id = "health"
    title = _("System Health")
    icon_name = "security-high-symbolic"

    def build(self):
        self.summary = self.group(_("Aurora Doctor"),
                                  _("Checks your computer for common problems. Nothing is "
                                    "changed without you clicking."))
        self.headline = Adw.ActionRow(title=_("Checking…"))
        self.summary.add(self.headline)
        again = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER,
                           css_classes=["flat"], tooltip_text=_("Check Again"))
        again.connect("clicked", lambda *_: self.run_checks())
        self.headline.add_suffix(again)
        self.copy_report = Gtk.Button(icon_name="edit-copy-symbolic",
                                      valign=Gtk.Align.CENTER, sensitive=False,
                                      css_classes=["flat"], tooltip_text=_("Copy report"))
        self.copy_report.connect("clicked", self._copy_report)
        self.headline.add_suffix(self.copy_report)
        self.list = self.group()
        self.rows = []
        self.report = ""
        diagnostic = self.group(_("Guided Diagnostics"),
                                _("Choose a problem, review the report, then save it yourself."))
        create = Adw.ButtonRow(title=_("Create Diagnostic Report…"))
        create.connect("activated", lambda *_: self._diagnostic_dialog())
        diagnostic.add(create)
        self.run_checks()

    def _diagnostic_dialog(self):
        dialog = Adw.AlertDialog(heading=_("Guided Diagnostics"),
                                 body=_("No report is uploaded automatically."))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        categories = ("install", "boot", "apps")
        issue = Adw.ComboRow(title=_("Problem"), model=Gtk.StringList.new(
            [_ ("Installation"), _("Startup or login"), _("Applications")]))
        details = Adw.SwitchRow(title=_("Include detailed logs"),
                                subtitle=_("Logs may contain personal information. Review "
                                           "the report before sharing it."))
        box.append(issue)
        box.append(details)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("create", _("Create Report"))
        dialog.connect("response", lambda _d, response: self._create_report(
            categories[issue.get_selected()], details.get_active())
            if response == "create" else None)
        dialog.present(self.get_root())

    def _create_report(self, category, detailed):
        from aurora import diagnostics
        toast(self, _("Collecting diagnostics…"))

        def work():
            report = diagnostics.collect(category, detailed)
            GLib.idle_add(self._preview_report, report)
        threading.Thread(target=work, daemon=True).start()

    def _preview_report(self, report):
        dialog = Adw.AlertDialog(heading=_("Review Diagnostic Report"),
                                 body=_("Nothing is sent automatically. Remove anything "
                                        "you do not want to share."))
        view = Gtk.TextView(editable=True, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                            top_margin=8, bottom_margin=8, left_margin=8, right_margin=8)
        view.get_buffer().set_text(report)
        scroll = Gtk.ScrolledWindow(child=view, min_content_width=650,
                                    min_content_height=360)
        dialog.set_extra_child(scroll)
        dialog.add_response("close", _("Close"))
        dialog.add_response("save", _("Save Report…"))
        dialog.connect("response", lambda _d, response: self._save_report(view)
                       if response == "save" else None)
        dialog.present(self.get_root())
        return False

    def _save_report(self, view):
        buf = view.get_buffer()
        report = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        dialog = Gtk.FileDialog(title=_("Save Diagnostic Report"),
                                initial_name="aurora-diagnostics.txt")

        def selected(d, result):
            try:
                target = d.save_finish(result)
                target.replace_contents(report.encode("utf-8"), None, True,
                                        Gio.FileCreateFlags.NONE, None)
                toast(self, _("Diagnostic report saved"))
            except GLib.Error as err:
                toast(self, str(err))
        dialog.save(self.get_root(), None, selected)

    def _copy_report(self, *_):
        if self.report:
            Gdk.Display.get_default().get_clipboard().set(self.report)
            toast(self, _("Report copied"))

    def run_checks(self):
        self.report = ""
        self.copy_report.set_sensitive(False)
        for row in self.rows:
            self.list.remove(row)
        self.rows = []
        self.headline.set_title(_("Checking…"))
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        results = []
        for title, icon, fn in CHECKS:
            try:
                r = fn()
            except Exception as e:  # noqa: BLE001 - one broken check must not hide the rest
                r = ("warn", str(e), None)
            if r is not None:
                results.append((title, icon, r))
        GLib.idle_add(self._show, results)

    def _show(self, results):
        self.report = format_report(results)
        self.copy_report.set_sensitive(bool(results))
        bad = sum(1 for *_x, (st, _s, _f) in results if st != "ok")
        self.headline.set_title(_("Everything looks good") if not bad else
                                ngettext("{n} thing needs attention", "{n} things need attention",
                                         bad).format(n=bad))
        order = {"bad": 0, "warn": 1, "ok": 2}
        for title, icon, (status, text, fix) in sorted(results, key=lambda r: order[r[2][0]]):
            row = Adw.ActionRow(title=title, subtitle=text, subtitle_lines=3)
            row.add_prefix(Gtk.Image(icon_name=icon))
            name, cls = ICONS[status]
            row.add_suffix(Gtk.Image(icon_name=name, css_classes=[cls]))
            if fix:
                label, fn = fix
                b = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
                b.connect("clicked", lambda *_x, f=fn: f())
                row.add_suffix(b)
            self.list.add(row)
            self.rows.append(row)
        return False
