"""Sun position, conversions, clipboard history, OCR helpers, weather parsing,
Spotlight providers and the Night Light schedule."""

import datetime
import io
import json
import os
import zoneinfo

import pytest

from aurora import clipboard, convert, ocr, sun, weather

ROME = zoneinfo.ZoneInfo("Europe/Rome")


# --- sun -----------------------------------------------------------------

def test_timezone_coordinates():
    lat, lon = sun.location("Europe/Rome")
    assert lat == pytest.approx(41.9, abs=0.1) and lon == pytest.approx(12.48, abs=0.1)
    lat, lon = sun.location("America/New_York")
    assert lat == pytest.approx(40.7, abs=0.2) and lon == pytest.approx(-74.0, abs=0.2)
    assert sun.location("Not/AZone") is None


@pytest.mark.parametrize("date, rise, set_", [
    (datetime.date(2026, 6, 21), "05:34", "20:48"),
    (datetime.date(2026, 12, 21), "07:34", "16:41"),
])
def test_sunrise_sunset_rome(date, rise, set_):
    r, s = sun.sun_times(41.9, 12.48, date, ROME)

    def minutes(hhmm):
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    assert abs(r.hour * 60 + r.minute - minutes(rise)) <= 5
    assert abs(s.hour * 60 + s.minute - minutes(set_)) <= 5


def test_polar_day_has_no_sunset():
    assert sun.sun_times(78.2, 15.6, datetime.date(2026, 6, 21), datetime.timezone.utc) is None


@pytest.mark.parametrize("hour, phase", [(3, "night"), (7, "dawn"), (13, "day"),
                                         (19, "dusk"), (23, "night")])
def test_phases_through_a_day(hour, phase):
    when = datetime.datetime(2026, 9, 23, hour, 20, tzinfo=ROME)
    assert sun.phase(when, (41.9, 12.48)) == phase


def test_is_dark():
    loc = (41.9, 12.48)
    assert sun.is_dark(datetime.datetime(2026, 9, 23, 22, 0, tzinfo=ROME), loc)
    assert not sun.is_dark(datetime.datetime(2026, 9, 23, 12, 0, tzinfo=ROME), loc)


# --- conversions ---------------------------------------------------------

@pytest.mark.parametrize("query, expected", [
    ("10 km in mi", 6.2137),
    ("5 kg to lb", 11.0231),
    ("100 f in c", 37.7778),
    ("0 c in k", 273.15),
    ("1 GiB in MB", 1073.7418),
    ("90 min in h", 1.5),
    ("3 ft in cm", 91.44),
    ("1 gal in l", 3.7854),
])
def test_unit_conversion(query, expected):
    value, frm, to = convert.parse(query)
    assert convert.convert_units(value, frm, to) == pytest.approx(expected, rel=1e-4)


def test_incompatible_units_do_not_convert():
    assert convert.convert_units(1, "kg", "km") is None
    assert convert.parse("hello world") is None


def test_currency_parsing_and_math():
    assert convert.parse("100 usd in eur") == (100.0, "usd", "eur")
    assert convert.parse("€20 to gbp") == (20.0, "eur", "gbp")
    assert convert.is_currency("usd", "eur")
    rates = {"eur": 1.0, "usd": 1.10, "gbp": 0.85}
    assert convert.convert_currency(110, "usd", "gbp", rates) == pytest.approx(85)


def test_ecb_xml_parsing():
    xml = b"""<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
      xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><Cube><Cube time="2026-09-22">
      <Cube currency="USD" rate="1.1000"/><Cube currency="JPY" rate="160.5"/></Cube></Cube>
      </gesmes:Envelope>"""
    rates = convert.parse_ecb(xml)
    assert rates == {"eur": 1.0, "usd": 1.1, "jpy": 160.5}


