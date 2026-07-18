"""Privacy & Security, Sharing, Users and Updates pages."""

import grp
import os
import pty
import pwd
import re
import select
import shutil
import socket
import subprocess
import time

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.settingsapp.util import Page, run, switch_row, toast


def admin(*args, stdin=None):
    """Run a privileged action through pkexec; returns (ok, error message)."""
    try:
        res = subprocess.run(["pkexec", "/usr/libexec/aurora-admin", *args], input=stdin,
                             capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)
    if res.returncode in (126, 127):
        return False, _("Authorization was cancelled")
    return res.returncode == 0, res.stderr.strip()


def service_active(name):
    return run(["systemctl", "is-active", name]).strip() == "active"


# --------------------------------------------------------------- privacy

class Privacy(Page):
    page_id = "privacy"
    title = _("Privacy & Security")
    icon_name = "preferences-system-privacy-symbolic"

    def build(self):
        aurora = settings.get()
        privacy = settings.get("org.gnome.desktop.privacy")

        lock = self.group(_("Screen Lock"))
        if aurora:
            lock.add(switch_row(_("Lock automatically"), aurora.get_boolean("idle-lock"),
                                lambda v: aurora.set_boolean("idle-lock", v),
                                subtitle=_("When the screen turns off or the computer sleeps")))
        lock.add(Adw.ActionRow(title=_("Lock now"), subtitle="Super + L"))

        history = self.group(_("File History"))
        if privacy:
            history.add(switch_row(_("Remember recent files"),
                                   privacy.get_boolean("remember-recent-files"),
                                   lambda v: privacy.set_boolean("remember-recent-files", v)))
        clear = Adw.ButtonRow(title=_("Clear History…"))
        clear.connect("activated", lambda *_: self._clear_history())
        history.add(clear)

        fw = self.group(_("Firewall"),
                        _("Blocks unrequested incoming connections. Outgoing traffic is not affected."))
        status = run(["systemctl", "is-enabled", "ufw"]).strip() == "enabled"
        conf_on = False
        try:
            with open("/etc/ufw/ufw.conf") as f:
                conf_on = "ENABLED=yes" in f.read()
        except OSError:
            pass
        fw.add(switch_row(_("Firewall"), status and conf_on, self._set_firewall))

        trash = self.group(_("Trash"))
        if privacy:
            trash.add(switch_row(_("Automatically empty Trash"),
                                 privacy.get_boolean("remove-old-trash-files"),
                                 lambda v: privacy.set_boolean("remove-old-trash-files", v),
                                 subtitle=_("Items older than 30 days")))

    def _clear_history(self):
        Gtk.RecentManager.get_default().purge_items()
        toast(self, _("History cleared"))

    def _set_firewall(self, on):
        ok, err = admin("firewall", "on" if on else "off")
        toast(self, (_("Firewall enabled") if on else _("Firewall disabled")) if ok else err)


# --------------------------------------------------------------- sharing

class Sharing(Page):
    page_id = "sharing"
    title = _("Sharing")
    icon_name = "preferences-system-sharing-symbolic"

    def build(self):
        g = self.group(_("Remote Login"),
                       _("Allow connecting to this computer with SSH."))
        installed = shutil.which("sshd") or os.path.exists("/usr/sbin/sshd")
        if not installed:
            g.add(Adw.ActionRow(title=_("OpenSSH server is not installed")))
            return
        on = service_active("ssh")
        g.add(switch_row(_("Secure Shell (SSH)"), on, self._set_ssh))
        host = GLib.get_host_name()
        addr = self._address()
        user = GLib.get_user_name()
        g.add(Adw.ActionRow(title=_("Connect with"),
                            subtitle=f"ssh {user}@{addr or host + '.local'}",
                            subtitle_selectable=True))

    def _address(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("192.0.2.1", 9))  # no packet is sent for UDP connect
            return s.getsockname()[0]
        except OSError:
            return ""

    def _set_ssh(self, on):
        ok, err = admin("ssh", "on" if on else "off")
        toast(self, (_("SSH enabled") if on else _("SSH disabled")) if ok else err)


# ----------------------------------------------------------------- users

def human_users():
    return [p for p in pwd.getpwall()
            if 1000 <= p.pw_uid < 60000 and not p.pw_shell.endswith(("nologin", "false"))]


def is_admin(user):
    try:
        return user in grp.getgrnam("sudo").gr_mem
    except KeyError:
        return False


