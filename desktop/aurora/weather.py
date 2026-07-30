"""Current weather and today's forecast for the calendar popover.

Data comes from Open-Meteo (open-meteo.com): free, no account or API key.
The location is the time zone's reference city (see aurora.sun), so only an
approximate position is ever sent. Results are cached for 30 minutes, and the
widget can be turned off in Settings → Privacy.
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


def cached(lat, lon, max_age=MAX_AGE):
    try:
        with open(cache_path()) as f:
            data = json.load(f)
        if time.time() - data["fetched"] > max_age or data["where"] != [round(lat, 2),
                                                                           round(lon, 2)]:
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


def uses_fahrenheit(loc=None):
    """The US (and a few others) use Fahrenheit."""
    import locale
    loc = loc or locale.getlocale(locale.LC_MEASUREMENT if hasattr(locale, "LC_MEASUREMENT")
                                  else locale.LC_CTYPE)[0] or os.environ.get("LANG", "")
    return any(loc.startswith(p) for p in ("en_US", "en_LR", "my_MM"))
