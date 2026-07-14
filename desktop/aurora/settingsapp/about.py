"""About: system information and hostname."""

import os
import platform
import re

from gi.repository import Adw, GLib, Gtk

from aurora import VERSION
from aurora.i18n import _
from aurora.settingsapp.util import Page, run, toast


def os_release():
    info = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    k, sep, v = line.strip().partition("=")
                    if sep:
                        info[k] = v.strip('"')
            break
    return info


def cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                    return re.sub(r"\s+", " ", name) + f" × {os.cpu_count()}"
    except OSError:
        pass
    return platform.processor() or "?"


def memory():
    try:
        with open("/proc/meminfo") as f:
            kb = int(f.readline().split()[1])
        return GLib.format_size(kb * 1024)
    except (OSError, ValueError, IndexError):
        return "?"


def disk():
    st = os.statvfs("/")
    return GLib.format_size(st.f_blocks * st.f_frsize)


def graphics():
    out = run(["lspci", "-mm"])
    for line in out.splitlines():
        if '"VGA' in line or '"3D' in line or '"Display' in line:
            parts = re.findall(r'"([^"]*)"', line)
            if len(parts) >= 3:
                return f"{parts[1]} {parts[2]}"
    return _("Unknown")


class About(Page):
    page_id = "about"
    title = _("About")
    icon_name = "help-about-symbolic"

    def build(self):
        rel = os_release()
        header = self.group()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_top=12, margin_bottom=12)
        box.append(Gtk.Image(icon_name="aurora-logo", pixel_size=128))
        box.append(Gtk.Label(label=rel.get("NAME", "Aurora OS"), css_classes=["title-1"]))
        box.append(Gtk.Label(label=rel.get("VERSION", VERSION), css_classes=["dim-label"]))
        header.add(box)

        g = self.group(_("Device"))
        self.host = Adw.EntryRow(title=_("Device name"), show_apply_button=True,
                                 text=GLib.get_host_name())
        self.host.connect("apply", self._set_hostname)
        g.add(self.host)
        for title, value in ((_("Processor"), cpu_model()), (_("Memory"), memory()),
                             (_("Graphics"), graphics()), (_("Disk capacity"), disk())):
            g.add(self._row(title, value))

        s = self.group(_("Software"))
        debian = rel.get("DEBIAN_CODENAME", "")
        for title, value in (
            (_("Operating system"), rel.get("PRETTY_NAME", "Aurora OS")),
            (_("Based on"), f"Debian {debian}" if debian else "Debian"),
            (_("Desktop"), f"Aurora Shell {VERSION} (labwc)"),
            (_("Windowing system"), "Wayland" if os.environ.get("WAYLAND_DISPLAY") else "X11"),
            (_("Kernel"), f"Linux {platform.release()}"),
        ):
            s.add(self._row(title, value))

    def _row(self, title, value):
        row = Adw.ActionRow(title=title, subtitle=value, subtitle_selectable=True)
        row.add_css_class("property")
        return row

    def _set_hostname(self, row):
        name = row.get_text().strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}", name):
            toast(self, _("Use letters, digits and hyphens only."))
            return
        try:
            run(["hostnamectl", "set-hostname", name], check=True)
            toast(self, _("Device name changed"))
        except RuntimeError as err:
            toast(self, str(err))