def change_password(old, new):
    """Run passwd on a pseudo-terminal; returns (ok, message)."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["LC_ALL"] = "C"
        os.execvp("passwd", ["passwd"])
    out = b""
    answers = [old, new, new]
    deadline = time.time() + 20
    while time.time() < deadline:
        r, _w, _x = select.select([fd], [], [], 0.5)
        if not r:
            continue
        try:
            chunk = os.read(fd, 1024)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if re.search(rb"(?i)password:\s*$", out) and answers:
            os.write(fd, (answers.pop(0) + "\n").encode())
            out += b"\n"
    _pid, status = os.waitpid(pid, 0)
    text = out.decode(errors="replace")
    ok = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
    lines = [ln.strip() for ln in text.splitlines()
             if ln.strip() and "password" not in ln.lower()[:20]]
    return ok, (lines[-1] if lines else "")


class Users(Page):
    page_id = "users"
    title = _("Users")
    icon_name = "system-users-symbolic"

    def build(self):
        me = pwd.getpwuid(os.getuid())
        self.me = me
        you = self.group(_("Your Account"))
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_bottom=12)
        self.avatar = Adw.Avatar(size=96, show_initials=True,
                                 text=me.pw_gecos.split(",")[0] or me.pw_name)
        icon = f"/var/lib/AccountsService/icons/{me.pw_name}"
        if os.path.exists(icon):
            self.avatar.set_custom_image(Gdk.Texture.new_from_filename(icon))
        change = Gtk.Button(label=_("Change Picture…"), halign=Gtk.Align.CENTER,
                            css_classes=["flat"])
        change.connect("clicked", lambda *_: self._pick_avatar())
        header.append(self.avatar)
        header.append(change)
        you.add(header)

        name = Adw.EntryRow(title=_("Full name"), text=me.pw_gecos.split(",")[0],
                            show_apply_button=True)
        name.connect("apply", lambda r: self._accounts_call("SetRealName",
                                                            GLib.Variant("(s)", (r.get_text(),))))
        you.add(name)
        you.add(Adw.ActionRow(title=_("Username"), subtitle=me.pw_name))
        pw = Adw.ButtonRow(title=_("Change Password…"))
        pw.connect("activated", lambda *_: self._password_dialog())
        you.add(pw)

        login = self.group(_("Login"))
        autologin = self._current_autologin()
        login.add(switch_row(_("Log in automatically"), autologin == me.pw_name,
                             lambda v: self._set_autologin(v),
                             subtitle=_("Skip the login screen when the computer starts")))

        self.others = self.group(_("Other Users"))
        add = Gtk.Button(icon_name="list-add-symbolic", css_classes=["flat"],
                         tooltip_text=_("Add User"))
        add.connect("clicked", lambda *_: self._add_user_dialog())
        self.others.set_header_suffix(add)
        self._rows = []
        self._fill_users()

    # --- AccountsService ---

    def _accounts_user_path(self):
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        res = bus.call_sync("org.freedesktop.Accounts", "/org/freedesktop/Accounts",
                            "org.freedesktop.Accounts", "FindUserByName",
                            GLib.Variant("(s)", (self.me.pw_name,)), None,
                            Gio.DBusCallFlags.NONE, -1, None)
        return bus, res.unpack()[0]

    def _accounts_call(self, method, params):
        try:
            bus, path = self._accounts_user_path()
            bus.call_sync("org.freedesktop.Accounts", path, "org.freedesktop.Accounts.User",
                          method, params, None, Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION,
                          -1, None)
            toast(self, _("Saved"))
            return True
        except GLib.Error as err:
            toast(self, err.message.split(":")[-1].strip())
            return False

    def _pick_avatar(self):
        dialog = Gtk.FileDialog(title=_("Choose a Picture"))
        filt = Gtk.FileFilter(name=_("Images"))
        filt.add_mime_type("image/*")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dialog.set_filters(store)

        def done(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            if self._accounts_call("SetIconFile", GLib.Variant("(s)", (f.get_path(),))):
                self.avatar.set_custom_image(Gdk.Texture.new_from_filename(f.get_path()))
        dialog.open(self.get_root(), None, done)

    # --- password ---

    def _password_dialog(self):
        dialog = Adw.AlertDialog(heading=_("Change Password"))
        box = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        old = Adw.PasswordEntryRow(title=_("Current password"))
        new = Adw.PasswordEntryRow(title=_("New password"))
        again = Adw.PasswordEntryRow(title=_("Confirm new password"))
        for r in (old, new, again):
            box.append(r)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("change", _("Change"))
        dialog.set_response_appearance("change", Adw.ResponseAppearance.SUGGESTED)

        def response(_d, resp):
            if resp != "change":
                return
            if new.get_text() != again.get_text() or not new.get_text():
                toast(self, _("The new passwords do not match"))
                return
            ok, msg = change_password(old.get_text(), new.get_text())
            toast(self, _("Password changed") if ok else (msg or _("Could not change password")))
        dialog.connect("response", response)
        dialog.present(self.get_root())

    # --- autologin ---

    def _current_autologin(self):
        try:
            with open("/etc/greetd/config.toml") as f:
                text = f.read()
        except OSError:
            return None
        m = re.search(r'\[initial_session\][^\[]*?user\s*=\s*"([^"]+)"', text, re.S)
        return m.group(1) if m else None

    def _set_autologin(self, on):
        ok, err = admin("autologin", self.me.pw_name if on else "off")
        toast(self, _("Saved") if ok else err)

    # --- other users ---

    def _fill_users(self):
        for r in self._rows:
            self.others.remove(r)
        self._rows = []
        for p in human_users():
            if p.pw_uid == self.me.pw_uid:
                continue
            row = Adw.ActionRow(title=p.pw_gecos.split(",")[0] or p.pw_name,
                                subtitle=(_("Administrator") if is_admin(p.pw_name)
                                          else _("Standard")) + f" · {p.pw_name}")
            row.add_prefix(Adw.Avatar(size=32, text=p.pw_gecos or p.pw_name, show_initials=True))
            rm = Gtk.Button(icon_name="user-trash-symbolic", css_classes=["flat"],
                            valign=Gtk.Align.CENTER, tooltip_text=_("Remove User"))
            rm.connect("clicked", lambda _b, u=p.pw_name: self._delete_user(u))
            row.add_suffix(rm)
            self.others.add(row)
            self._rows.append(row)
        if not self._rows:
            row = Adw.ActionRow(title=_("No other users"))
            self.others.add(row)
            self._rows.append(row)

    def _add_user_dialog(self):
        dialog = Adw.AlertDialog(heading=_("Add User"))
        box = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        full = Adw.EntryRow(title=_("Full name"))
        user = Adw.EntryRow(title=_("Username"))
        password = Adw.PasswordEntryRow(title=_("Password"))
        is_adm = Adw.SwitchRow(title=_("Administrator"))

        def suggest(*_a):
            base = re.sub(r"[^a-z0-9]", "", full.get_text().split(" ")[0].lower())
            user.set_text(base)
        full.connect("changed", suggest)
        for r in (full, user, password, is_adm):
            box.append(r)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def response(_d, resp):
            if resp != "add":
                return
            ok, err = admin("add-user", user.get_text(), full.get_text(),
                            "yes" if is_adm.get_active() else "no",
                            stdin=password.get_text() + "\n")
            toast(self, _("User added") if ok else (err or _("Could not add user")))
            self._fill_users()
        dialog.connect("response", response)
        dialog.present(self.get_root())

    def _delete_user(self, name):
        dialog = Adw.AlertDialog(heading=_("Remove {user}?").format(user=name),
                                 body=_("Their home folder and all their files will be deleted."))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def response(_d, resp):
            if resp == "remove":
                ok, err = admin("delete-user", name)
                toast(self, _("User removed") if ok else err)
                self._fill_users()
        dialog.connect("response", response)
        dialog.present(self.get_root())


# --------------------------------------------------------------- updates

class Updates(Page):
    page_id = "updates"
    title = _("Software Updates")
    icon_name = "software-update-available-symbolic"

    def build(self):
        g = self.group(_("Updates"), _("Aurora keeps itself secure by installing security "
                                       "updates automatically in the background."))
        auto = False
        try:
            with open("/etc/apt/apt.conf.d/20auto-upgrades") as f:
                auto = 'Unattended-Upgrade "1"' in f.read()
        except OSError:
            pass
        g.add(switch_row(_("Install security updates automatically"), auto,
                         lambda v: self._set_auto(v)))
        self.status = Adw.ActionRow(title=_("Available updates"), subtitle=_("Checking…"))
        g.add(self.status)
        open_sw = Adw.ButtonRow(title=_("Open App Center to Update…"))
        open_sw.connect("activated", lambda *_: apps.spawn(["gnome-software", "--mode=updates"]))
        g.add(open_sw)

        snaps = self.group(_("System Snapshots"),
                           _("Take a snapshot before big changes and roll back if something breaks."))
        ts = Adw.ButtonRow(title=_("Open Timeshift…"))
        ts.connect("activated", lambda *_: apps.spawn(["timeshift-launcher"]))
        snaps.add(ts)
        GLib.idle_add(self._check)

    def _check(self):
        out = run(["apt", "list", "--upgradable"])
        n = len([ln for ln in out.splitlines() if "/" in ln])
        self.status.set_subtitle(_("Your system is up to date") if n == 0 else
                                 _("{n} updates available").format(n=n))
        return GLib.SOURCE_REMOVE

    def _set_auto(self, on):
        ok, err = admin("auto-updates", "on" if on else "off")
        toast(self, _("Saved") if ok else err)
