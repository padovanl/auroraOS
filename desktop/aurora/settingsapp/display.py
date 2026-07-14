"""Displays: resolution, refresh rate, scale, rotation via wlr-randr.

Changes apply immediately and are saved to ~/.config/aurora/displays.sh,
which the session runs at login.
"""

import json
import os
import shlex

from gi.repository import Adw, Gtk

from aurora import config_path
from aurora.i18n import _
from aurora.settingsapp.util import Page, combo_row, run, switch_row, toast

SCALES = [1.0, 1.25, 1.5, 1.75, 2.0]
TRANSFORMS = [("normal", _("Normal")), ("90", _("90° Clockwise")),
              ("180", _("Upside Down")), ("270", _("90° Counterclockwise"))]


def outputs():
    out = run(["wlr-randr", "--json"])
    try:
        return json.loads(out) if out else []
    except json.JSONDecodeError:
        return []


class Displays(Page):
    page_id = "display"
    title = _("Displays")
    icon_name = "video-display-symbolic"

    def build(self):
        self._groups = []
        self.refresh()

    def refresh(self):
        for g in self._groups:
            self.remove(g)
        self._groups = []
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
        return g

    def _apply(self, output, args):
        cmd = ["wlr-randr", "--output", output] + args
        try:
            run(cmd, check=True)
        except RuntimeError as err:
            toast(self, _("Could not change display: {err}").format(err=err))
            return
        self._save(output, args)

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
