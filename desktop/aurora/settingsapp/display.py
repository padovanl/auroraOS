"""Displays: resolution, refresh rate, scale, rotation via wlr-randr.

Changes apply immediately and are saved to ~/.config/aurora/displays.sh,
which the session runs at login.
"""

import json
import os
import shlex

from gi.repository import Adw, GLib, Gtk

from aurora import compositor, config_path
from aurora.i18n import _, ngettext
from aurora.settingsapp.util import Page, combo_row, run, switch_row, toast

SCALES = [1.0, 1.25, 1.5, 1.75, 2.0]
KEEP_SECONDS = 15
TRANSFORMS = [("normal", _("Normal")), ("90", _("90° Clockwise")),
              ("180", _("Upside Down")), ("270", _("90° Counterclockwise"))]


def outputs():
    out = run(["wlr-randr", "--json"])
    try:
        return json.loads(out) if out else []
    except json.JSONDecodeError:
        return []


def previous_args(o):
    """wlr-randr arguments that put each of an output's options back as it is
    now, by option (--mode, --scale, --transform, --off)."""
    position = o.get("position") or {}
    undo = {"--pos": ["--pos", f"{position.get('x', 0)},{position.get('y', 0)}"],
            "--scale": ["--scale", str(o.get("scale", 1.0))],
            "--transform": ["--transform", o.get("transform", "normal")],
            "--off": ["--on"]}
    current = next((m for m in o.get("modes", []) if m.get("current")), None)
    if current:
        undo["--mode"] = ["--mode", f"{current['width']}x{current['height']}"
                                    f"@{current['refresh']:.3f}Hz"]
    return undo


