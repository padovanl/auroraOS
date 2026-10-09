"""Launchpad's sections: the apps you use most, then every app by what it's for,
with the system's tools last under Utilities."""

import datetime

from aurora.i18n import N_

# (title, freedesktop categories), in the order Launchpad shows them; an app
# goes to the first one it matches.
SECTIONS = (
    (N_("Internet"), {"WebBrowser", "Email", "Chat", "InstantMessaging", "Network"}),
    (N_("Office"), {"Office", "WordProcessor", "Spreadsheet", "Presentation", "Calendar",
                    "ContactManagement"}),
    (N_("Photos, Music & Video"), {"Graphics", "Photography", "AudioVideo", "Audio",
                                   "Video", "Player"}),
    (N_("Games"), {"Game"}),
    (N_("Development"), {"Development", "IDE"}),
)
UTILITIES = N_("Utilities")
# Network tools that are utilities, not what people mean by "Internet".
TOOLS = {"System", "Settings", "Monitor", "PackageManager", "HardwareSettings"}


def section_of(categories):
    cats = set(c for c in (categories or "").split(";") if c)
    for title, wanted in SECTIONS:
        if cats & wanted and not (title == SECTIONS[0][0] and cats & TOOLS):
            return title
    return UTILITIES


def group(apps):
    """{section title: [apps]} for AppInfos, sections in Launchpad's order."""
    out = {title: [] for title, _w in SECTIONS}
    out[UTILITIES] = []
    for app in apps:
        cats = app.get_categories() if hasattr(app, "get_categories") else ""
        out[section_of(cats)].append(app)
    for members in out.values():
        members.sort(key=lambda a: (a.get_display_name() or "").casefold())
    return {k: v for k, v in out.items() if v}


def frequent(apps, n=6, today=None):
    """The apps used most this week (Screen Time), most first."""
    from aurora import screentime
    today = today or datetime.date.today()
    totals = {}
    for i in range(7):
        for app_id, seconds in screentime.load(today - datetime.timedelta(days=i)).items():
            totals[app_id] = totals.get(app_id, 0) + seconds
    from aurora import apps as applib
    shown = {app.get_id(): app for app in apps}
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for app_id, _s in ranked:
        info = applib.find_app(app_id)
        app = shown.get(info.get_id()) if info is not None else None
        if app is not None and app not in out:
            out.append(app)
        if len(out) == n:
            break
    return out
