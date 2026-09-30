"""A new background every day, from a well-known picture of the day.

Bing's photo of the day, NASA's Astronomy Picture of the Day and Wikimedia
Commons' Picture of the Day. Only a request for today's picture goes out: no
account, no location. The pictures are kept for a week in
~/.local/share/aurora/daily, with their title and credit.
"""

import datetime
import json
import os
import re
import urllib.parse
import urllib.request

from aurora.i18n import N_

SOURCES = {
    "bing": N_("Bing: photo of the day"),
    "nasa": N_("NASA: astronomy picture of the day"),
    "wikimedia": N_("Wikimedia Commons: picture of the day"),
}
KEEP_DAYS = 7
AGENT = "AuroraOS/0.1 (https://github.com/padovanl/auroraOS; daily wallpaper)"


def folder():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "aurora", "daily")


def info_path(source, day):
    return os.path.join(folder(), f"{source}-{day.isoformat()}.json")


def _get(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


# --- each source: today's (image url, title, credit) -----------------------------

def parse_bing(payload):
    image = payload["images"][0]
    base = image.get("urlbase")
    url = "https://www.bing.com" + (f"{base}_UHD.jpg" if base else image["url"])
    credit = image.get("copyright", "")
    title = image.get("title") or re.sub(r"\s*\(©.*\)$", "", credit)
    return url, title, credit


def parse_nasa(payload):
    if payload.get("media_type") != "image":
        raise ValueError("today's APOD is not a picture")
    url = payload.get("hdurl") or payload["url"]
    credit = payload.get("copyright", "NASA").strip().replace("\n", " ")
    return url, payload.get("title", ""), f"© {credit}" if credit != "NASA" else "NASA"


def commons_sized(url, width, max_width=3840):
    """A Commons original can be 50 MB: ask for a screen-sized copy instead."""
    url = url.split("?", 1)[0]
    marker = "/wikipedia/commons/"
    if not width or width <= max_width or marker not in url or "/thumb/" in url:
        return url
    head, tail = url.split(marker, 1)
    name = tail.rsplit("/", 1)[-1]
    return f"{head}{marker}thumb/{tail}/{max_width}px-{name}"


def parse_wikimedia(payload):
    image = payload["image"]
    original = image.get("image") or image["thumbnail"]
    url = commons_sized(original["source"], original.get("width", 0))
    description = (image.get("description") or {}).get("text", "")
    title = re.sub(r"<[^>]+>", "", description).strip() or image.get("title", "")
    artist = re.sub(r"<[^>]+>", "", (image.get("artist") or {}).get("text", "")).strip()
    return url, title[:160], artist and f"© {artist}"


def parse_apod_page(html):
    """APOD's page on science.nasa.gov, when the API is down: its picture
    (the original, not the 1280-pixel rendition)."""
    match = re.search(r'<meta property="og:image" content="([^"]+)"', html, re.I)
    if not match:
        raise ValueError("no APOD picture found")
    url = match.group(1).split("/jcr:content/", 1)[0]
    if not url.lower().endswith((".jpg", ".jpeg", ".png")):
        raise ValueError("today's APOD is not a picture")
    title = re.search(r'<meta property="og:description" content="([^"]+)"', html, re.I)
    return url, title.group(1)[:160] if title else "", "NASA"


def market(lang=None):
    """Bing's market from the language: it_IT.UTF-8 → it-IT."""
    lang = (lang or os.environ.get("LANG") or "en_US").split(".")[0]
    return lang.replace("_", "-") if "_" in lang else "en-US"


def today_url(source, day):
    if source == "bing":
        payload = json.loads(_get("https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1"
                                  f"&mkt={market()}"))
        return parse_bing(payload)
    if source == "nasa":
        try:
            payload = json.loads(_get("https://api.nasa.gov/planetary/apod"
                                      "?api_key=DEMO_KEY&thumbs=false"))
            return parse_nasa(payload)
        except (OSError, ValueError, KeyError):
            return parse_apod_page(_get("https://science.nasa.gov/apod/")
                                   .decode("utf-8", "replace"))
    if source == "wikimedia":
        payload = json.loads(_get("https://api.wikimedia.org/feed/v1/wikipedia/en/featured/"
                                  f"{day:%Y/%m/%d}"))
        return parse_wikimedia(payload)
    raise ValueError(f"unknown source {source}")


# --- fetching and remembering ------------------------------------------------------

def cached(source, day=None):
    """Today's picture if already here: {"path", "title", "credit"} or None."""
    day = day or datetime.date.today()
    try:
        with open(info_path(source, day)) as f:
            info = json.load(f)
        return info if os.path.isfile(info.get("path", "")) else None
    except (OSError, ValueError):
        return None


def latest(source):
    """The newest picture from this source that's here, however old."""
    try:
        names = sorted((n for n in os.listdir(folder())
                        if n.startswith(source + "-") and n.endswith(".json")), reverse=True)
    except OSError:
        return None
    for name in names:
        try:
            with open(os.path.join(folder(), name)) as f:
                info = json.load(f)
            if os.path.isfile(info.get("path", "")):
                return info
        except (OSError, ValueError):
            continue
    return None


def fetch(source, day=None):
    """Download today's picture (blocking: call from a thread)."""
    day = day or datetime.date.today()
    found = cached(source, day)
    if found:
        return found
    url, title, credit = today_url(source, day)
    extension = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp"):
        extension = ".jpg"
    os.makedirs(folder(), exist_ok=True)
    path = os.path.join(folder(), f"{source}-{day.isoformat()}{extension}")
    data = _get(url, timeout=60)
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    info = {"path": path, "title": title, "credit": credit, "source": source,
            "day": day.isoformat()}
    with open(info_path(source, day), "w") as f:
        json.dump(info, f)
    prune(day)
    return info


def prune(today, keep=KEEP_DAYS):
    """Forget pictures older than a week."""
    try:
        names = os.listdir(folder())
    except OSError:
        return
    for name in names:
        match = re.search(r"-(\d{4}-\d{2}-\d{2})\.", name)
        if match and (today - datetime.date.fromisoformat(match.group(1))).days > keep:
            try:
                os.remove(os.path.join(folder(), name))
            except OSError:
                pass
