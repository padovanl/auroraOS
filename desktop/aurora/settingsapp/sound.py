"""Sound: output/input devices and volumes via PipeWire (pw-dump + wpctl)."""

import shutil

from gi.repository import Adw, GLib, Gtk

from aurora import apps, settings
from aurora.i18n import _
from aurora.settingsapp.util import Page, run, switch_row
from aurora.shell.services import audio_nodes, get_volume


SOUNDS = "/usr/share/sounds/aurora"


class Sound(Page):
    page_id = "sound"
    title = _("Sound")
    icon_name = "audio-speakers-symbolic"

    def build(self):
        self.out_group = self.group(_("Output"))
        self.in_group = self.group(_("Input"))
        self._rows = []
        self.refresh()

        # Volume Mixer: each app playing sound, with its own volume.
        mixer = self.group(_("Volume Mixer"), _("Apps playing sound right now"))
        self.mixer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                                 margin_top=6, margin_bottom=6)
        mixer.add(self.mixer_box)
        self._mixer_source = 0
        self.connect("map", lambda *_a: self._start_mixer())
        self.connect("unmap", lambda *_a: self._stop_mixer())

        aurora = settings.get()
        if aurora is not None:
            loud = self.group()
            loud.add(switch_row(_("Over-amplification"), aurora.get_boolean("volume-overamplify"),
                                lambda v: (aurora.set_boolean("volume-overamplify", v),
                                           self.refresh()),
                                subtitle=_("Allow the volume above 100%. Sound may be "
                                           "distorted.")))
            alerts = self.group(_("System Sounds"))
            row = switch_row(_("Startup and shutdown sounds"), aurora.get_boolean("session-sounds"),
                             lambda v: aurora.set_boolean("session-sounds", v),
                             subtitle=_("The Aurora sound when you log in, shut down, restart "
                                        "or log out"))
            alerts.add(row)
            for name, title in (("startup", _("Startup sound")),
                                ("shutdown", _("Shutdown sound"))):
                preview = Adw.ActionRow(title=title)
                play = Gtk.Button(icon_name="media-playback-start-symbolic",
                                  tooltip_text=_("Play"), valign=Gtk.Align.CENTER,
                                  css_classes=["flat"])
                play.connect("clicked", lambda _b, n=name: apps.spawn(
                    ["pw-play", f"{SOUNDS}/{n}.wav"]))
                preview.add_suffix(play)
                alerts.add(preview)

    def _start_mixer(self):
        self._update_mixer()
        if not self._mixer_source:
            self._mixer_source = GLib.timeout_add_seconds(2, self._update_mixer)

    def _stop_mixer(self):
        if self._mixer_source:
            GLib.source_remove(self._mixer_source)
            self._mixer_source = 0

    def _update_mixer(self):
        from aurora import mixerui
        from aurora.shell.services import app_streams
        aurora = settings.get()
        loud = aurora is not None and aurora.get_boolean("volume-overamplify")
        mixerui.fill(self.mixer_box, app_streams(),
                     _("When an app plays sound, its volume appears here"),
                     maximum=1.5 if loud else 1.0)
        return GLib.SOURCE_CONTINUE

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
        aurora = settings.get()
        top = 1.5 if aurora is not None and aurora.get_boolean("volume-overamplify") else 1.0
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, top, 0.01)
        if top > 1.0:
            scale.add_mark(1.0, Gtk.PositionType.BOTTOM, None)
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
        if target == "@DEFAULT_AUDIO_SINK@" and shutil.which("pactl"):
            self._add(group, self._balance_row(scale))

    def _balance_row(self, volume):
        """Left/right balance, applied as per-channel volumes (pactl)."""
        row = Adw.ActionRow(title=_("Balance"))
        bal = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.05)
        bal.set_value(0.0)
        bal.add_mark(0.0, Gtk.PositionType.BOTTOM, None)
        bal.set_hexpand(True)
        bal.set_size_request(260, -1)
        bal.set_draw_value(False)

        def apply(*_a):
            v, b = volume.get_value(), bal.get_value()
            left = v * (1 - max(0.0, b))
            right = v * (1 + min(0.0, b))
            run(["pactl", "set-sink-volume", "@DEFAULT_SINK@",
                 f"{left * 100:.0f}%", f"{right * 100:.0f}%"])
        bal.connect("value-changed", apply)
        row.add_prefix(Gtk.Label(label=_("Left"), css_classes=["dim-label"]))
        row.add_suffix(bal)
        row.add_suffix(Gtk.Label(label=_("Right"), css_classes=["dim-label"]))
        return row
