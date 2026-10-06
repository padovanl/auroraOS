"""Aurora Dev Hub and Game Hub: one-click installs from official sources.

Both are the same window with a different catalog: Dev Hub for developer
toolchains (recipes.py), Game Hub for games, Windows and Android apps (games.py).
"""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gtk, Pango, Vte  # noqa: E402

from aurora import VERSION, activities, projectworkspaces  # noqa: E402
from aurora.devhub.recipes import CATEGORIES, RECIPES  # noqa: E402
from aurora.i18n import N_, _  # noqa: E402

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


def install_wrapper(path):
    """Run and remove a recipe while preserving its exit code."""
    quoted_path = shlex.quote(path)
    return (f"bash {quoted_path}; status=$?; rm -f {quoted_path}; "
            "[ $status -ne 0 ] && echo && echo '✖ Installation failed (see above).'; "
            "exit $status")


INSTALL_SCRIPT_HEADER = "#!/bin/bash\nset -euo pipefail\n"


class InstallWindow(Adw.Window):
    """A friendly, in-app terminal for recipes that may ask for sudo."""

    def __init__(self, parent, card, path, activity_id):
        recipe = card.recipe
        super().__init__(transient_for=parent, modal=True,
                         title=_("Installing {name}").format(name=_(recipe["name"])),
                         default_width=760, default_height=500)
        self.parent_window = parent
        self.card = card
        self.recipe = recipe
        self.activity_id = activity_id
        self.recipe_path = path
        self.running = True

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        self.status = Gtk.Label(label=_("Downloading and installing…"), xalign=0,
                                css_classes=["title-4"])
        box.append(self.status)
        box.append(Gtk.Label(
            label=_("If asked, type your administrator password below. The log stays "
                    "visible so failures can be diagnosed."),
            xalign=0, wrap=True, css_classes=["dim-label"]))
        self.progress = Gtk.ProgressBar(show_text=False)
        box.append(self.progress)
        self.terminal = Vte.Terminal(vexpand=True, hexpand=True)
        self.terminal.set_scrollback_lines(5000)
        self.terminal.set_allow_hyperlink(True)
        frame = Gtk.Frame(child=self.terminal, css_classes=["card"])
        box.append(frame)
        view.set_content(box)
        self.set_content(view)

        self.terminal.connect("child-exited", self._finished)
        self.connect("close-request", self._close_requested)
        self._pulse_id = GLib.timeout_add(120, self._pulse)
        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT, GLib.get_home_dir(),
            ["/bin/bash", "-c", install_wrapper(path)], None,
            GLib.SpawnFlags.DEFAULT, None, None, -1, None,
            self._spawned, None)

    def _spawned(self, _terminal, _pid, error, *_data):
        if error is None:
            return
        try:
            os.remove(self.recipe_path)
        except FileNotFoundError:
            pass
        self._complete(False, error.message)

    def _pulse(self):
        if not self.running:
            return GLib.SOURCE_REMOVE
        self.progress.pulse()
        return GLib.SOURCE_CONTINUE

    def _close_requested(self, _window):
        if self.running:
            self.status.set_label(_("Installation is still running"))
            return True
        return False

    def _finished(self, _terminal, status):
        success = status == 0 and is_installed(self.recipe)
        self._complete(success)

    def _complete(self, success, detail=""):
        if not self.running:
            return
        self.running = False
        # A recipe can install its executable and still fail during a later
        # setup step. Keep the card retryable until the whole recipe succeeds.
        self.card.install_failed = not success
        activities.update(self.activity_id, status="finished" if success else "failed",
                          progress=1.0 if success else 0,
                          error="" if success else detail or _("Installation failed"))
        self.card.refresh()
        self.progress.set_fraction(1.0)
        self.progress.add_css_class("success" if success else "error")
        if success:
            self.status.set_label(_("{name} installed").format(name=_(self.recipe["name"])))
            self.parent_window.toasts.add_toast(Adw.Toast(
                title=_("{name} installed").format(name=_(self.recipe["name"]))))
        else:
            self.status.set_label(_("Installation failed — review the log below"))
            self.parent_window.toasts.add_toast(Adw.Toast(title=_("Installation failed")))