def test_rates_cache_expires(home, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    os.makedirs(os.path.dirname(convert.rates_path()))
    with open(convert.rates_path(), "w") as f:
        json.dump({"fetched": 0, "rates": {"eur": 1}}, f)
    assert convert.cached_rates() is None
    assert convert.cached_rates(max_age=10 ** 12) == {"eur": 1}


def test_number_formatting():
    assert convert.format_number(6.21371192) == "6.213712"
    assert convert.format_number(1500) == "1,500"
    assert convert.format_number(0) == "0"


# --- clipboard history ---------------------------------------------------

@pytest.fixture
def data_home(home, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    return home


def test_clipboard_store_and_dedupe(data_home):
    for text in ("one", "two", "one"):
        clipboard.store(io.StringIO(text), env={"CLIPBOARD_STATE": "data"})
    assert clipboard.load() == ["one", "two"]
    assert oct(os.stat(clipboard.history_path()).st_mode & 0o777) == "0o600"


def test_clipboard_skips_passwords_and_blanks(data_home):
    clipboard.store(io.StringIO("hunter2"), env={"CLIPBOARD_STATE": "sensitive"})
    clipboard.store(io.StringIO("   "), env={})
    assert clipboard.load() == []


def test_clipboard_limit_and_clear(data_home):
    items = []
    for i in range(clipboard.LIMIT + 20):
        items = clipboard.add(str(i), items)
    assert len(items) == clipboard.LIMIT and items[0] == str(clipboard.LIMIT + 19)
    clipboard.store(io.StringIO("x"), env={})
    clipboard.clear()
    assert clipboard.load() == []


# --- OCR helpers ---------------------------------------------------------

def test_ocr_language_choice(monkeypatch):
    monkeypatch.setattr(ocr, "installed_languages", lambda: {"eng", "ita", "chi_sim"})
    assert ocr.language_for("it_IT.UTF-8") == "eng+ita"
    assert ocr.language_for("en_US.UTF-8") == "eng"
    assert ocr.language_for("zh_CN.UTF-8") == "eng+chi_sim"
    assert ocr.language_for("de_DE.UTF-8") == "eng"      # German data not installed


def test_ocr_cleanup():
    assert ocr.clean("Hello  \n\n\n\nWorld\f\n") == "Hello\n\nWorld"


# --- weather -------------------------------------------------------------

def test_weather_parse_and_icons():
    payload = {
        "current": {"time": "2026-09-23T14:00", "temperature_2m": 22.4, "weather_code": 2,
                    "is_day": 1},
        "current_units": {"temperature_2m": "°C"},
        "daily": {"temperature_2m_max": [24.0], "temperature_2m_min": [15.5]},
        "hourly": {"time": [f"2026-09-23T{h:02d}:00" for h in range(24)],
                   "temperature_2m": list(range(24)), "weather_code": [0] * 24},
    }
    w = weather.parse(payload)
    assert w["temp"] == 22.4 and w["high"] == 24.0 and w["unit"] == "°C"
    assert [h[0] for h in w["hours"]] == ["15:00", "18:00", "21:00"]
    assert weather.describe(0, is_day=False)[1] == "weather-clear-night-symbolic"
    assert weather.describe(95)[1] == "weather-storm-symbolic"


# --- Spotlight providers -------------------------------------------------

def test_spotlight_emoji_and_units():
    from aurora.shell import search
    results = search.search_emoji(":rocket")
    assert results and results[0].title.startswith("🚀")
    conv = search.search_convert("10 km in mi")
    assert conv and "6.213712 mi" in conv[0].title


def test_spotlight_clipboard(data_home):
    from aurora.shell import search
    clipboard.store(io.StringIO("git push origin main"), env={})
    results = search.search_clipboard("clip: push")
    assert results[0].title == "git push origin main"


def test_spotlight_projects(home, monkeypatch):
    from aurora.shell import search
    repo = home / "git" / "portop"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    monkeypatch.setattr(search, "_projects_cache", (0.0, []))
    results = search.search_projects("port")
    assert results and results[0].title == "portop" and "main" in results[0].subtitle


# --- Night Light ---------------------------------------------------------

class FakeSettings:
    def __init__(self, **values):
        self.values = values

    def get_boolean(self, key):
        return self.values[key]

    def get_int(self, key):
        return self.values[key]

    def get_string(self, key):
        return self.values[key]


@pytest.mark.parametrize("schedule, expected", [
    ("always", ["-t", "4000", "-T", "4001"]),
    ("manual", ["-t", "4000", "-T", "6500", "-s", "21:00", "-S", "06:30"]),
    ("sunset", ["-t", "4000", "-T", "6500", "-l", "41.90", "-L", "12.48"]),
])
def test_night_light_arguments(monkeypatch, schedule, expected):
    from aurora.shell import daycycle
    fake = FakeSettings(**{"night-light": True, "night-light-temperature": 4000,
                           "night-light-schedule": schedule, "night-light-from": "21:00",
                           "night-light-to": "06:30"})
    monkeypatch.setattr(daycycle.settings, "get", lambda *a: fake)
    cycle = daycycle.DayCycle.__new__(daycycle.DayCycle)
    cycle.location = (41.9, 12.483)
    assert cycle.night_light_args() == expected


def test_weather_units_follow_the_measurement_locale():
    # English text with Italian formats: Celsius, as GNOME Weather shows.
    env = {"LANG": "en_US.UTF-8", "LC_MEASUREMENT": "it_IT.UTF-8"}
    assert weather.measurement_locale(env) == "it_IT.UTF-8"
    assert not weather.uses_fahrenheit(weather.measurement_locale(env))
    assert weather.measurement_locale({"LANG": "en_US.UTF-8"}) == "en_US.UTF-8"
    assert weather.measurement_locale({"LC_ALL": "de_DE", "LC_MEASUREMENT": "en_US"}) == "de_DE"


def test_weather_zone_city_names():
    assert weather.zone_city("Europe/Rome") == "Rome"
    assert weather.zone_city("America/New_York") == "New York"


def test_weather_remembered_location(tmp_path, monkeypatch):
    import json
    import time
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert weather._located() is None
    (tmp_path / "aurora").mkdir()
    (tmp_path / "aurora" / "where.json").write_text(json.dumps(
        {"found": time.time(), "lat": 44.5, "lon": 11.3, "name": "Bologna"}))
    assert weather._located() == ((44.5, 11.3), "Bologna")
    assert weather._located(max_age=-1) is None


def test_background_recent_row_and_memory(tmp_path):
    from aurora.settingsapp import backgrounds as b
    pics = []
    for name in "abcdefgh":
        p = tmp_path / f"{name}.png"
        p.write_bytes(b"x")
        pics.append(str(p))
    assert b.remember(pics[:3], pics[1]) == [pics[1], pics[0], pics[2]]
    assert len(b.remember(pics, "new", keep=4)) == 4
    row = b.recent_row(pics[2:4], pics[5], pics, count=4)
    assert row == [pics[5], pics[2], pics[3], pics[0]]
    assert b.pretty_name("/x/my-nice_wall.jpg") == "my nice wall"
    assert b.find_wallpapers([str(tmp_path)]) == sorted(pics)


def test_verification_codes_in_notifications():
    from aurora.otp import verification_code as code
    assert code("Bank", "Your verification code is 482913. Don't share it.") == "482913"
    assert code("Il tuo codice", "Usa 123-456 per accedere") == "123456"
    assert code("G-Mail", "<b>OTP</b>: 7781") == "7781"
    assert code("Meeting", "Starts at 1530 in room 2") is None      # no code words
    assert code("Your code", "Valid until 2026") is None             # a year, not a code
    assert code("Order shipped", "Order 12345678 is on its way") is None


def test_picture_of_the_day_parsers():
    from aurora import dailypicture as d
    url, title, credit = d.parse_bing({"images": [{
        "url": "/th?id=OHR.X_1920x1080.jpg", "urlbase": "/th?id=OHR.X",
        "copyright": "Lake Bled, Slovenia (© Someone/Getty)", "title": "A calm lake"}]})
    assert url == "https://www.bing.com/th?id=OHR.X_UHD.jpg" and title == "A calm lake"
    assert "Getty" in credit
    url, title, credit = d.parse_nasa({"media_type": "image", "url": "u", "hdurl": "h",
                                       "title": "M31", "copyright": "\nJane\n"})
    assert (url, title, credit) == ("h", "M31", "© Jane")
    import pytest
    with pytest.raises(ValueError):
        d.parse_nasa({"media_type": "video", "url": "v"})
    url, title, credit = d.parse_wikimedia({"image": {
        "title": "File:A.jpg", "image": {"source": "https://up/A.jpg"},
        "description": {"text": "<i>A</i> fox"}, "artist": {"text": "<a>Ann</a>"}}})
    assert (url, title, credit) == ("https://up/A.jpg", "A fox", "© Ann")


def test_picture_of_the_day_is_kept_a_week(tmp_path, monkeypatch):
    import datetime
    import json
    from aurora import dailypicture as d
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    folder = tmp_path / "aurora" / "daily"
    folder.mkdir(parents=True)
    today = datetime.date(2026, 10, 1)
    for age in (0, 3, 9):
        day = today - datetime.timedelta(days=age)
        pic = folder / f"bing-{day}.jpg"
        pic.write_bytes(b"x")
        (folder / f"bing-{day}.json").write_text(json.dumps({"path": str(pic), "title": str(age)}))
    assert d.cached("bing", today)["title"] == "0"
    assert d.latest("bing")["title"] == "0"
    d.prune(today)
    assert not (folder / f"bing-{today - datetime.timedelta(days=9)}.jpg").exists()
    assert (folder / f"bing-{today - datetime.timedelta(days=3)}.jpg").exists()


def test_picture_of_the_day_fallbacks():
    from aurora import dailypicture as d
    page = ('<meta property="og:image" content="https://assets/x/eagle.jpg/jcr:content/'
            'renditions/web.jpeg">')
    assert d.parse_apod_page(page)[0] == "https://assets/x/eagle.jpg"
    big = "https://upload.wikimedia.org/wikipedia/commons/4/47/A.jpg?utm=1"
    assert d.commons_sized(big, 8000) == \
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/A.jpg/3840px-A.jpg"
    assert d.commons_sized(big, 2000) == "https://upload.wikimedia.org/wikipedia/commons/4/47/A.jpg"
    assert d.market("it_IT.UTF-8") == "it-IT" and d.market("C") == "en-US"


def test_storage_cleanup(tmp_path):
    import os
    import time
    from aurora import housekeeping as h
    trash = tmp_path / "Trash"
    (trash / "files").mkdir(parents=True)
    (trash / "info").mkdir()
    for name, date in (("old.txt", "2020-01-01T10:00:00"), ("new.txt", None)):
        (trash / "files" / name).write_text("x" * 5000)
        if date:
            (trash / "info" / f"{name}.trashinfo").write_text(
                f"[Trash Info]\nPath=/x/{name}\nDeletionDate={date}\n")
    assert h.tree_size(str(trash)) >= 8192
    assert h.empty_trash(older_than_days=30, trash=str(trash)) == 1
    assert sorted(os.listdir(trash / "files")) == ["new.txt"]
    assert h.empty_trash(trash=str(trash)) == 1
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "a.zip").write_text("a")
    (downloads / "b.zip").write_text("b")
    past = time.time() - 40 * 86400
    os.utime(downloads / "a.zip", (past, past))
    assert [os.path.basename(p) for p in h.old_files(str(downloads), 30)] == ["a.zip"]


def test_archive_names(tmp_path):
    from aurora.files import archives as a
    assert a.is_archive("photos.tar.xz") and a.is_archive("A.ZIP") and not a.is_archive("a.txt")
    (tmp_path / "Holiday").mkdir()
    assert a.archive_name([str(tmp_path / "Holiday")]) == "Holiday"
    assert a.archive_name([str(tmp_path / "report.pdf")]) == "report"
    assert a.archive_name([str(tmp_path / "x"), str(tmp_path / "y")]) == tmp_path.name
    (tmp_path / "Holiday.zip").write_text("")
    assert a.free_name(str(tmp_path), "Holiday", ".zip").endswith("Holiday (2).zip")


def test_volume_mixer_lists_apps_playing_sound():
    pytest = __import__("pytest")
    services = pytest.importorskip("aurora.shell.services")
    dump = [
        {"id": 40, "type": "PipeWire:Interface:Node", "info": {"props": {
            "media.class": "Audio/Sink", "node.name": "speakers"}}},
        {"id": 77, "type": "PipeWire:Interface:Node", "info": {"props": {
            "media.class": "Stream/Output/Audio", "application.name": "Firefox",
            "application.icon-name": "firefox-esr", "media.name": "YouTube"}}},
        {"id": 78, "type": "PipeWire:Interface:Node", "info": {"props": {
            "media.class": "Stream/Output/Audio", "application.process.binary": "Spotify"}}},
    ]
    got = services.app_streams(dump)
    assert [(s["id"], s["app"], s["icon"]) for s in got] == [
        (77, "Firefox", "firefox-esr"), (78, "Spotify", "spotify")]


def test_restart_after_updates():
    import datetime
    pytest = __import__("pytest")
    sn = pytest.importorskip("aurora.shell.sysnotify")
    assert sn.reboot_needed("6.12.38-amd64", ["6.12.38-amd64", "6.12.41-amd64"])
    assert not sn.reboot_needed("6.12.41-amd64", ["6.12.38-amd64", "6.12.41-amd64"])
    assert sn.reboot_needed("6.12.41-amd64", [], flag=True)
    assert sn.in_active_hours(10, 8, 23) and not sn.in_active_hours(2, 8, 23)
    assert sn.in_active_hours(23, 22, 6) and sn.in_active_hours(3, 22, 6)
    assert not sn.in_active_hours(12, 22, 6)
    now = datetime.datetime(2026, 10, 1, 15, 20)
    assert sn.next_quiet_time(now, 8, 23) == datetime.datetime(2026, 10, 1, 23, 0)
    late = datetime.datetime(2026, 10, 1, 23, 40)
    assert sn.next_quiet_time(late, 8, 23) == late


def test_screen_time(tmp_path, monkeypatch):
    import datetime
    from aurora import screentime as st
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    today = datetime.date(2026, 10, 1)
    usage = st.add(today, "firefox-esr", 600)
    usage = st.add(today, "firefox-esr", 30, usage)
    usage = st.add(today, "org.gnome.TextEditor", 120, usage)
    st.save(today, usage)
    assert st.load(today) == {"firefox-esr": 630, "org.gnome.TextEditor": 120}
    assert st.top(usage)[0] == ("firefox-esr", 630)
    days = st.week(today)
    assert len(days) == 7 and days[-1] == (today, 750) and days[0][1] == 0
    assert st.duration(30) == "< 1 min" and st.duration(3900) == "1 h 05 min"
    limits = st.limits('{"firefox-esr": 10, "x": 0, "bad": "?"}')
    assert limits == {"firefox-esr": 10}
    assert st.over_limit(usage, limits) == ["firefox-esr"]
    old = today - datetime.timedelta(days=40)
    st.save(old, {"a": 1})
    st.prune(today)
    assert st.load(old) == {} and st.load(today)


def test_image_resizer_and_file_holders(tmp_path):
    import os
    from aurora.files import imagetools as it
    assert it.fit(4000, 3000, 1920) == (1920, 1440)
    assert it.fit(800, 600, 1920) == (800, 600)
    assert it.fit(1000, 4000, 1080) == (270, 1080)
    p = str(tmp_path / "photo.jpg")
    assert it.output_path(p, "Small") == str(tmp_path / "photo (Small).jpg")
    assert it.output_path(p, "Small", "png") == str(tmp_path / "photo (Small).png")
    assert it.output_path(p, "Small", in_place=True) == p
    from gi.repository import GdkPixbuf
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 3000, 2000)
    pix.fill(0x336699ff)
    pix.savev(p, "jpeg", [], [])
    out = it.resize(p, 854, "Small")
    small = GdkPixbuf.Pixbuf.new_from_file(out)
    assert (small.get_width(), small.get_height()) == (854, 569)
    # This test's own open file shows up as held by… nobody else; a child holding it does.
    import subprocess
    holder = subprocess.Popen(["sleep", "5"], cwd=str(tmp_path))
    try:
        found = it.holders([str(tmp_path)])
        assert any(pid == holder.pid for pid, _n, _w in found)
    finally:
        holder.kill()
    assert it.holders([str(tmp_path / "nothing-here")]) == []
    assert os.path.exists(p)


