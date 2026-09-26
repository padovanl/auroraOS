"""Current weather and today's forecast for the calendar popover.

Data comes from Open-Meteo (open-meteo.com): free, no account or API key.
The place follows GNOME Weather: the city picked there first, else the
automatic location it also uses (GeoClue, rounded to about 10 km), else the
time zone's reference city (see aurora.sun). Only that approximate position is
ever sent. Results are cached for 30 minutes, and the widget can be turned off
in Settings → Privacy.
"""

import json
import os
import time
import urllib.parse
import urllib.request

from aurora.i18n import N_

API = "https://api.open-meteo.com/v1/forecast"
MAX_AGE = 30 * 60

# WMO weather codes → (description, icon name without the -symbolic suffix)
CODES = {
    0: (N_("Clear sky"), "weather-clear"),
    1: (N_("Mainly clear"), "weather-few-clouds"),
    2: (N_("Partly cloudy"), "weather-few-clouds"),
    3: (N_("Overcast"), "weather-overcast"),
    45: (N_("Fog"), "weather-fog"), 48: (N_("Fog"), "weather-fog"),
    51: (N_("Light drizzle"), "weather-showers-scattered"),
    53: (N_("Drizzle"), "weather-showers-scattered"),
    55: (N_("Heavy drizzle"), "weather-showers"),
    56: (N_("Freezing drizzle"), "weather-showers"), 57: (N_("Freezing drizzle"), "weather-showers"),
    61: (N_("Light rain"), "weather-showers-scattered"), 63: (N_("Rain"), "weather-showers"),
    65: (N_("Heavy rain"), "weather-showers"),
    66: (N_("Freezing rain"), "weather-showers"), 67: (N_("Freezing rain"), "weather-showers"),
    71: (N_("Light snow"), "weather-snow"), 73: (N_("Snow"), "weather-snow"),
    75: (N_("Heavy snow"), "weather-snow"), 77: (N_("Snow grains"), "weather-snow"),
    80: (N_("Rain showers"), "weather-showers-scattered"), 81: (N_("Rain showers"), "weather-showers"),
    82: (N_("Violent rain showers"), "weather-showers"),
    85: (N_("Snow showers"), "weather-snow"), 86: (N_("Snow showers"), "weather-snow"),
    95: (N_("Thunderstorm"), "weather-storm"), 96: (N_("Thunderstorm with hail"), "weather-storm"),
    99: (N_("Thunderstorm with hail"), "weather-storm"),
}
NIGHT_ICONS = {"weather-clear": "weather-clear-night",
               "weather-few-clouds": "weather-few-clouds-night"}


def describe(code, is_day=True):
    text, icon = CODES.get(code, (N_("Unknown"), "weather-severe-alert"))
    if not is_day:
        icon = NIGHT_ICONS.get(icon, icon)
    return text, icon + "-symbolic"


def cache_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aurora", "weather.json")


def cached(lat, lon, max_age=MAX_AGE, fahrenheit=None):
    try:
        with open(cache_path()) as f:
            data = json.load(f)
        if time.time() - data["fetched"] > max_age or data["where"] != [round(lat, 2),
                                                                           round(lon, 2)]:
            return None
        if fahrenheit is not None and (data["weather"].get("unit") == "°F") != fahrenheit:
            return None
        return data["weather"]
    except (OSError, ValueError, KeyError):
        return None


def parse(payload):
    """Open-Meteo JSON → {temp, code, is_day, high, low, unit, hours: [(hour, temp, code)]}."""
    cur = payload["current"]
    daily = payload["daily"]
    hourly = payload.get("hourly", {})
    now_hour = cur["time"][:13]
    hours = []
    times = hourly.get("time", [])
    start = next((i for i, t in enumerate(times) if t[:13] >= now_hour), 0)
    for i in range(start + 1, min(start + 13, len(times)), 3):
        hours.append((times[i][11:16], hourly["temperature_2m"][i], hourly["weather_code"][i]))
    return {
        "temp": cur["temperature_2m"], "code": cur["weather_code"],
        "is_day": bool(cur.get("is_day", 1)),
        "high": daily["temperature_2m_max"][0], "low": daily["temperature_2m_min"][0],
        "unit": payload.get("current_units", {}).get("temperature_2m", "°C"),
        "hours": hours,
    }


def fetch(lat, lon, fahrenheit=False, timeout=6):
    """Download and cache the weather. Blocking: call from a thread."""
    query = urllib.parse.urlencode({
        "latitude": f"{lat:.2f}", "longitude": f"{lon:.2f}",
        "current": "temperature_2m,weather_code,is_day",
        "hourly": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto", "forecast_days": 2,
        "temperature_unit": "fahrenheit" if fahrenheit else "celsius",
    })
    with urllib.request.urlopen(f"{API}?{query}", timeout=timeout) as resp:
        weather = parse(json.load(resp))
    path = cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"fetched": time.time(), "where": [round(lat, 2), round(lon, 2)],
                   "weather": weather}, f)
    return weather


def measurement_locale(env=None):
    """The locale that picks units, by glibc's rule: LC_ALL, then LC_MEASUREMENT,
    then LANG. (Python has no locale.LC_MEASUREMENT, and the text locale can
    differ: English text with Italian formats is common.)"""
    env = os.environ if env is None else env
    for name in ("LC_ALL", "LC_MEASUREMENT", "LANG"):
        if env.get(name):
            return env[name]
    return ""


