"""Launchpad's folders and pages.

A folder is a name and a list of desktop ids, kept in one GSettings string so
it survives a reinstall of the apps inside it. Everything here is about lists,
not widgets: what the grid shows, in what order, cut into pages.

An id in a folder whose app is no longer installed is remembered rather than
dropped — reinstalling the app puts it back where it was — but it is never
shown, so a folder of three apps with two uninstalled looks like a folder of
one, and empties itself only when the last one goes.
"""

import json

MIN_PER_PAGE = 8


def load(text):
    """[{"name": str, "apps": [id, …]}] from what GSettings holds, ignoring
    anything that is not that, because a hand-edited value must not stop
    Launchpad from opening."""
    try:
        raw = json.loads(text or "[]")
    except ValueError:
        return []
    folders = []
    if not isinstance(raw, list):
        return []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        apps = item.get("apps")
        if not isinstance(name, str) or not isinstance(apps, list):
            continue
        ids = [app for app in apps if isinstance(app, str) and app]
        if ids:
            folders.append({"name": name.strip() or "Folder", "apps": list(dict.fromkeys(ids))})
    return folders


def dump(folders):
    return json.dumps([{"name": f["name"], "apps": f["apps"]} for f in folders],
                      ensure_ascii=False)


def folder_of(folders, app_id):
    """The folder holding an app, or None."""
    for folder in folders:
        if app_id in folder["apps"]:
            return folder
    return None


def arrange(apps, folders):
    """What the grid shows, in order: ("app", app) and ("folder", folder, [apps]).

    A folder takes the place of its first member, so making one out of two
    tiles leaves the folder where they were rather than at the end."""
    by_id = {}
    for app in apps:
        app_id = app.get_id() if hasattr(app, "get_id") else str(app)
        by_id.setdefault(app_id, app)
    placed = set()
    items = []
    for app in apps:
        app_id = app.get_id() if hasattr(app, "get_id") else str(app)
        folder = folder_of(folders, app_id)
        if folder is None:
            items.append(("app", app))
            continue
        name = folder["name"]
        if name in placed:
            continue
        members = [by_id[i] for i in folder["apps"] if i in by_id]
        if not members:
            continue
        placed.add(name)
        items.append(("folder", folder, members))
    return items


def put_together(folders, first_id, second_id, name):
    """Drop one app on another: a folder with both, or the app added to the
    folder the other one is already in. Returns the folders, changed."""
    if first_id == second_id:
        return folders
    folders = [dict(f, apps=list(f["apps"])) for f in folders]
    home = folder_of(folders, first_id)
    moved_from = folder_of(folders, second_id)
    if moved_from is not None and moved_from is home:
        return folders
    if moved_from is not None:
        moved_from["apps"].remove(second_id)
    if home is None:
        home = {"name": name, "apps": [first_id]}
        folders.insert(0, home)
    if second_id not in home["apps"]:
        home["apps"].append(second_id)
    return [f for f in folders if f["apps"]]


def take_out(folders, app_id):
    """An app leaves its folder; a folder with nothing left disappears."""
    folders = [dict(f, apps=[a for a in f["apps"] if a != app_id]) for f in folders]
    return [f for f in folders if f["apps"]]


def rename(folders, old, new):
    new = (new or "").strip()
    if not new:
        return folders
    return [dict(f, name=new) if f["name"] == old else dict(f) for f in folders]


def paginate(items, per_page):
    """The grid cut into pages. One page when they all fit, and never a page
    of one tile because the count is one over."""
    per_page = max(MIN_PER_PAGE, int(per_page or MIN_PER_PAGE))
    if len(items) <= per_page:
        return [list(items)]
    return [list(items[i:i + per_page]) for i in range(0, len(items), per_page)]


def fits(width, height, tile_width, tile_height):
    """How many tiles a page of this size holds, with at least two rows."""
    columns = max(3, min(8, int(width // max(1, tile_width))))
    rows = max(2, int(height // max(1, tile_height)))
    return columns * rows, columns
