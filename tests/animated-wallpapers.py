"""Exercise all the bundled downloaded wallpapers, Settings, desktop pixels and decoder lifecycle."""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import gi
import numpy as np

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Adw, GdkPixbuf, Gio, GLib, GObject, Gtk
from aurora import settings, wallpapers
from aurora.settingsapp.appearance import Appearance
from aurora.settingsapp.backgrounds import MOTIONS, mode_of, find_wallpapers, personal_dir
from aurora.shell.daycycle import cache_link
from aurora.shell.livingwallpaper import LivingWallpaper

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--wallpaper', action='append', default=[], metavar='ID',
                    help='Exercise playback for selected wallpapers; always verify the complete catalog')
args = parser.parse_args()
unknown = set(args.wallpaper) - {key for key, _ in wallpapers.ANIMATED}
if unknown:
    parser.error('Unknown wallpaper: ' + ', '.join(sorted(unknown)))
test_wallpapers = tuple(item for item in wallpapers.ANIMATED if not args.wallpaper or item[0] in args.wallpaper)

OUT = Path('/out/animated')
OUT.mkdir(parents=True, exist_ok=True)


def settle(seconds=.25):
    deadline = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        time.sleep(.01)


def wait_for(predicate, timeout=12):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        settle(.05)
    assert predicate(), 'Video did not finish loading or respond to playback changes'


def ready(widget):
    return widget.media is not None and widget.media.is_prepared() and widget.media.has_video()


class Service(GObject.Object):
    __gsignals__ = {'changed': (GObject.SignalFlags.RUN_FIRST, None, ())}


Adw.init()
s = settings.get()
assert s is not None
assert wallpapers.ANIMATED
credits = json.loads(Path(wallpapers.BACKGROUNDS, 'animated/sources.json').read_text())
assert len(credits) == len(wallpapers.ANIMATED)
assert {e['id'] for e in credits} == {key for key, _ in wallpapers.ANIMATED}
assert {p.stem for p in Path(wallpapers.BACKGROUNDS, 'animated').glob('*.mp4')} == {e['id'] for e in credits}
for entry in credits:
    path = Path(wallpapers.BACKGROUNDS, 'animated', entry['file'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
    assert entry['recipe']['slowdown'] >= 1
    assert Path(wallpapers.poster_path(str(path))).is_file()
included = find_wallpapers([wallpapers.BACKGROUNDS])
static_credits = json.loads(Path(wallpapers.BACKGROUNDS, 'static-sources.json').read_text())
assert len(static_credits) == 15
assert {e['id'] for e in static_credits} == {key for key, _ in wallpapers.STATIC}
for category in ('Space', 'Abstract', 'Nature'):
    assert sum(entry['category'] == category for entry in static_credits) == 5
for entry in static_credits:
    path = wallpapers.scene_path(entry['id'])
    assert path in included, 'Downloaded static wallpaper missing from the gallery'
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == entry['sha256']
for key, _label in wallpapers.ANIMATED:
    path = wallpapers.animated_path(key)
    assert path in included and wallpapers.poster_path(path) not in included
    data = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', path], text=True))
    assert len(data['streams']) == 1, 'Wallpapers must have no audio stream'
    stream = data['streams'][0]
    entry = next(e for e in credits if e['id'] == key)
    assert (stream['width'], stream['height'], stream['codec_name']) == (entry['width'], entry['height'], 'h264')
    assert (entry['width'], entry['height']) in ((1920, 1080), (3840, 2160))
    assert stream['pix_fmt'] == 'yuv420p'
    assert stream['avg_frame_rate'] == '30/1'

# One click disables other modes and selects automatic video playback.
page = Appearance()
window = Gtk.Window(default_width=740, default_height=850, child=page)
window.present()
settle()
for entry in static_credits:
    path = wallpapers.scene_path(entry['id'])
    page.background.choose(path)
    wait_for(lambda: page.background.live_preview.path == path)
    assert page.background.live_preview.media is None, 'Static picture must not start a video decoder'
    assert mode_of(s) == 'picture' and s.get_string('wallpaper') == path
print('15 downloaded static wallpapers: installation, gallery and Settings selection passed', flush=True)

# Exercise the same asynchronous import used by the file picker: originals
# can move, videos get posters, corrupt files do not change the selection.
uploads = Path('/tmp/personal-wallpaper-uploads')
uploads.mkdir(exist_ok=True)
photo = uploads / 'My holiday.JPG'
GdkPixbuf.Pixbuf.new_from_file(wallpapers.scene_path('alpine-valley')).savev(str(photo), 'jpeg', [], [])
paths = [photo]
original = wallpapers.animated_path('rain-window')
for extension in ('MP4', 'mov', 'm4v', 'webm'):
    target = uploads / ('My wallpaper.' + extension)
    codec = ['-vf', 'scale=320:180', '-c:v', 'libvpx-vp9', '-threads', '2'] if extension == 'webm' else ['-c:v', 'copy']
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', original,
                    '-t', '2', '-an', *codec, str(target)], check=True)
    paths.append(target)