def uses_fahrenheit(loc=None):
    """Follow the same GWeather unit preference used by GNOME Weather."""
    from gi.repository import Gio
    source = Gio.SettingsSchemaSource.get_default()
    if source is not None and source.lookup("org.gnome.GWeather4", True) is not None:
        choice = Gio.Settings.new("org.gnome.GWeather4").get_string("temperature-unit")
        if choice in ("fahrenheit", "centigrade", "kelvin"):
            return choice == "fahrenheit"
    loc = loc or measurement_locale()
    return any(loc.startswith(p) for p in ("en_US", "en_LR", "my_MM"))


def _saved_city():
    """(coords, name) of the first city chosen in the Weather app, or None."""
    try:
        import gi
        gi.require_version("GWeather", "4.0")
        from gi.repository import Gio, GWeather
        places = Gio.Settings.new("org.gnome.Weather").get_value("locations")
        if places.n_children():
            chosen = GWeather.Location.get_world().deserialize(
                places.get_child_value(0).get_variant())
            if chosen is not None and chosen.has_coords():
                return tuple(chosen.get_coords()), chosen.get_city_name() or chosen.get_name()
    except Exception:  # noqa: BLE001 - no GWeather or no chosen city
        pass
    return None


def where_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aurora", "where.json")


WHERE_MAX_AGE = 6 * 3600


def _located(max_age=WHERE_MAX_AGE):
    """The automatic location found by locate(), if recent: (coords, name) or None."""
    try:
        with open(where_path()) as f:
            data = json.load(f)
        if time.time() - data["found"] > max_age:
            return None
        return (data["lat"], data["lon"]), data.get("name")
    except (OSError, ValueError, KeyError, TypeError):
        return None


def nearest_city(lat, lon):
    try:
        import gi
        gi.require_version("GWeather", "4.0")
        from gi.repository import GWeather
        city = GWeather.Location.get_world().find_nearest_city(lat, lon)
        return city.get_city_name() or city.get_name() if city else None
    except Exception:  # noqa: BLE001
        return None


def locate(timeout=20):
    """Ask GeoClue where we are, as GNOME Weather does, and remember it (rounded
    to about 10 km) for place(). Blocking: call from a thread. True if found."""
    try:
        import gi
        gi.require_version("Geoclue", "2.0")
        from gi.repository import Gio, Geoclue
        cancel = Gio.Cancellable()
        import threading
        timer = threading.Timer(timeout, cancel.cancel)
        timer.start()
        try:
            simple = Geoclue.Simple.new_sync("aurora-shell", Geoclue.AccuracyLevel.CITY, cancel)
        finally:
            timer.cancel()
        loc = simple.get_location()
        lat, lon = round(loc.props.latitude, 1), round(loc.props.longitude, 1)
    except Exception as e:  # noqa: BLE001 - no GeoClue, no network, denied
        print(f"aurora: no automatic location: {e}")
        return False
    path = where_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"found": time.time(), "lat": lat, "lon": lon,
                   "name": nearest_city(lat, lon)}, f)
    return True


def needs_locating():
    return _saved_city() is None and _located() is None


_waiting = []
_last_try = [0.0]


def locate_then(callback):
    """Run locate() in a thread when the place isn't known yet (one search at a
    time, at most every 10 minutes), then call callback() on the main loop."""
    if not needs_locating():
        return
    _waiting.append(callback)
    if len(_waiting) > 1 or time.time() - _last_try[0] < 600:
        if len(_waiting) == 1:
            _waiting.clear()
        return
    _last_try[0] = time.time()
    import threading
    from gi.repository import GLib

    def done(found):
        callbacks = list(_waiting)
        _waiting.clear()
        if found:
            for cb in callbacks:
                cb()
        return False

    threading.Thread(target=lambda: GLib.idle_add(done, locate()), daemon=True).start()


def zone_city(tz=None):
    """"Europe/Rome" → "Rome"."""
    from aurora import sun
    tz = tz or sun.local_timezone() or ""
    return tz.rsplit("/", 1)[-1].replace("_", " ") or None


def place():
    """((latitude, longitude), city name or None) for the forecast, in GNOME
    Weather's order: the city chosen there, else the automatic location, else
    the time zone's reference city."""
    from aurora import sun
    found = _saved_city() or _located(max_age=30 * 24 * 3600)
    if found:
        return found
    loc = sun.location()
    return loc, (zone_city() if loc else None)


def watch(callback):
    """Call callback() when the chosen city or the unit changes. Keep the
    result, and pass it to unwatch() when done."""
    from gi.repository import Gio
    kept = []
    source = Gio.SettingsSchemaSource.get_default()
    for schema, key in (("org.gnome.Weather", "locations"),
                        ("org.gnome.GWeather4", "temperature-unit")):
        if source is not None and source.lookup(schema, True) is not None:
            s = Gio.Settings.new(schema)
            kept.append((s, s.connect(f"changed::{key}", lambda *_a: callback())))
    return kept


def unwatch(kept):
    for s, handler in kept:
        s.disconnect(handler)
    kept.clear()
