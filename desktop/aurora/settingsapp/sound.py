"""Sound: output/input devices and volumes via PipeWire (pw-dump + wpctl)."""

import json
import re

from gi.repository import Adw, GLib, Gtk

from aurora.i18n import _
from aurora.settingsapp.util import Page, run


def audio_nodes():
    """Return (sinks, sources, default_sink_name, default_source_name)."""
    try:
        data = json.loads(run(["pw-dump"]) or "[]")
    except json.JSONDecodeError:
        data = []
    sinks, sources = [], []
    default_sink = default_source = None
    for obj in data:
        if obj.get("type") == "PipeWire:Interface:Metadata":
            for entry in obj.get("metadata", []) or []:
                val = entry.get("value")
                if isinstance(val, dict):
                    if entry.get("key") == "default.audio.sink":
                        default_sink = val.get("name")
                    elif entry.get("key") == "default.audio.source":
                        default_source = val.get("name")
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = (obj.get("info") or {}).get("props") or {}
        cls = props.get("media.class")
        node = {"id": obj["id"], "name": props.get("node.name", ""),
                "label": props.get("node.description") or props.get("node.nick")
                or props.get("node.name", "?")}
        if cls == "Audio/Sink":
            sinks.append(node)
        elif cls == "Audio/Source":
            sources.append(node)
    return sinks, sources, default_sink, default_source


def get_volume(target):
    out = run(["wpctl", "get-volume", target])
    m = re.search(r"Volume:\s*([\d.]+)", out)
    return (float(m.group(1)) if m else 0.0), "[MUTED]" in out


class Sound(Page):
    page_id = "sound"
    title = _("Sound")
    icon_name = "audio-speakers-symbolic"

    def build(self):
        self.out_group = self.group(_("Output"))
        self.in_group = self.group(_("Input"))
        self._rows = []
        self.refresh()

    def refresh(self):
        for group, row in self._rows:
            group.remove(row)
        self._rows = []
        sinks, sources, dsink, dsource = audio_nodes()
        self._device_rows(self.out_group, sinks, dsink, "@DEFAULT_AUDIO_SINK@",
                          _("Output device"), "audio-speakers-symbolic")
        self._device_rows(self.in_group, sources, dsource, "@DEFAULT_AUDIO_SOURCE@",
                          _("Input device"), "audio-input-microphone-symbolic")

    def _add(self, group, row):
        group.add(row)
        self._rows.append((group, row))

    def _device_rows(self, group, nodes, default, target, title, icon):
        if not nodes:
            self._add(group, Adw.ActionRow(title=_("No devices found")))
            return
        labels = [n["label"] for n in nodes]
        idx = next((i for i, n in enumerate(nodes) if n["name"] == default), 0)
        combo = Adw.ComboRow(title=title, model=Gtk.StringList.new(labels))
        combo.set_selected(idx)
        combo.connect("notify::selected",
                      lambda r, _p: run(["wpctl", "set-default", str(nodes[r.get_selected()]["id"])]))
        self._add(group, combo)

        vol, muted = get_volume(target)
        row = Adw.ActionRow(title=_("Volume"))
        mute = Gtk.ToggleButton(icon_name="audio-volume-muted-symbolic", active=muted,
                                valign=Gtk.Align.CENTER, css_classes=["flat"],
                                tooltip_text=_("Mute"))
        mute.connect("toggled", lambda b: run(["wpctl", "set-mute", target,
                                               "1" if b.get_active() else "0"]))
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1.0, 0.01)
        scale.set_value(vol)
        scale.set_hexpand(True)
        scale.set_size_request(260, -1)
        scale.set_draw_value(False)
        scale.connect("value-changed",
                      lambda s: run(["wpctl", "set-volume", target, f"{s.get_value():.2f}"]))
        row.add_prefix(Gtk.Image(icon_name=icon))
        row.add_suffix(scale)
        row.add_suffix(mute)
        self._add(group, row)