class Displays(Page):
    page_id = "display"
    title = _("Displays")
    icon_name = "video-display-symbolic"

    def build(self):
        self._groups = []
        self._previous = {}
        self.position_controls = {}
        self.refresh()

    def refresh(self):
        for g in self._groups:
            self.remove(g)
        self._groups = []
        self.position_controls = {}
        outs = outputs()
        if not outs:
            g = self.group(_("No displays found"),
                           _("Display configuration needs a running Aurora session."))
            self._groups.append(g)
            return
        for o in outs:
            self._groups.append(self._output_group(o))

    def _output_group(self, o):
        name = o["name"]
        self._previous[name] = previous_args(o)
        desc = " ".join(x for x in (o.get("make"), o.get("model")) if x and x != "Unknown")
        g = self.group(desc or name, name if desc else None)

        g.add(switch_row(_("Enabled"), o.get("enabled", True),
                         lambda v: self._apply(name, ["--on" if v else "--off"])))

        modes = o.get("modes", [])
        labels, args = [], []
        current = 0
        seen = set()
        for m in modes:
            key = (m["width"], m["height"], round(m["refresh"], 2))
            if key in seen:
                continue
            seen.add(key)
            if m.get("current"):
                current = len(labels)
            star = " ★" if m.get("preferred") else ""
            labels.append(f"{m['width']} × {m['height']} @ {m['refresh']:.2f} Hz{star}")
            args.append(["--mode", f"{m['width']}x{m['height']}@{m['refresh']:.3f}Hz"])
        if labels:
            g.add(combo_row(_("Resolution"), labels, current,
                            on_change=lambda i: self._apply(name, args[i])))

        scale = o.get("scale", 1.0)
        scale_idx = min(range(len(SCALES)), key=lambda i: abs(SCALES[i] - scale))
        g.add(combo_row(_("Scale"), [f"{int(s * 100)} %" for s in SCALES], scale_idx,
                        on_change=lambda i: self._apply(name, ["--scale", str(SCALES[i])])))

        tr = o.get("transform", "normal")
        tr_ids = [t[0] for t in TRANSFORMS]
        g.add(combo_row(_("Orientation"), [t[1] for t in TRANSFORMS],
                        tr_ids.index(tr) if tr in tr_ids else 0,
                        on_change=lambda i: self._apply(name, ["--transform", tr_ids[i]])))
        position = o.get("position") or {}
        place = Adw.ActionRow(title=_("Position"),
                             subtitle=_("X moves the screen left or right; Y moves it up or down. "
                                        "Coordinates use logical pixels."))
        coordinates = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        x, y = Gtk.SpinButton.new_with_range(-32768, 32768, 1), Gtk.SpinButton.new_with_range(-32768, 32768, 1)
        for label, spin, value, tooltip in (("X", x, position.get("x", 0), _("Horizontal position")),
                                           ("Y", y, position.get("y", 0), _("Vertical position"))):
            spin.set_value(value)
            spin.set_width_chars(5)
            spin.set_tooltip_text(tooltip)
            coordinates.append(Gtk.Label(label=label))
            coordinates.append(spin)
        move = Gtk.Button(label=_("Move"), valign=Gtk.Align.CENTER)
        move.connect("clicked", lambda *_: self._apply(
            name, ["--pos", f"{x.get_value_as_int()},{y.get_value_as_int()}"]))
        coordinates.append(move)
        place.add_suffix(coordinates)
        g.add(place)
        self.position_controls[name] = (x, y, move)
        return g

    def _apply(self, output, args):
        cmd = ["wlr-randr", "--output", output] + args
        try:
            run(cmd, check=True)
        except RuntimeError as err:
            toast(self, _("Could not change display: {err}").format(err=err))
            return
        undo = self._previous.get(output, {}).get(args[0])
        if undo is None:
            self._keep(output, args)
            return
        self._confirm(output, args, undo)

    def _confirm(self, output, args, undo):
        """As on Windows: keep the change only when confirmed, and go back by
        itself after a few seconds, in case the screen shows nothing now."""
        dialog = Adw.AlertDialog(heading=_("Keep these display settings?"))
        dialog.add_response("revert", _("Revert"))
        dialog.add_response("keep", _("Keep Changes"))
        dialog.set_response_appearance("keep", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("keep")
        dialog.set_close_response("revert")
        left = [KEEP_SECONDS]

        def body():
            dialog.set_body(ngettext("Going back to the previous settings in {n} second.",
                                     "Going back to the previous settings in {n} seconds.",
                                     left[0]).format(n=left[0]))

        def tick():
            left[0] -= 1
            if left[0] <= 0:
                dialog.close()
                return GLib.SOURCE_REMOVE
            body()
            return GLib.SOURCE_CONTINUE

        def done(_dialog, response):
            GLib.source_remove(timer)
            if response == "keep":
                self._keep(output, args)
            else:
                try:
                    run(["wlr-randr", "--output", output] + undo, check=True)
                except RuntimeError as err:
                    toast(self, _("Could not change display: {err}").format(err=err))
            self.refresh()

        body()
        timer = GLib.timeout_add_seconds(1, tick)
        dialog.connect("response", done)
        dialog.present(self)

    def _keep(self, output, args):
        self._save(output, args)
        if compositor.is_wayfire():
            compositor.refresh()

    def _save(self, output, args):
        """Persist settings as a list of wlr-randr commands, one per output+option."""
        path = config_path("displays.sh")
        lines = []
        if os.path.exists(path):
            with open(path) as f:
                lines = [ln.rstrip("\n") for ln in f if ln.startswith("wlr-randr ")]
        prefix = f"wlr-randr --output {shlex.quote(output)} {args[0]}"
        lines = [ln for ln in lines if not ln.startswith(prefix)]
        if args[0] in ("--on", "--off"):
            lines = [ln for ln in lines if not ln.startswith(
                f"wlr-randr --output {shlex.quote(output)} --o")]
        lines.append(" ".join(shlex.quote(a) for a in ["wlr-randr", "--output", output] + args))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("# Written by Aurora Settings\n" + "\n".join(lines) + "\n")