personal = []
for source in paths:
    s.set_boolean('wallpaper-dynamic', True)
    s.set_string('wallpaper-animation', 'off')
    assert page.background.import_button.get_visible(), 'Personal import must be available in dynamic mode'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    page.background._import_personal(str(source))
    wait_for(lambda: not page.background._importing, timeout=60)
    dest = s.get_string('wallpaper')
    assert dest != str(source) and Path(dest).parent == Path(personal_dir())
    assert hashlib.sha256(Path(dest).read_bytes()).hexdigest() == source_hash, 'Keep the original quality'
    assert dest in find_wallpapers() and dest in s.get_strv('wallpaper-recent')
    source.rename(source.with_suffix(source.suffix + '.moved'))
    assert Path(dest).is_file(), 'Moving the original must leave the wallpaper available'
    wait_for(lambda: page.background.live_preview.path == dest)
    if wallpapers.is_video(dest):
        wait_for(lambda: ready(page.background.live_preview))
        assert s.get_string('wallpaper-animation') == 'auto'
        assert page.background.live_preview.media.get_loop() and page.background.live_preview.media.get_muted()
        assert Path(wallpapers.poster_path(dest)).is_file()
        assert wallpapers.poster_path(dest) not in find_wallpapers()
    else:
        assert page.background.live_preview.media is None
    personal.append(dest)
before = set(Path(personal_dir()).iterdir())
for suffix in ('jpg', 'mp4'):
    bad = uploads / ('broken.' + suffix)
    bad.write_bytes(b'not an image or a video')
    selected = s.get_string('wallpaper')
    page.background._import_personal(str(bad))
    wait_for(lambda: not page.background._importing, timeout=60)
    assert s.get_string('wallpaper') == selected
    assert set(Path(personal_dir()).iterdir()) == before, 'Failed import left a partial file'
    assert page.background.import_button.get_sensitive()
Gio.Settings.sync()
assert subprocess.check_output(['python3', '-c',
    'from aurora import settings; print(settings.get().get_string("wallpaper"))'], text=True).strip() == personal[-1]
# Gallery/recent selection must also start a personal video after Still.
s.set_string('wallpaper-animation', 'off')
page.background.choose(personal[-1])
wait_for(lambda: page.background.live_preview.running)
assert s.get_string('wallpaper-animation') == 'auto'
print('Personal JPG, MP4, MOV, M4V and WebM: import, preserved originals, gallery, restart persistence and failure cleanup passed', flush=True)

for key, _label in test_wallpapers:
    path = wallpapers.animated_path(key)
    previous = page.background.live_preview.media
    s.set_boolean('wallpaper-slideshow', True)
    s.set_string('wallpaper-animation', 'off')
    page.background.animated_buttons[path].emit('clicked')
    wait_for(lambda: page.background.live_preview.path == path and ready(page.background.live_preview))
    assert mode_of(s) == 'picture' and s.get_string('wallpaper') == path
    assert s.get_string('wallpaper-animation') == 'auto'
    assert page.background.motion_row.get_selected() == MOTIONS.index('auto')
    assert page.background.video_motion_row.get_visible() and page.background.video_motion_row.get_active()
    assert not page.background.motion_row.get_visible()
    assert page.background.live_preview.running and not page.background.live_preview._tick
    assert page.background.live_preview.media.get_loop()
    assert page.background.live_preview.media.get_muted()
    if previous is not None:
        assert previous.get_file() is None, 'Previous decoder was not closed'
    print(f'{key}: Settings selection and decoding passed', flush=True)
