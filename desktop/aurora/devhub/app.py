"""Aurora Dev Hub: one-click developer toolchains from official sources."""

import os
import subprocess
import sys
import tempfile

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from aurora import VERSION  # noqa: E402
from aurora.devhub.recipes import CATEGORIES, RECIPES  # noqa: E402
from aurora.i18n import _  # noqa: E402

CSS = """
.devhub-card { padding: 16px; border-radius: 16px; }
.devhub-card .title-4 { margin-top: 6px; }
.devhub-hero {
  background-image: linear-gradient(120deg, #a970ff, #ff6f91 60%, #ffa45c);
  border-radius: 20px; padding: 28px; color: white;
}
.devhub-hero .title-1 { color: white; }
"""


def is_installed(recipe):
    try:
        return subprocess.run(["bash", "-c", recipe["check"]], capture_output=True,
                              timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def icon_for(recipe):
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    return recipe["icon"] if theme.has_icon(recipe["icon"]) else recipe["fallback_icon"]


class Card(Gtk.Box):
    def __init__(self, win, recipe):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                         css_classes=["card", "devhub-card"])
        self.win = win
        self.recipe = recipe
        self.set_size_request(240, 190)
        self.append(Gtk.Image(icon_name=icon_for(recipe), pixel_size=48, halign=Gtk.Align.START))
        self.append(Gtk.Label(label=_(recipe["name"]), xalign=0, css_classes=["title-4"]))
        self.append(Gtk.Label(label=_(recipe["desc"]), xalign=0, wrap=True, lines=3,
                              ellipsize=3, css_classes=["dim-label"], vexpand=True,
                              valign=Gtk.Align.START, max_width_chars=28, width_chars=28))
        self.button = Gtk.Button(halign=Gtk.Align.END, css_classes=["pill"])
        self.button.connect("clicked", lambda *_: win.install(self))
        self.append(self.button)
        self.refresh()

    def refresh(self):
        done = is_installed(self.recipe)
        self.button.set_label(_("Installed") if done else _("Install"))
        self.button.set_sensitive(not done)
        for c in ("suggested-action",):
            (self.button.remove_css_class if done else self.button.add_css_class)(c)


class DevHub(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Dev Hub"), default_width=1100,
                         default_height=760)
        self.cards = []
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.search = Gtk.SearchEntry(placeholder_text=_("Search tools"), width_chars=28)
        self.search.connect("search-changed", lambda *_: self._filter())
        header.set_title_widget(self.search)
        view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22,
                          margin_top=18, margin_bottom=24, margin_start=24, margin_end=24)
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["devhub-hero"])
        hero.append(Gtk.Label(label=_("Your toolbox, one click away"), xalign=0,
                              css_classes=["title-1"]))
        hero.append(Gtk.Label(label=_("Everything installs from its official source, so you "
                                      "always get the latest release. Git, Python, Node.js, "
                                      "Docker, Podman and more are already on your system."),
                              xalign=0, wrap=True))
        content.append(hero)

        self.sections = []
        for cat, title in CATEGORIES:
            label = Gtk.Label(label=_(title), xalign=0, css_classes=["title-3"])
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                               max_children_per_line=4, min_children_per_line=2,
                               column_spacing=14, row_spacing=14)
            for r in [r for r in RECIPES if r["cat"] == cat]:
                card = Card(self, r)
                self.cards.append(card)
                flow.append(card)
            content.append(label)
            content.append(flow)
            self.sections.append((label, flow))

        self.toasts = Adw.ToastOverlay(child=Gtk.ScrolledWindow(
            child=Adw.Clamp(child=content, maximum_size=1200),
            hscrollbar_policy=Gtk.PolicyType.NEVER))
        view.set_content(self.toasts)
        self.set_content(view)

    def _filter(self):
        q = self.search.get_text().lower()
        for card in self.cards:
            r = card.recipe
            match = not q or q in _(r["name"]).lower() or q in _(r["desc"]).lower()
            card.get_parent().set_visible(match)

    def install(self, card):
        r = card.recipe
        fd, path = tempfile.mkstemp(prefix=f"devhub-{r['id']}-", suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write("#!/bin/bash\nset -e\n")
            f.write(f"echo '▶ Installing {r['name']}'\n")
            f.write(r["script"])
            f.write("\necho\necho '✔ Done. Open a new terminal to use it.'\n")
        wrapper = (f"bash {path}; status=$?; rm -f {path}; "
                   "[ $status -ne 0 ] && echo && echo '✖ Installation failed (see above).'; "
                   "echo; read -rp 'Press Enter to close…' _")
        try:
            proc = subprocess.Popen(["foot", "--title", f"Dev Hub · {r['name']}",
                                     "bash", "-c", wrapper])
        except OSError:
            proc = subprocess.Popen(["x-terminal-emulator", "-e", "bash", "-c", wrapper])
        card.button.set_label(_("Installing…"))
        card.button.set_sensitive(False)

        def poll():
            if proc.poll() is None:
                return GLib.SOURCE_CONTINUE
            card.refresh()
            if is_installed(r):
                self.toasts.add_toast(Adw.Toast(title=_("{name} installed").format(name=_(r["name"]))))
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(1000, poll)


class DevHubApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.aurora.DevHub")

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        (self.props.active_window or DevHub(self)).present()


def main():
    return DevHubApp().run(sys.argv)
