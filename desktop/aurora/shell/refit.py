"""Keep windows in proportion when a display's resolution changes (Wayfire).

Wayfire resizes maximized, tiled and fullscreen windows by itself, but leaves
floating ones where they were: after going from 2560x1440 to 1280x800 they hang
off the screen. The shell watches each monitor; when one changes size, every
floating window on it keeps its relative place and size in the new work area
(and never shrinks below the size the app asks for). labwc already moves
windows back onto the screen itself.
"""

import threading

from gi.repository import Gdk, GLib


def refit_geometry(geometry, old_area, new_area, min_size=(0, 0)):
    """The geometry (dict x, y, width, height) a window gets when its work area
    (dict x, y, width, height) changes from old_area to new_area."""
    if old_area == new_area or not old_area["width"] or not old_area["height"]:
        return dict(geometry)
    sx = new_area["width"] / old_area["width"]
    sy = new_area["height"] / old_area["height"]
    width = max(round(geometry["width"] * sx), min_size[0], 1)
    height = max(round(geometry["height"] * sy), min_size[1], 1)
    width, height = min(width, new_area["width"]), min(height, new_area["height"])
    x = new_area["x"] + round((geometry["x"] - old_area["x"]) * sx)
    y = new_area["y"] + round((geometry["y"] - old_area["y"]) * sy)
    x = min(max(x, new_area["x"]), new_area["x"] + new_area["width"] - width)
    y = min(max(y, new_area["y"]), new_area["y"] + new_area["height"] - height)
    return {"x": x, "y": y, "width": width, "height": height}


def floating(view):
    return (view.get("role") == "toplevel" and view.get("mapped")
            and not view.get("fullscreen") and not view.get("minimized")
            and not view.get("tiled-edges"))


class WindowRefit:
    def __init__(self, shell):
        self.shell = shell
        self._areas = {}
        from aurora import compositor
        if not compositor.is_wayfire():
            return
        monitors = Gdk.Display.get_default().get_monitors()
        monitors.connect("items-changed", lambda *_: self._watch_all(monitors))
        self._watch_all(monitors)
        threading.Thread(target=self._remember, daemon=True).start()

    def _watch_all(self, monitors):
        for i in range(monitors.get_n_items()):
            monitor = monitors.get_item(i)
            if not getattr(monitor, "_aurora_refit", False):
                monitor._aurora_refit = True
                monitor.connect("notify::geometry", self._changed)

    def _outputs(self):
        from aurora import wayfirelayout
        return {o["name"]: o["workarea"] for o in wayfirelayout.request("window-rules/list-outputs")
                if isinstance(o, dict) and "workarea" in o}

    def _remember(self):
        try:
            self._areas = self._outputs()
        except (OSError, ValueError, ConnectionError):
            pass

    def _changed(self, *_args):
        # Let the compositor and the panels settle on the new size first.
        GLib.timeout_add(600, lambda: (threading.Thread(target=self._refit, daemon=True).start(),
                                       False)[1])

    def _refit(self):
        from aurora import wayfirelayout
        try:
            areas = self._outputs()
            views = wayfirelayout.views()
        except (OSError, ValueError, ConnectionError) as err:
            print(f"aurora: windows not refitted: {err}")
            return
        for view in views:
            old, new = self._areas.get(view.get("output-name")), areas.get(view.get("output-name"))
            if not old or not new or old == new or not floating(view):
                continue
            size = view.get("min-size") or {}
            geometry = refit_geometry(view["geometry"], old, new,
                                      (size.get("width", 0), size.get("height", 0)))
            if geometry == view["geometry"]:
                continue
            try:
                wayfirelayout.request("window-rules/configure-view",
                                      {"id": view["id"], "geometry": geometry})
            except (OSError, ValueError, ConnectionError) as err:
                print(f"aurora: cannot refit {view.get('app-id')}: {err}")
        self._areas = areas
