"""Unit and currency conversion for Spotlight: "10 km in mi", "100 usd to eur".

Units are converted offline. Currency rates come from the European Central
Bank's daily reference rates (a public XML file, no account or key), fetched
only when someone types a currency conversion and cached for 12 hours.
"""

import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
RATES_MAX_AGE = 12 * 3600

# unit -> (dimension, factor to the base unit). Temperatures are special-cased.
UNITS = {}


def _add(dimension, factor, *names):
    for n in names:
        UNITS[n] = (dimension, factor)


_add("length", 1, "m", "meter", "meters", "metre", "metres")
_add("length", 1000, "km", "kilometer", "kilometers", "kilometre", "kilometres")
_add("length", 0.01, "cm", "centimeter", "centimeters")
_add("length", 0.001, "mm", "millimeter", "millimeters")
_add("length", 0.0254, "in", "inch", "inches", '"')
_add("length", 0.3048, "ft", "foot", "feet", "'")
_add("length", 0.9144, "yd", "yard", "yards")
_add("length", 1609.344, "mi", "mile", "miles")
_add("length", 1852, "nmi", "nautical")
_add("mass", 1, "kg", "kilogram", "kilograms", "kilo", "kilos")
_add("mass", 0.001, "g", "gram", "grams")
_add("mass", 1e-6, "mg", "milligram", "milligrams")
_add("mass", 1000, "t", "tonne", "tonnes", "ton")
_add("mass", 0.45359237, "lb", "lbs", "pound", "pounds")
_add("mass", 0.028349523125, "oz", "ounce", "ounces")
_add("mass", 6.35029318, "st", "stone")
_add("volume", 1, "l", "liter", "liters", "litre", "litres")
_add("volume", 0.001, "ml", "milliliter", "milliliters")
_add("volume", 0.01, "cl")
_add("volume", 3.785411784, "gal", "gallon", "gallons")
_add("volume", 0.946352946, "qt", "quart", "quarts")
_add("volume", 0.2365882365, "cup", "cups")
_add("volume", 0.0295735295625, "floz")
_add("time", 1, "s", "sec", "second", "seconds")
_add("time", 0.001, "ms", "millisecond", "milliseconds")
_add("time", 60, "min", "minute", "minutes")
_add("time", 3600, "h", "hr", "hour", "hours")
_add("time", 86400, "d", "day", "days")
_add("time", 604800, "wk", "week", "weeks")
_add("time", 31557600, "yr", "year", "years")
_add("speed", 1, "m/s", "mps")
_add("speed", 1 / 3.6, "km/h", "kmh", "kph")
_add("speed", 0.44704, "mph")
_add("speed", 0.514444, "kn", "knot", "knots")
_add("data", 1, "b", "byte", "bytes")
_add("data", 1 / 8, "bit", "bits")
for i, prefix in enumerate(("k", "m", "g", "t", "p"), start=1):
    _add("data", 1000 ** i, f"{prefix}b")
    _add("data", 1024 ** i, f"{prefix}ib")
    _add("data", 1000 ** i / 8, f"{prefix}bit")
_add("area", 1, "m2", "m²", "sqm")
_add("area", 1e6, "km2", "km²")
_add("area", 10000, "ha", "hectare", "hectares")
_add("area", 4046.8564224, "acre", "acres")
_add("area", 0.09290304, "ft2", "ft²", "sqft")
_add("energy", 1, "j", "joule", "joules")
_add("energy", 1000, "kj")
_add("energy", 4184, "kcal")
_add("energy", 3.6e6, "kwh")

TEMPERATURES = {"c": "C", "°c": "C", "celsius": "C", "f": "F", "°f": "F",
                "fahrenheit": "F", "k": "K", "kelvin": "K"}

CURRENCIES = {"eur", "usd", "jpy", "bgn", "czk", "dkk", "gbp", "huf", "pln", "ron", "sek",
              "chf", "isk", "nok", "try", "aud", "brl", "cad", "cny", "hkd", "idr", "ils",
              "inr", "krw", "mxn", "myr", "nzd", "php", "sgd", "thb", "zar"}
CURRENCY_SYMBOLS = {"€": "eur", "$": "usd", "£": "gbp", "¥": "jpy", "₹": "inr", "₩": "krw"}

QUERY = re.compile(
    r"^\s*(?P<num>[-+]?\d+(?:[.,]\d+)?)\s*(?P<from>[^\s\d]+?)\s+(?:in|to|as|into|=)\s+"
    r"(?P<to>\S+)\s*$", re.I)
SYMBOL_QUERY = re.compile(r"^\s*(?P<sym>[€$£¥₹₩])\s*(?P<num>\d+(?:[.,]\d+)?)\s+"
                          r"(?:in|to)\s+(?P<to>\S+)\s*$", re.I)


def parse(query):
    """(value, from_unit, to_unit) in lower case, or None."""
    m = SYMBOL_QUERY.match(query)
    if m:
        return float(m["num"].replace(",", ".")), CURRENCY_SYMBOLS[m["sym"]], m["to"].lower()
    m = QUERY.match(query)
    if not m:
        return None
    frm = m["from"].lower()
    frm = CURRENCY_SYMBOLS.get(frm, frm)
    to = m["to"].lower()
    to = CURRENCY_SYMBOLS.get(to, to)
    return float(m["num"].replace(",", ".")), frm, to


def _temperature(value, frm, to):
    c = {"C": value, "F": (value - 32) * 5 / 9, "K": value - 273.15}[frm]
    return {"C": c, "F": c * 9 / 5 + 32, "K": c + 273.15}[to]


def convert_units(value, frm, to):
    """Convert between units of the same kind; None if they don't match."""
    if frm in TEMPERATURES and to in TEMPERATURES:
        return _temperature(value, TEMPERATURES[frm], TEMPERATURES[to])
    a, b = UNITS.get(frm), UNITS.get(to)
    if a is None or b is None or a[0] != b[0]:
        return None
    return value * a[1] / b[1]


def is_currency(frm, to):
    return frm in CURRENCIES and to in CURRENCIES


def rates_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "aurora", "rates.json")


def cached_rates(max_age=RATES_MAX_AGE):
    """{currency: units per euro} from the cache, or None if missing or old."""
    try:
        with open(rates_path()) as f:
            data = json.load(f)
        if time.time() - data["fetched"] > max_age:
            return None
        return data["rates"]
    except (OSError, ValueError, KeyError):
        return None


def parse_ecb(xml_bytes):
    rates = {"eur": 1.0}
    for el in ET.fromstring(xml_bytes).iter():
        if el.tag.endswith("Cube") and "currency" in el.attrib:
            rates[el.attrib["currency"].lower()] = float(el.attrib["rate"])
    return rates


def fetch_rates(timeout=5):
    """Download today's rates and cache them. Blocking: call from a thread."""
    with urllib.request.urlopen(ECB_URL, timeout=timeout) as resp:
        rates = parse_ecb(resp.read())
    path = rates_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"fetched": time.time(), "rates": rates}, f)
    return rates


def convert_currency(value, frm, to, rates):
    if frm not in rates or to not in rates:
        return None
    return value / rates[frm] * rates[to]


def format_number(x):
    if abs(x) >= 1e15 or (x != 0 and abs(x) < 1e-6):
        return f"{x:.6g}"
    text = f"{x:,.6f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"
