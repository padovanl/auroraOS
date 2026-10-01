"""Screen time, like Android's Digital Wellbeing and iPhone's Screen Time: how
long each app was in front of you, per day.

The shell adds time to the app whose window is focused, only while the screen
is unlocked and you're active. One small JSON file per day in
~/.local/share/aurora/screentime; nothing leaves the computer. Days older than
five weeks are forgotten.
"""

import datetime
import json
import os

KEEP_DAYS = 35


def folder():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "aurora", "screentime")


def day_path(day):
    return os.path.join(folder(), f"{day.isoformat()}.json")


def load(day):
    """{app id: seconds} for a day."""
    try:
        with open(day_path(day)) as f:
            data = json.load(f)
        return {str(k): int(v) for k, v in data.items() if isinstance(v, (int, float))}
    except (OSError, ValueError, AttributeError):
        return {}


def save(day, usage):
    os.makedirs(folder(), exist_ok=True)
    tmp = day_path(day) + ".new"
    with open(tmp, "w") as f:
        json.dump(usage, f)
    os.replace(tmp, day_path(day))


def add(day, app_id, seconds, usage=None):
    """Add time to an app; returns the day's usage."""
    usage = load(day) if usage is None else usage
    if app_id and seconds > 0:
        usage[app_id] = usage.get(app_id, 0) + int(seconds)
    return usage


def week(today):
    """[(day, total seconds)] for the last seven days, oldest first."""
    days = [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    return [(d, sum(load(d).values())) for d in days]


def top(usage, n=None):
    """Apps by time, most first."""
    ranked = sorted(usage.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:n] if n else ranked


def prune(today, keep=KEEP_DAYS):
    try:
        names = os.listdir(folder())
    except OSError:
        return
    for name in names:
        try:
            day = datetime.date.fromisoformat(name.removesuffix(".json"))
        except ValueError:
            continue
        if (today - day).days > keep:
            try:
                os.remove(os.path.join(folder(), name))
            except OSError:
                pass


def clear():
    try:
        for name in os.listdir(folder()):
            os.remove(os.path.join(folder(), name))
    except OSError:
        pass


def duration(seconds):
    """"2 h 05 min", "35 min", "< 1 min"."""
    minutes = int(seconds) // 60
    if minutes < 1:
        return "< 1 min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def limits(text):
    """{app id: minutes} from the settings' JSON."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return {}
    out = {}
    for key, value in (data.items() if isinstance(data, dict) else []):
        try:
            if int(value) > 0:
                out[str(key)] = int(value)
        except (ValueError, TypeError):
            continue
    return out


def over_limit(usage, app_limits):
    """Apps past their daily limit today."""
    return [app for app, minutes in app_limits.items() if usage.get(app, 0) >= minutes * 60]
