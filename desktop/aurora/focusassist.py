"""Automatic Do Not Disturb (Settings → Notifications), like Windows' Focus Assist."""


def auto_dnd(s, hour, fullscreen, sharing):
    """Why Do Not Disturb is on by itself right now (a reason), or None:
    Windows' Focus Assist rules."""
    if s is None:
        return None
    if s.get_boolean("dnd-schedule"):
        start, end = s.get_int("dnd-from"), s.get_int("dnd-to")
        inside = start <= hour < end if start < end else (hour >= start or hour < end)
        if start != end and inside:
            return "schedule"
    if fullscreen and s.get_boolean("dnd-fullscreen"):
        return "fullscreen"
    if sharing and s.get_boolean("dnd-sharing"):
        return "sharing"
    return None