def test_battery_saver_turns_on_and_off():
    pytest = __import__("pytest")
    sn = pytest.importorskip("aurora.shell.sysnotify")
    act = sn.battery_saver_action
    assert act(19, False, 20, False, False) == "on"
    assert act(25, False, 20, False, False) is None
    assert act(19, False, 20, True, True) is None          # already on
    assert act(40, True, 20, True, True) == "off"          # plugged in: we turned it on
    assert act(40, True, 20, True, False) is None          # the user chose it: leave it
    assert act(5, False, 0, False, False) is None          # never


def test_automatic_do_not_disturb():
    pytest = __import__("pytest")
    from aurora import focusassist as n
    assert pytest

    class S:
        def __init__(self, **v):
            self.v = {"dnd-schedule": False, "dnd-from": 22, "dnd-to": 7,
                      "dnd-fullscreen": True, "dnd-sharing": True, **v}
        get_boolean = get_int = lambda self, k: self.v[k]
    assert n.auto_dnd(S(), 23, False, False) is None
    assert n.auto_dnd(S(**{"dnd-schedule": True}), 23, False, False) == "schedule"
    assert n.auto_dnd(S(**{"dnd-schedule": True}), 6, False, False) == "schedule"
    assert n.auto_dnd(S(**{"dnd-schedule": True}), 12, False, False) is None
    assert n.auto_dnd(S(), 12, True, False) == "fullscreen"
    assert n.auto_dnd(S(**{"dnd-fullscreen": False}), 12, True, False) is None
    assert n.auto_dnd(S(), 12, False, True) == "sharing"


