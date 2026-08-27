"""Aurora Greeter: graphical login for greetd, run inside a kiosk labwc."""

import configparser
import glob
import os
import pwd
import shlex
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from aurora import data_path  # noqa: E402
from aurora.greeter.greetd import Greetd, GreetdError  # noqa: E402
from aurora.i18n import _  # noqa: E402

WALLPAPER = "/usr/share/backgrounds/aurora/aurora-dawn.png"


def greeter_wallpaper():
    """The dynamic landscape for this time of day, like the desktop default."""
    from aurora import sun
    dynamic = f"/usr/share/backgrounds/aurora/aurora-dynamic-{sun.phase()}.png"
    for path in (dynamic, WALLPAPER):
        if os.path.exists(path):
            return path
    return None
AVATAR_DIR = "/var/lib/AccountsService/icons"

CSS = """
window.greeter { background: #0d0a14; color: #f6f1ff; }
.greeter-scrim {
  background-image: linear-gradient(90deg, rgba(10,8,20,0.48), rgba(10,8,20,0.16) 55%, rgba(10,8,20,0.4));
}
.greeter-card {
  background-color: rgba(24, 19, 37, 0.9);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 30px;
  padding: 32px 38px;
  box-shadow: 0 18px 56px rgba(0,0,0,0.5);
  color: #f6f1ff;
}
.greeter-card.error-state { border-color: #ff829e; }
.greeter-brand { font-size: 11pt; font-weight: 800; letter-spacing: 3px; color: #ffc9db; }
.greeter-clock { font-size: 64pt; font-weight: 300; color: #ffffff; }
.greeter-date { font-size: 14pt; color: rgba(250,246,255,0.86); }
.greeter-error {
  background: rgba(214, 49, 88, 0.23); border: 1px solid rgba(255, 120, 151, 0.55);
  border-radius: 12px; color: #ffcfda; padding: 10px 12px;
}
.greeter-card entry, .greeter-card dropdown { min-height: 42px; }
.greeter-card button.suggested-action { min-height: 42px; }
.greeter-power button { color: #f2eefa; }
"""


def login_users():
    users = []
    for p in pwd.getpwall():
        if 1000 <= p.pw_uid < 60000 and not p.pw_shell.endswith(("nologin", "false")):
            users.append(p)
    return sorted(users, key=lambda p: p.pw_name)


def sessions():
    found = []
    for path in sorted(glob.glob("/usr/share/wayland-sessions/*.desktop")):
        cp = configparser.ConfigParser(interpolation=None)
        try:
            cp.read(path)
            entry = cp["Desktop Entry"]
            if entry.get("Hidden", "false") == "true":
                continue
            found.append((entry.get("Name", os.path.basename(path)), entry["Exec"]))
        except (KeyError, configparser.Error):
            continue
    found.sort(key=lambda s: (s[1] != "aurora-session", s[0]))
    return found or [("Aurora", "aurora-session")]


