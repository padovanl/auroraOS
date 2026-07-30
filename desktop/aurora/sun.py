"""Where the sun is, without the network or a location service.

The location comes from the system time zone: tzdata lists coordinates for
every zone (zone1970.tab), which is close enough for sunrise and sunset
(minutes of error, not hours). The sun position uses the NOAA formulas.

Used by the dynamic wallpaper, automatic dark style and Night Light.
"""

import datetime
import math
import os

ZONE_TABLES = ("/usr/share/zoneinfo/zone1970.tab", "/usr/share/zoneinfo/zone.tab")


def _parse_coord(text):
    """ISO 6709 '+4154+01227' or '+415402+0122705' → (lat, lon) in degrees."""
    split = max(text.rfind("+"), text.rfind("-"))
    lat, lon = text[:split], text[split:]

    def conv(part, deg_digits):
        sign = -1 if part[0] == "-" else 1
        digits = part[1:]
        deg = int(digits[:deg_digits])
        rest = digits[deg_digits:]
        minutes = int(rest[:2]) if rest else 0
        seconds = int(rest[2:4]) if len(rest) > 2 else 0
        return sign * (deg + minutes / 60 + seconds / 3600)
    return conv(lat, 2), conv(lon, 3)


def local_timezone():
    tz = os.environ.get("TZ", "").lstrip(":")
    if tz:
        return tz
    try:
        link = os.readlink("/etc/localtime")
        return link.split("zoneinfo/", 1)[1]
    except (OSError, IndexError):
        pass
    try:
        with open("/etc/timezone") as f:
            return f.read().strip()
    except OSError:
        return "UTC"


def location(tz=None):
    """(latitude, longitude) of the time zone's reference city, or None."""
    tz = tz or local_timezone()
    for table in ZONE_TABLES:
        try:
            with open(table) as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    cols = line.rstrip("\n").split("\t")
                    if len(cols) >= 3 and cols[2] == tz:
                        return _parse_coord(cols[1])
        except OSError:
            continue
    return None


def elevation(lat, lon, when):
    """Solar elevation in degrees at an aware datetime."""
    utc = when.astimezone(datetime.timezone.utc)
    day = utc.timetuple().tm_yday
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    g = 2 * math.pi / 365 * (day - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    solar_minutes = hour * 60 + eqtime + 4 * lon
    ha = math.radians(solar_minutes / 4 - 180)
    phi = math.radians(lat)
    cos_zenith = (math.sin(phi) * math.sin(decl)
                  + math.cos(phi) * math.cos(decl) * math.cos(ha))
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))


def sun_times(lat, lon, date, tzinfo):
    """(sunrise, sunset) as aware datetimes in tzinfo, or None in polar day/night."""
    start = datetime.datetime(date.year, date.month, date.day, tzinfo=tzinfo)
    samples = [(start + datetime.timedelta(minutes=m)) for m in range(0, 24 * 60 + 1, 10)]
    elev = [elevation(lat, lon, t) for t in samples]
    rise = set_ = None
    for i in range(1, len(samples)):
        a, b = elev[i - 1], elev[i]
        if a < -0.833 <= b and rise is None:
            rise = samples[i - 1] + (samples[i] - samples[i - 1]) * ((-0.833 - a) / (b - a))
        if a >= -0.833 > b:
            set_ = samples[i - 1] + (samples[i] - samples[i - 1]) * ((a + 0.833) / (a - b))
    if rise is None or set_ is None:
        return None
    return rise, set_


def phase(when=None, loc=None):
    """The part of the day: 'night', 'dawn', 'day' or 'dusk'."""
    when = when or datetime.datetime.now().astimezone()
    loc = loc or location()
    if loc is None:
        # No coordinates: a sensible clock-based fallback.
        h = when.hour
        return "night" if h < 6 or h >= 21 else "dawn" if h < 9 else "day" if h < 18 else "dusk"
    e = elevation(loc[0], loc[1], when)
    if e < -6:
        return "night"
    if e < 8:
        return "dawn" if when.hour < 12 else "dusk"
    return "day"


def is_dark(when=None, loc=None):
    """True between sunset and sunrise."""
    when = when or datetime.datetime.now().astimezone()
    loc = loc or location()
    if loc is None:
        return when.hour < 7 or when.hour >= 19
    return elevation(loc[0], loc[1], when) < -0.833