def test_spotlight_actions_paths_and_addresses(tmp_path):
    pytest = __import__("pytest")
    try:
        from aurora.shell import search
    except (ImportError, ValueError):
        pytest.skip("needs the desktop's GTK stack")
    titles = [r.title for r in search.search_actions("resta")]
    assert "Restart" in titles
    assert search.search_actions("re") == []
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Downloads").mkdir()
    (tmp_path / "notes.txt").write_text("x")
    found = [r.title for r in search.search_location(str(tmp_path) + "/Do")]
    assert found == ["Documents", "Downloads"]
    assert search.search_location(str(tmp_path))[0].path == str(tmp_path)
    assert search.search_location("github.com/padovanl")[0].subtitle == "Web address"
    assert search.search_location("hello world") == []
    assert search.search_location("10 km in mi") == []


def test_lock_key_leds(tmp_path):
    pytest = __import__("pytest")
    try:
        from aurora.shell import lockkeys
    except (ImportError, ValueError):
        pytest.skip("needs GTK")
    for name, value in (("input3::capslock", "1"), ("input3::numlock", "0"),
                        ("input9::numlock", "0")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "brightness").write_text(value + "\n")
    pattern = str(tmp_path) + "/input*::{}/brightness"
    assert lockkeys.led_states(pattern) == {"capslock": True, "numlock": False}
    assert lockkeys.message("capslock", True)[1] == "Caps Lock On"


