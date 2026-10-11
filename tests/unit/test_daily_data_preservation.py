"""Regression scenarios found while auditing everyday tools across the desktop."""
import io
from pathlib import Path

import pytest
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, GLib
from aurora import clipboard, migrate, usbwriter
from aurora.files import imagetools


def picture(path):
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 40, 30)
    pix.fill(0x336699ff)
    pix.savev(str(path), 'jpeg', [], [])
    return path


def test_image_conversion_preserves_an_existing_other_format(tmp_path):
    source = picture(tmp_path / 'photo.jpg')
    target = tmp_path / 'photo.png'
    target.write_bytes(b'an existing picture')
    with pytest.raises(FileExistsError):
        imagetools.resize(str(source), 20, 'Small', 'png', True)
    assert source.exists() and target.read_bytes() == b'an existing picture'


def test_image_copy_never_follows_an_existing_dangling_link(tmp_path):
    source = picture(tmp_path / 'photo.jpg')
    victim = tmp_path / 'elsewhere'
    (tmp_path / 'photo (Small).jpg').symlink_to(victim)
    target = imagetools.resize(str(source), 20, 'Small')
    assert not victim.exists()
    assert Path(target).name == 'photo (Small 2).jpg'


def test_failed_image_save_keeps_the_original_and_removes_temporary_files(tmp_path, monkeypatch):
    source = picture(tmp_path / 'photo.jpg')
    before = source.read_bytes()
    def failed(_pix, filename, *_args):
        Path(filename).write_bytes(b'partial encoded file')
        raise GLib.Error('encoding failed')
    monkeypatch.setattr(GdkPixbuf.Pixbuf, 'savev', failed)
    with pytest.raises(GLib.Error):
        imagetools.resize(str(source), 20, 'Small', in_place=True)
    assert source.read_bytes() == before and sorted(p.name for p in tmp_path.iterdir()) == ['photo.jpg']


@pytest.mark.parametrize('format', ['gnu', 'bsd'])
def test_usb_checksum_matches_the_whole_filename(tmp_path, format):
    image = tmp_path / 'disk.img'
    image.write_bytes(b'image')
    digest = usbwriter.checksum(str(image))
    if format == 'gnu':
        text = f"{'0'*64}  disk.img.old\n{digest} *disk.img\n"
    else:
        text = f"SHA256 (disk.img.old) = {'0'*64}\nSHA256 (disk.img) = {digest}\n"
    (tmp_path / 'SHA256SUMS').write_text(text)
    assert usbwriter.stated_checksum(str(image)) == (digest, 'SHA256SUMS')


def test_pinned_clipboard_item_survives_more_than_the_history_limit(home):
    clipboard.store(io.StringIO('keep this'), env={})
    clipboard.pin('keep this')
    for n in range(clipboard.LIMIT + 2):
        clipboard.store(io.StringIO(f'entry {n}'), env={})
    assert clipboard.load()[0] == 'keep this'
    assert len(clipboard.load()) == clipboard.LIMIT
    assert len(clipboard._meta()) == clipboard.LIMIT


def test_ignored_clipboard_input_does_not_create_metadata(home):
    clipboard.store(io.StringIO('  '), env={})
    clipboard.store(io.StringIO('x' * (clipboard.MAX_BYTES + 1)), env={})
    assert clipboard.load() == [] and clipboard._meta() == {}


def test_migration_keeps_a_dangling_destination_link(tmp_path):
    source, target = tmp_path / 'Windows', tmp_path / 'Aurora'
    source.mkdir(); target.mkdir()
    (source / 'document.txt').write_text('incoming')
    victim = tmp_path / 'outside'
    (target / 'document.txt').symlink_to(victim)
    skipped = []
    assert migrate.copy_tree(str(source), str(target), skipped=skipped) == 0
    assert not victim.exists() and skipped == [str(target / 'document.txt')]