subprocess.run(['grim', str(OUT / 'settings.png')], check=True)
window.destroy()
settle()
assert page.background.live_preview.media is None and not page.background.live_preview._handlers

# Pause/resume freezes media time, and unmapping releases the decoder.
tracker, profiles = Service(), Service()
tracker.toplevels, profiles.current = [], 'balanced'
activity = []
video = LivingWallpaper(SimpleNamespace(toplevels=tracker, power_profiles=profiles), activity.append)
video.set_picture(wallpapers.animated_path(test_wallpapers[0][0]))
window = Gtk.Window(default_width=400, default_height=225, child=video)
window.present()
wait_for(lambda: ready(video) and video.media.get_timestamp() > 300000)
profiles.current = 'power-saver'
profiles.emit('changed')
settle(.3)
stamp = video.media.get_timestamp()
settle(.4)
assert not video.running and not video.media.get_playing() and not activity[-1]
assert video.media.get_timestamp() == stamp, 'Power saver did not stop decoding'
profiles.current = 'balanced'
profiles.emit('changed')
wait_for(lambda: video.media.get_timestamp() > stamp + 100000)
tracker.toplevels = [SimpleNamespace(minimized=False, fullscreen=True, maximized=False)]
tracker.emit('changed')
assert not video.running and not video.media.get_playing()
tracker.toplevels[0].minimized = True
tracker.emit('changed')
assert video.running and video.media.get_playing()
video.media.seek(video.media.get_duration() - 250000)
wait_for(lambda: video.media.get_timestamp() > video.media.get_duration() - 600000)
wait_for(lambda: video.media.get_timestamp() < 2000000)
assert video.media.get_playing(), 'Loop stopped at the end'
s.set_string('wallpaper-animation', 'off')
settle()
assert not video.running and not video._video.get_visible()
window.destroy()
settle()
assert video.media is None and not video._handlers

# A corrupt/missing video must expose the static fallback, with no busy timer.
s.set_string('wallpaper-animation', 'auto')
Path('/tmp/broken-wallpaper.mp4').write_bytes(b'not a video')
video = LivingWallpaper()
video.set_picture('/tmp/broken-wallpaper.mp4')
window = Gtk.Window(default_width=400, default_height=225, child=video)
window.present()
wait_for(lambda: video.media is not None and video.media.get_error() is not None)
assert not video.running and not video._video.get_visible() and not video._tick
window.destroy()
settle()


def screenshot(name):
    path = OUT / name
    subprocess.run(['grim', str(path)], check=True)
    pix = GdkPixbuf.Pixbuf.new_from_file(str(path))
    rows = np.frombuffer(pix.get_pixels(), dtype=np.uint8).reshape(pix.get_height(), pix.get_rowstride())
    pixels = rows[:, :pix.get_width() * pix.get_n_channels()].reshape(
        pix.get_height(), pix.get_width(), pix.get_n_channels())
    return pixels[100:-110, 100:-100, :3].astype(float)


for key, _label in test_wallpapers:
    path = wallpapers.animated_path(key)
    s.set_string('wallpaper', path)
    s.set_string('wallpaper-animation', 'auto')
    print(f'{key}: lock poster {Path(cache_link()).resolve()}, selected mode {mode_of(s)}', flush=True)
    wait_for(lambda: Path(cache_link()).resolve() == Path(wallpapers.poster_path(path)).resolve())
    settle(3)
    assert Path(cache_link()).resolve() == Path(wallpapers.poster_path(path)).resolve(), f'Lock poster: {Path(cache_link()).resolve()} expected {wallpapers.poster_path(path)}; mode {mode_of(s)}'
    before = screenshot(f'{key}-a.png')
    settle(1.5)
    after = screenshot(f'{key}-b.png')
    change = float(np.abs(after - before).mean())
    print(f'{key}: desktop movement {change:.3f} levels', flush=True)
    assert change > .08, f'{key}: desktop video frames are frozen'
s.set_string('wallpaper-animation', 'off')
settle(.4)
before = screenshot('still-a.png')
settle(1)
after = screenshot('still-b.png')
assert np.array_equal(before, after), 'Still must stop all movement'
s.set_string('wallpaper-animation', 'auto')
(OUT / 'result').write_text('passed\n')
print(f'{len(test_wallpapers)} video wallpapers: Settings, decode, looping, pause/resume, cleanup, lock screen and desktop motion passed; {len(credits)} catalog entries verified')