def test_bluetooth_low_battery_warnings():
    pytest = __import__("pytest")
    sn = pytest.importorskip("aurora.shell.sysnotify")
    dev = {"path": "/h", "name": "Headphones", "connected": True, "battery": 12}
    now, warned = sn.bluetooth_warnings([dev], set())
    assert [d["name"] for d in now] == ["Headphones"] and warned == {"/h"}
    now, warned = sn.bluetooth_warnings([dict(dev, battery=10)], warned)
    assert now == []                                   # once per discharge
    now, warned = sn.bluetooth_warnings([dict(dev, battery=20)], warned)
    assert now == [] and warned == {"/h"}              # not charged enough yet
    now, warned = sn.bluetooth_warnings([dict(dev, battery=80)], warned)
    assert warned == set()
    now, _w = sn.bluetooth_warnings([dict(dev, battery=14)], warned)
    assert len(now) == 1


def test_spotlight_world_time():
    import datetime
    pytest = __import__("pytest")
    try:
        from aurora.shell import search
    except (ImportError, ValueError):
        pytest.skip("needs the desktop's GTK stack")
    assert search.find_zone("tokyo") == "Asia/Tokyo"
    assert search.find_zone("new york") == "America/New_York"
    assert search.find_zone("xy") is None
    rome = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
    city, clock, detail = search.world_time("time in Tokyo", rome)
    assert (city, clock) == ("Tokyo", "19:00") and "+7 h" in detail
    assert search.world_time("che ore sono a New York?", rome)[1] == "06:00"
    assert search.world_time("London time", rome)[1] == "11:00"
    assert search.world_time("time machine") is None