class Greeter(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, css_classes=["greeter"])
        self.users = login_users()
        self.sessions = sessions()
        self.busy = False

        overlay = Gtk.Overlay()
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, hexpand=True, vexpand=True)
        wallpaper = greeter_wallpaper()
        if wallpaper:
            pic.set_file(Gio.File.new_for_path(wallpaper))
        overlay.set_child(pic)
        scrim = Gtk.Box(css_classes=["greeter-scrim"], hexpand=True, vexpand=True)
        overlay.add_overlay(scrim)

        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                         halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        column.append(Gtk.Label(label="AURORA OS", css_classes=["greeter-brand"]))
        self.clock = Gtk.Label(css_classes=["greeter-clock"])
        self.date = Gtk.Label(css_classes=["greeter-date"])
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        clock_box.append(self.clock)
        clock_box.append(self.date)
        column.append(clock_box)

        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                            css_classes=["greeter-card"])
        card = self.card
        card.set_size_request(380, -1)
        card.append(Gtk.Label(label=_("Welcome to Aurora OS"),
                              css_classes=["title-3"], halign=Gtk.Align.CENTER))
        self.avatar = Adw.Avatar(size=96, show_initials=True)
        card.append(self.avatar)

        names = [u.pw_gecos.split(",")[0] or u.pw_name for u in self.users] + [_("Other…")]
        self.user_drop = Gtk.DropDown.new_from_strings(names)
        self.user_drop.connect("notify::selected", lambda *_: self._on_user())
        card.append(self.user_drop)
        self.username = Gtk.Entry(placeholder_text=_("Username"), visible=False)
        card.append(self.username)

        self.password = Gtk.PasswordEntry(placeholder_text=_("Password"), show_peek_icon=True)
        self.password.connect("activate", lambda *_: self.login())
        card.append(self.password)

        self.error = Gtk.Label(css_classes=["greeter-error"], wrap=True)
        self.error.set_accessible_role(Gtk.AccessibleRole.ALERT)
        self.error_revealer = Gtk.Revealer(child=self.error,
                                            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                            transition_duration=220)
        card.append(self.error_revealer)

        self.spinner = Gtk.Spinner(halign=Gtk.Align.CENTER, visible=False)
        card.append(self.spinner)

        bottom = Gtk.Box(spacing=8)
        self.session_drop = Gtk.DropDown.new_from_strings([s[0] for s in self.sessions])
        self.session_drop.set_visible(len(self.sessions) > 1)
        bottom.append(self.session_drop)
        self.login_btn = Gtk.Button(label=_("Log In"), hexpand=True,
                                    css_classes=["suggested-action", "pill"])
        self.login_btn.connect("clicked", lambda *_: self.login())
        bottom.append(self.login_btn)
        card.append(bottom)
        column.append(card)
        overlay.add_overlay(column)

        power = Gtk.Box(spacing=8, halign=Gtk.Align.END, valign=Gtk.Align.END,
                        margin_end=24, margin_bottom=24, css_classes=["greeter-power"])
        for icon, tip, method in (("system-reboot-symbolic", _("Restart"), "Reboot"),
                                  ("system-shutdown-symbolic", _("Power Off"), "PowerOff")):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip, css_classes=["circular", "osd"])
            b.connect("clicked", lambda _b, m=method: self._power(m))
            power.append(b)
        overlay.add_overlay(power)

        self.set_content(overlay)
        self._tick()
        GLib.timeout_add_seconds(1, self._tick)
        self._on_user()
        self._animate_entry()

    def _animations_enabled(self):
        return bool(Gtk.Settings.get_default().get_property("gtk-enable-animations"))

    def _animate_entry(self):
        if not self._animations_enabled():
            return
        self.card.set_opacity(0.0)
        steps = iter(range(1, 11))

        def fade():
            step = next(steps, None)
            if step is None:
                return GLib.SOURCE_REMOVE
            self.card.set_opacity(step / 10)
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add(22, fade)

    def _shake_error(self):
        self.card.add_css_class("error-state")
        if not self._animations_enabled():
            GLib.timeout_add(600, self._clear_error_state)
            return
        offsets = iter((0, -7, 7, -5, 5, -2, 2, 0))

        def shake():
            offset = next(offsets, None)
            if offset is None:
                self._clear_error_state()
                return GLib.SOURCE_REMOVE
            self.card.set_margin_start(max(0, offset))
            self.card.set_margin_end(max(0, -offset))
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add(35, shake)

    def _clear_error_state(self):
        self.card.set_margin_start(0)
        self.card.set_margin_end(0)
        self.card.remove_css_class("error-state")
        return GLib.SOURCE_REMOVE

    def _tick(self):
        now = GLib.DateTime.new_now_local()
        self.clock.set_label(now.format("%H:%M"))
        self.date.set_label(now.format("%A, %e %B"))
        return GLib.SOURCE_CONTINUE

    def _selected_user(self):
        i = self.user_drop.get_selected()
        if i < len(self.users):
            return self.users[i]
        return None

    def _on_user(self):
        user = self._selected_user()
        self.username.set_visible(user is None)
        if user is None:
            self.avatar.set_text("")
            self.avatar.set_custom_image(None)
            self.username.grab_focus()
            return
        self.avatar.set_text(user.pw_gecos.split(",")[0] or user.pw_name)
        icon = os.path.join(AVATAR_DIR, user.pw_name)
        if os.path.exists(icon):
            self.avatar.set_custom_image(Gdk.Texture.new_from_filename(icon))
        else:
            self.avatar.set_custom_image(None)
        self.password.grab_focus()

    def _show_error(self, text):
        self.error.set_label(text)
        self.error_revealer.set_reveal_child(bool(text))
        if text:
            self._shake_error()

    def login(self):
        if self.busy:
            return
        user = self._selected_user()
        name = user.pw_name if user else self.username.get_text().strip()
        if not name:
            return
        self.busy = True
        self.login_btn.set_sensitive(False)
        self._show_error("")
        self.spinner.set_visible(True)
        self.spinner.start()
        cmd = self.sessions[self.session_drop.get_selected()][1]
        threading.Thread(target=self._authenticate,
                         args=(name, self.password.get_text(), cmd), daemon=True).start()

    def _authenticate(self, name, password, cmd):
        """Runs in a thread: drive the greetd conversation."""
        try:
            g = Greetd()
            resp = g.create_session(name)
            answered = False
            while resp.get("type") == "auth_message":
                kind = resp.get("auth_message_type")
                if kind in ("secret", "visible"):
                    if answered:
                        # A second prompt (e.g. expired password) is not supported here.
                        g.cancel()
                        raise GreetdError(resp.get("auth_message", ""))
                    answered = True
                    resp = g.respond(password)
                else:
                    msg = resp.get("auth_message", "")
                    if kind == "error" and msg:
                        GLib.idle_add(self._show_error, msg)
                    resp = g.respond(None)
            if resp.get("type") == "error":
                g.cancel()
                raise GreetdError(resp.get("description") or _("Login failed"))
            resp = g.start_session(shlex.split(cmd))
            if resp.get("type") == "error":
                raise GreetdError(resp.get("description") or _("Could not start session"))
            GLib.idle_add(self._done)
        except (GreetdError, OSError) as err:
            msg = str(err)
            if "auth" in msg.lower() or not msg:
                msg = _("Wrong password. Please try again.")
            GLib.idle_add(self._failed, msg)

    def _failed(self, msg):
        self.busy = False
        self.login_btn.set_sensitive(True)
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.password.set_text("")
        self.password.grab_focus()
        self._show_error(msg)

    def _done(self):
        # greetd starts the session once the greeter's compositor exits.
        subprocess.Popen(["labwc", "--exit"])
        self.get_application().quit()

    def _power(self, method):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            bus.call_sync("org.freedesktop.login1", "/org/freedesktop/login1",
                          "org.freedesktop.login1.Manager", method,
                          GLib.Variant("(b)", (True,)), None, Gio.DBusCallFlags.NONE, -1, None)
        except GLib.Error as err:
            self._show_error(err.message)


class GreeterApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.Greeter")

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = Greeter(self)
        win.fullscreen()
        win.present()


def main():
    return GreeterApp().run(sys.argv)