def test_migration_exports_choose_unused_names(tmp_path, monkeypatch):
    profile = tmp_path / 'Windows'
    themes = profile / 'AppData/Roaming/Microsoft/Windows/Themes'
    themes.mkdir(parents=True)
    (themes / 'TranscodedWallpaper').write_bytes(b'new picture')
    (tmp_path / 'Windows background.jpg').write_bytes(b'old picture')
    (tmp_path / 'Windows bookmarks.html').write_text('old bookmarks')
    monkeypatch.setattr(GLib, 'get_user_special_dir', lambda _kind: str(tmp_path))
    monkeypatch.setattr(migrate, 'browser_bookmark_files', lambda _path: {'Edge': 'fixture'})
    monkeypatch.setattr(migrate, 'chromium_bookmarks', lambda _path: [('New', 'https://example.com')])
    job = migrate.Migration({'path': str(profile)}, [], [], lambda *_args: False, lambda *_args: False)
    job._wallpaper(); job._bookmarks()
    assert (tmp_path / 'Windows background.jpg').read_bytes() == b'old picture'
    assert (tmp_path / 'Windows bookmarks.html').read_text() == 'old bookmarks'
    assert (tmp_path / 'Windows background (2).jpg').read_bytes() == b'new picture'
    assert 'https://example.com' in (tmp_path / 'Windows bookmarks (2).html').read_text()


def test_resizing_does_not_replace_an_original_edited_while_encoding(tmp_path, monkeypatch):
    source = picture(tmp_path / 'photo.jpg')
    save = GdkPixbuf.Pixbuf.savev
    def edited(pix, filename, *args):
        result = save(pix, filename, *args)
        source.write_bytes(b'edited by another application')
        return result
    monkeypatch.setattr(GdkPixbuf.Pixbuf, 'savev', edited)
    with pytest.raises(OSError, match='Changed while resizing'):
        imagetools.resize(str(source), 20, 'Small', in_place=True)
    assert source.read_bytes() == b'edited by another application'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['photo.jpg']


def test_pin_and_watcher_preserve_each_others_metadata(home, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    clipboard.store(io.StringIO('favorite'), env={})
    pin_saving, release_pin, store_started = threading.Event(), threading.Event(), threading.Event()
    save = clipboard._save_meta
    def held(meta):
        if threading.current_thread().name.startswith('pin-audit'):
            pin_saving.set()
            assert release_pin.wait(2)
        save(meta)
    monkeypatch.setattr(clipboard, '_save_meta', held)
    def incoming():
        store_started.set()
        clipboard.store(io.StringIO('new clipboard text'), env={})
    with ThreadPoolExecutor(1, thread_name_prefix='pin-audit') as pin_pool, \
            ThreadPoolExecutor(1, thread_name_prefix='store-audit') as store_pool:
        pinning = pin_pool.submit(clipboard.pin, 'favorite')
        try:
            assert pin_saving.wait(1)
            storing = store_pool.submit(incoming)
            assert store_started.wait(1)
            try:
                storing.result(timeout=.15)
            except TimeoutError:
                pass
        finally:
            release_pin.set()
        pinning.result(); storing.result()
    assert clipboard.info('favorite')['pinned']
    assert clipboard.info('new clipboard text')['time'] > 0
    assert set(clipboard.load()) == {'favorite', 'new clipboard text'}


def test_usb_named_checksum_file_matches_the_requested_image(tmp_path):
    image = tmp_path / 'disk.img'
    image.write_bytes(b'image')
    digest = usbwriter.checksum(str(image))
    sidecar = tmp_path / 'disk.img.sha256'
    sidecar.write_text(f"{'0'*64}  other.img\n{digest}  ./disk.img\n")
    assert usbwriter.stated_checksum(str(image)) == (digest, sidecar.name)
    sidecar.write_text(digest + '\n')
    assert usbwriter.stated_checksum(str(image)) == (digest, sidecar.name)