def test_hotspot_command_and_password():
    pytest = __import__("pytest")
    services = pytest.importorskip("aurora.shell.services")
    pw = services.hotspot_password()
    assert len(pw) == 10 and not set(pw) & set("0O1lI")
    cmd = services.hotspot_command("wlan0", "Desk Aurora", pw)
    assert cmd[:4] == ["nmcli", "device", "wifi", "hotspot"]
    assert cmd[cmd.index("ssid") + 1] == "Desk Aurora" and cmd[-1] == pw


def test_screen_keyboard_sends_keys():
    pytest = __import__("pytest")
    try:
        from aurora.shell import osk
    except (ImportError, ValueError):
        pytest.skip("needs gtk4-layer-shell")
    assert osk.wtype_args(None, "a") == ["wtype", "--", "a"]
    assert osk.wtype_args("BackSpace") == ["wtype", "-k", "BackSpace"]
    assert osk.wtype_args(None, "c", ctrl=True) == ["wtype", "-M", "ctrl", "-k", "c", "-m", "ctrl"]


def test_input_methods(tmp_path, monkeypatch):
    from aurora import inputmethods as im
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert im.chosen() is None
    assert im.defaults_for("zh_CN.UTF-8") == ["pinyin"] and im.defaults_for("en_US") == []
    assert im.setup(lang="en_US.UTF-8") is False and im.chosen() is None
    assert im.setup(lang="ko_KR.UTF-8", layout="kr") is True
    assert im.chosen() == ["hangul"]
    text = (tmp_path / "fcitx5" / "profile").read_text()
    assert "Name=keyboard-kr" in text and "Name=hangul" in text and "DefaultIM=hangul" in text
    im.save([])
    assert im.setup(lang="ko_KR.UTF-8") is False      # turned off by hand: stays off


def test_input_methods_stay_private(tmp_path):
    from aurora import inputmethods as im
    path = tmp_path / "config"
    im.ensure_private(str(path))
    assert "[Behavior/DisabledAddons]\n0=cloudpinyin" in path.read_text()
    path.write_text("[Hotkey]\nX=1\n\n[Behavior/DisabledAddons]\n0=clipboard\n\n[Behavior]\nY=2\n")
    im.ensure_private(str(path))
    text = path.read_text()
    assert "0=clipboard\n1=cloudpinyin" in text and "X=1" in text and "Y=2" in text
    im.ensure_private(str(path))
    assert path.read_text().count("cloudpinyin") == 1


def test_input_methods_keep_every_layout(tmp_path, monkeypatch):
    from aurora import inputmethods as im
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "labwc").mkdir()
    (tmp_path / "labwc" / "environment").write_text("XKB_DEFAULT_LAYOUT=it,us\n")
    assert im.chosen_layouts() == "it,us"
    im.save(["pinyin"])
    text = (tmp_path / "fcitx5" / "profile").read_text()
    assert "Default Layout=it" in text
    assert text.index("keyboard-it") < text.index("keyboard-us") < text.index("Name=pinyin")
