"""System monitor readings, the color picker's pixel decoding, and the shortcut list."""

from aurora.shell import colorpicker, sysmon


def test_cpu_percent_from_proc_stat():
    before = sysmon.cpu_times("cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 1 2 3 4\n")
    after = sysmon.cpu_times("cpu  150 0 150 900 0 0 0 0 0 0\n")
    # 100 busy jiffies out of 200: half the processor.
    assert sysmon.cpu_percent(before, after) == 50.0
    assert sysmon.cpu_percent(after, after) == 0.0


def test_iowait_counts_as_idle():
    before = sysmon.cpu_times("cpu  0 0 0 0 0 0 0 0\n")
    after = sysmon.cpu_times("cpu  10 0 0 50 40 0 0 0\n")
    assert sysmon.cpu_percent(before, after) == 10.0


def test_memory_uses_available():
    used, total = sysmon.memory("MemTotal: 8000 kB\nMemFree: 1000 kB\nMemAvailable: 6000 kB\n")
    assert (used, total) == (2000 * 1024, 8000 * 1024)


def test_network_skips_loopback(tmp_path):
    for name, rx, tx in (("lo", 999, 999), ("eth0", 10, 20), ("wlan0", 5, 1)):
        stats = tmp_path / name / "statistics"
        stats.mkdir(parents=True)
        (stats / "rx_bytes").write_text(str(rx))
        (stats / "tx_bytes").write_text(str(tx))
    assert sysmon.network_bytes(str(tmp_path)) == (15, 21)


def test_temperature_prefers_the_processor(tmp_path):
    for entry, name, milli in (("hwmon0", "acpitz", 40000), ("hwmon1", "coretemp", 55500)):
        (tmp_path / entry).mkdir()
        (tmp_path / entry / "name").write_text(name + "\n")
        (tmp_path / entry / "temp1_input").write_text(str(milli))
    assert sysmon.temperature(str(tmp_path)) == 55.5
    assert sysmon.temperature(str(tmp_path / "missing")) is None


def test_rates_read_naturally():
    assert sysmon.human_rate(512) == "512 B/s"
    assert sysmon.human_rate(2_500_000) == "2.5 MB/s"


def test_ppm_pixel_and_hex():
    assert colorpicker.ppm_pixel(b"P6\n1 1\n255\n\x12\xab\xff") == (0x12, 0xAB, 0xFF)
    assert colorpicker.ppm_pixel(b"P6 # grim\n1 1 255 \x00\x80\x01") == (0, 128, 1)
    # 16-bit samples are scaled down.
    assert colorpicker.ppm_pixel(b"P6\n1 1\n65535\n\xff\xff\x00\x00\x80\x00") == (255, 0, 128)
    assert colorpicker.hex_color((18, 171, 255)) == "#12ABFF"


def test_every_shortcut_in_the_overlay_has_words(monkeypatch, tmp_path):
    import os
    import shutil
    from aurora.shell import shortcuts
    config = tmp_path / ".config" / "labwc"
    config.mkdir(parents=True)
    rc = os.path.join(os.path.dirname(__file__), "..", "..", "desktop", "data", "labwc", "rc.xml")
    shutil.copy(rc, config / "rc.xml")
    monkeypatch.setenv("HOME", str(tmp_path))
    rows = shortcuts.shortcut_rows()
    titles = [title for title, _keys in rows]
    assert "Pick a color from the screen" in titles
    assert "Show keyboard shortcuts" in titles
    assert len(titles) == len(set(titles))  # one row per action
    assert not any("aurora-shell" in t for t in titles)


def test_ai_download_refuses_to_fill_the_disk(tmp_path):
    from collections import namedtuple

    import pytest

    from aurora.ai import download
    Usage = namedtuple("Usage", "total used free")
    item = {"size": 5 * 10 ** 9}
    dest = str(tmp_path / "model.gguf")
    big_disk = lambda _p: Usage(500 * 10 ** 9, 0, 40 * 10 ** 9)   # noqa: E731
    download.check_space(item, dest, usage=big_disk)               # 40 GB free: fine
    # 14 GB free on a 500 GB disk: 5 GB would leave 9, under the 10 GB reserve.
    edge = lambda _p: Usage(500 * 10 ** 9, 0, 14 * 10 ** 9)        # noqa: E731
    with pytest.raises(download.DownloadError, match="Not enough disk space"):
        download.check_space(item, dest, usage=edge)
    # A resumed download only needs the rest.
    download.check_space(item, dest, have=4 * 10 ** 9, usage=edge)
    # Small disks keep at least 2 GB free.
    small = lambda _p: Usage(20 * 10 ** 9, 0, 6 * 10 ** 9)         # noqa: E731
    with pytest.raises(download.DownloadError):
        download.check_space(item, dest, usage=small)