class Card(Gtk.Box):
    def __init__(self, win, recipe):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                         css_classes=["card", "devhub-card"])
        self.win = win
        self.recipe = recipe
        self.install_failed = False
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
        done = is_installed(self.recipe) and not self.install_failed
        self.button.set_label(_("Installed") if done else _("Install"))
        self.button.set_sensitive(not done)
        for c in ("suggested-action",):
            (self.button.remove_css_class if done else self.button.add_css_class)(c)


DEV_HUB = {
    "id": "org.aurora.DevHub", "title": N_("Dev Hub"), "search": N_("Search tools"),
    "hero": N_("Your toolbox, one click away"),
    "text": N_("Everything installs from its official source, so you always get the latest "
               "release. Git, Python, Node.js, Docker, Podman and more are already on your "
               "system."),
    "categories": CATEGORIES, "recipes": RECIPES,
}


class DevHub(Adw.ApplicationWindow):
    def __init__(self, app, hub=DEV_HUB):
        super().__init__(application=app, title=_(hub["title"]), default_width=1100,
                         default_height=760)
        self.cards = []
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.search = Gtk.SearchEntry(placeholder_text=_(hub["search"]), width_chars=28)
        self.search.connect("search-changed", lambda *_: self._filter())
        header.set_title_widget(self.search)
        view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22,
                          margin_top=18, margin_bottom=24, margin_start=24, margin_end=24)
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["devhub-hero"])
        hero.append(Gtk.Label(label=_(hub["hero"]), xalign=0, css_classes=["title-1"]))
        hero.append(Gtk.Label(label=_(hub["text"]), xalign=0, wrap=True))
        content.append(hero)
        if hub is DEV_HUB:
            self.projects_group = Adw.PreferencesGroup(
                title=_("Project Workspaces"),
                description=_("Open your editor, terminal and Files together for a project."))
            add_project = Gtk.Button(icon_name="list-add-symbolic",
                                     tooltip_text=_("Add Project"), css_classes=["flat"])
            add_project.connect("clicked", lambda *_: self._add_project())
            self.projects_group.set_header_suffix(add_project)
            content.append(self.projects_group)
            self._project_rows = []
            self._refresh_projects()

        self.sections = []
        for cat, title in hub["categories"]:
            label = Gtk.Label(label=_(title), xalign=0, css_classes=["title-3"])
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                               max_children_per_line=4, min_children_per_line=2,
                               column_spacing=14, row_spacing=14)
            for r in [r for r in hub["recipes"] if r["cat"] == cat]:
                card = Card(self, r)
                self.cards.append(card)
                flow.append(card)
            content.append(label)
            content.append(flow)
            self.sections.append((label, flow))

        self.content = content
        self.scroller = Gtk.ScrolledWindow(child=Adw.Clamp(child=content, maximum_size=1200),
                                           hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.toasts = Adw.ToastOverlay(child=self.scroller)
        view.set_content(self.toasts)

        # Categories in a sidebar: click one to jump to it.
        nav = Gtk.ListBox(css_classes=["navigation-sidebar"])
        for (cat, title), (label, _flow) in zip(hub["categories"], self.sections):
            row = Gtk.ListBoxRow(child=Gtk.Label(label=_(title), xalign=0, margin_start=6,
                                                 ellipsize=Pango.EllipsizeMode.END))
            row.target = label
            nav.append(row)
        nav.connect("row-activated", lambda _l, row: self._jump(row.target))
        side = Adw.ToolbarView()
        side.add_top_bar(Adw.HeaderBar(show_title=False))
        side.set_content(Gtk.ScrolledWindow(child=nav, hscrollbar_policy=Gtk.PolicyType.NEVER))
        split = Adw.OverlaySplitView(sidebar=side, content=view,
                                     min_sidebar_width=200, max_sidebar_width=240)
        self.set_content(split)

    def _refresh_projects(self):
        from aurora.shell.search import find_projects
        for row in self._project_rows:
            self.projects_group.remove(row)
        self._project_rows = []
        saved = projectworkspaces.load()
        paths = list(dict.fromkeys([*saved, *find_projects()]))
        for path in paths[:12]:
            if not os.path.isdir(path):
                continue
            row = Adw.ActionRow(title=os.path.basename(path), subtitle=path)
            launch = Gtk.Button(label=_("Open Workspace"), css_classes=["pill"],
                                valign=Gtk.Align.CENTER)
            launch.connect("clicked", lambda _b, p=path: projectworkspaces.open_workspace(p))
            row.add_suffix(launch)
            setup = Gtk.Button(icon_name="emblem-system-symbolic",
                               tooltip_text=_("Configure Workspace"),
                               css_classes=["flat"], valign=Gtk.Align.CENTER)
            setup.connect("clicked", lambda _b, p=path: self._configure_project(p))
            row.add_suffix(setup)
            self.projects_group.add(row)
            self._project_rows.append(row)
        if not self._project_rows:
            row = Adw.ActionRow(title=_("No projects found"),
                                subtitle=_("Add a project folder to begin."))
            self.projects_group.add(row)
            self._project_rows.append(row)

    def _add_project(self):
        dialog = Gtk.FileDialog(title=_("Choose Project Folder"))

        def chosen(d, result):
            try:
                folder = d.select_folder_finish(result)
            except GLib.Error:
                return
            path = folder.get_path()
            if path:
                projectworkspaces.configure(path)
                self._refresh_projects()
        dialog.select_folder(self, None, chosen)

    def _configure_project(self, path):
        prefs = projectworkspaces.preferences(path)
        dialog = Adw.AlertDialog(heading=_("Configure Workspace"), body=path)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        editors = ["auto", *[e for e in projectworkspaces.EDITORS[1:] if
                              shutil.which(e)]]
        editor = Adw.ComboRow(title=_("Editor"), model=Gtk.StringList.new(
            [_("Automatic") if e == "auto" else e for e in editors]))
        editor.set_selected(editors.index(prefs["editor"]) if prefs["editor"] in editors else 0)
        terminal = Adw.SwitchRow(title=_("Open Terminal"), active=prefs["terminal"])
        files = Adw.SwitchRow(title=_("Open Files"), active=prefs["files"])
        for row in (editor, terminal, files):
            box.append(row)
        layout = Gtk.Button(label=_("Save Current Window Layout"),
                            tooltip_text=_("Save positions of currently open windows for this workspace"))
        layout.connect("clicked", lambda *_: self._save_project_layout(path, dialog))
        box.append(layout)
        dialog.set_extra_child(box)
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("save", _("Save"))
        dialog.connect("response", lambda _d, response: projectworkspaces.configure(
            path, editors[editor.get_selected()], terminal.get_active(), files.get_active())
            if response == "save" else None)
        dialog.present(self)

    def _save_project_layout(self, path, dialog):
        try:
            count = projectworkspaces.capture_layout(path)
            dialog.set_body(_("Saved positions for %d windows.") % count)
        except (OSError, ValueError, ConnectionError):
            dialog.set_body(_("Window layout requires the Aurora animated session."))

    def _jump(self, label):
        ok, point = label.compute_point(self.content, Graphene.Point())
        if ok:
            self.scroller.get_vadjustment().set_value(max(0.0, point.y - 12))

    def _filter(self):
        q = self.search.get_text().lower()
        for card in self.cards:
            r = card.recipe
            match = not q or q in _(r["name"]).lower() or q in _(r["desc"]).lower()
            card.get_parent().set_visible(match)
        # Hide categories with nothing left to show.
        for label, flow in self.sections:
            child = flow.get_first_child()
            any_visible = False
            while child is not None:
                any_visible = any_visible or child.get_visible()
                child = child.get_next_sibling()
            label.set_visible(any_visible)
            flow.set_visible(any_visible)

    def install(self, card):
        r = card.recipe
        fd, path = tempfile.mkstemp(prefix=f"devhub-{r['id']}-", suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write(INSTALL_SCRIPT_HEADER)
            f.write(f"echo '▶ Installing {r['name']}'\n")
            f.write(r["script"])
            f.write("\necho\necho '✔ Done. Open a new terminal to use it.'\n")
        activity_id = activities.create(_("Installing {name}").format(name=_(r["name"])),
                                        "install", cancellable=False)
        card.button.set_label(_("Installing…"))
        card.button.set_sensitive(False)
        InstallWindow(self, card, path, activity_id).present()


class DevHubApp(Adw.Application):
    def __init__(self, hub=DEV_HUB):
        super().__init__(application_id=hub["id"])
        self.hub = hub

    def do_startup(self):
        Adw.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        (self.props.active_window or DevHub(self, self.hub)).present()


def main():
    return DevHubApp().run(sys.argv)


def main_games():
    from aurora.devhub.games import GAME_HUB
    return DevHubApp(GAME_HUB).run(sys.argv)