def test_full_disk_during_download_leaves_no_part_file(tmp_path, monkeypatch):
    import errno
    import hashlib
    import io

    import pytest

    from aurora.ai import download
    data = b"x" * (3 << 20)
    item = {"url": "https://example.invalid/m", "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}
    dest = tmp_path / "m.bin"
    real_open = open

    class Full(io.BufferedWriter):
        pass

    def opener(_req, timeout):
        return io.BytesIO(data)

    def failing_open(path, mode="r", *a, **k):
        f = real_open(path, mode, *a, **k)
        if str(path).endswith(".part"):
            def write(_block):
                raise OSError(errno.ENOSPC, "No space left on device")
            f.write = write
        return f

    from collections import namedtuple
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(download.shutil, "disk_usage",
                        lambda _p: Usage(500 * 10 ** 9, 0, 400 * 10 ** 9))
    monkeypatch.setattr("builtins.open", failing_open)
    with pytest.raises(download.DownloadError, match="filled up"):
        download.fetch(item, str(dest), opener=opener)
    assert not (tmp_path / "m.bin.part").exists()


def test_disk_low_threshold():
    from aurora.shell.sysnotify import disk_low
    gb = 1024 ** 3
    assert disk_low(100 * gb, 1 * gb)          # under 2 GB
    assert not disk_low(100 * gb, 10 * gb)     # 10% free
    assert disk_low(1000 * gb, 8 * gb)         # big disks keep at most 10 GB free
    assert not disk_low(1000 * gb, 40 * gb)


def test_disk_warning_skips_the_live_system():
    from aurora.shell.sysnotify import MEMORY_FS, fs_type
    live = ("overlay / overlay rw 0 0\n"
            "tmpfs /run tmpfs rw 0 0\n"
            "/dev/sr0 /run/live/medium iso9660 ro 0 0\n")
    assert fs_type("/", live) in MEMORY_FS
    assert fs_type("/home/aurora", live) in MEMORY_FS
    installed = ("/dev/vda2 / btrfs rw 0 0\n"
                 "/dev/vda1 /boot/efi vfat rw 0 0\n"
                 "/dev/vdb1 /home ext4 rw 0 0\n"
                 "tmpfs /home/me/cache tmpfs rw 0 0\n")
    assert fs_type("/", installed) == "btrfs"
    assert fs_type("/home/me", installed) == "ext4"
    assert fs_type("/homework", installed) == "btrfs"


def test_corner_assistant_sits_on_the_dock_or_at_the_bottom(tmp_path, monkeypatch):
    from aurora import assistant
    # Just above a dock that covers the bottom (it can be as wide as the screen)…
    assert assistant.pip_bottom_margin(82) == 90
    # …right at the bottom when there's none (side, off, auto-hidden).
    assert assistant.pip_bottom_margin(0) == 12
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    (tmp_path / "aurora-dock").write_text("76\n")
    assert assistant.dock_covers() == 76
    (tmp_path / "aurora-dock").write_text("0\n")
    assert assistant.dock_covers() == 0
    # A dock that ends well left of the Assistant leaves the corner free.
    assert assistant.pip_bottom_margin(82, 1300, 1920, 420) == 12
    assert assistant.pip_bottom_margin(82, 1600, 1920, 420) == 90
    (tmp_path / "aurora-dock").write_text("82 1300\n")
    assert assistant.dock_state() == (82, 1300)


def test_attachments_are_read_without_numpy(tmp_path, monkeypatch):
    import builtins
    import importlib
    import sys
    real_import = builtins.__import__

    def no_numpy(name, *args, **kwargs):
        if name == "numpy" or name.startswith("numpy."):
            raise ModuleNotFoundError("No module named 'numpy'")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_numpy)
    sys.modules.pop("aurora.ai.index", None)
    index = importlib.import_module("aurora.ai.index")
    note = tmp_path / "notes.txt"
    note.write_text("ship on Friday")
    assert index.extract(str(note)) == "ship on Friday"
    sys.modules.pop("aurora.ai.index", None)


def test_snap_zones_tile_the_work_area_exactly():
    from aurora.shell import snapzones as snap
    area = {"x": 0, "y": 31, "width": 1277, "height": 687}
    for layout in snap.LAYOUTS:
        cells = [snap.zone_geometry(z, area) for z in layout]
        assert sum(c["width"] * c["height"] for c in cells) == area["width"] * area["height"]
        for c in cells:
            assert c["x"] >= 0 and c["x"] + c["width"] <= area["width"]
            assert c["y"] >= 31 and c["y"] + c["height"] <= 31 + 687
    assert snap.other_half(snap.LEFT_HALF) == snap.LAYOUTS[0][1]
    assert snap.other_half(snap.RIGHT_HALF) == snap.LAYOUTS[0][0]
    assert snap.other_half(15) is None


def test_snap_assist_offers_other_windows_most_recent_first():
    from aurora.shell import snapzones as snap
    views = [
        {"id": 1, "role": "toplevel", "output-name": "A", "last-focus-timestamp": 5},
        {"id": 2, "role": "toplevel", "output-name": "A", "last-focus-timestamp": 9},
        {"id": 3, "role": "toplevel", "output-name": "B"},
        {"id": 4, "role": "desktop-environment", "output-name": "A"},
        {"id": 5, "role": "toplevel", "output-name": "A", "app-id": "org.aurora.Assistant"},
    ]
    assert [v["id"] for v in snap.candidates(views, "A", {1})] == [2]
    assert [v["id"] for v in snap.candidates(views, "A")] == [2, 1]


def test_more_widget_helpers():
    import datetime
    pytest = __import__("pytest")
    more = pytest.importorskip("aurora.shell.morewidgets")
    assert more.days_until(datetime.date(2026, 12, 25), datetime.date(2026, 12, 20)) == 5
    assert more.parse_date("nonsense", datetime.date(2026, 1, 1)) == datetime.date(2026, 1, 1)
    frac, start, end = more.period_progress(datetime.datetime(2026, 7, 2, 12), "year")
    assert start.year == 2026 and end.year == 2027 and 0.49 < frac < 0.51
    frac, start, _end = more.period_progress(datetime.datetime(2026, 9, 30, 18), "day")
    assert frac == 0.75
    frac, start, _end = more.period_progress(datetime.datetime(2026, 10, 1), "week")
    assert start.weekday() == 0
    full = datetime.datetime(2026, 8, 28, 4, 58, tzinfo=datetime.timezone.utc)  # a full moon
    assert more.moon(full)[2] == 4 and more.moon(full)[1] > 0.97
    assert more.load_tasks('[{"text": "milk"}, {"text": " "}, 3]') == [
        {"text": "milk", "done": False}]


def test_new_widgets_find_a_free_spot():
    from aurora.shell.widgets import free_spot
    # An empty screen: the top-right corner.
    assert free_spot(100, 100, [], 1000, 600, top=40, edge=10) == (890, 40)
    # Below a widget already there, then the next column.
    others = [(890, 40, 100, 100)]
    assert free_spot(100, 100, others, 1000, 600, top=40, edge=10, gap=0) == (890, 140)
    column = [(890, y, 100, 100) for y in range(40, 600, 100)]
    x, y = free_spot(100, 100, column, 1000, 600, top=40, edge=10)
    assert x + 100 <= 890 and y == 40
    assert free_spot(100, 100, [(0, 0, 1000, 600)], 1000, 600) is None


def test_widget_rectangles_overlap():
    from aurora.shell.widgets import rects_overlap
    assert rects_overlap((0, 0, 100, 100), (50, 50, 100, 100))
    assert not rects_overlap((0, 0, 100, 100), (100, 0, 100, 100))   # side by side
    assert not rects_overlap((0, 0, 100, 100), (0, 100, 100, 100))   # one under the other


def test_snapped_windows_keep_the_gap():
    from aurora.shell.snapzones import with_gaps
    area = {"x": 0, "y": 40, "width": 1000, "height": 760}
    left = {"x": 0, "y": 40, "width": 500, "height": 760}
    right = {"x": 500, "y": 40, "width": 500, "height": 760}
    assert with_gaps(left, area, 0) == left
    l, r = with_gaps(left, area, 10), with_gaps(right, area, 10)
    assert (l["x"], l["y"]) == (10, 50)                    # full gap at the screen's edges
    assert r["x"] - (l["x"] + l["width"]) == 10            # the same gap between them
    assert r["x"] + r["width"] == 990 and r["y"] + r["height"] == 790


def test_included_wallpapers_have_readable_names():
    from aurora.settingsapp.backgrounds import pretty_name
    assert pretty_name("/usr/share/backgrounds/aurora/aurora-veil-dusk.png") == "Veil · Dusk"
    assert pretty_name("/home/me/Pictures/my-cat_photo.jpg") == "my cat photo"


def test_dynamic_series_fall_back_to_the_default():
    from aurora import wallpapers

    class Settings:
        def __init__(self, value):
            self.value = value

        def get_string(self, _key):
            return self.value
    assert wallpapers.chosen_series(Settings("horizon")) == "horizon"
    assert wallpapers.chosen_series(Settings("gone")) == wallpapers.DEFAULT_SERIES
    assert wallpapers.chosen_series(None) == wallpapers.DEFAULT_SERIES
    assert wallpapers.path("veil", "night").endswith("/aurora-veil-night.png")
