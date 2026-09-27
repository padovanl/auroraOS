"""Snap Layouts' zones, and which windows Snap Assist offers (see snap.py)."""

# Each zone is (x, y, width, height) as fractions of the work area.
LAYOUTS = (
    ((0, 0, 1 / 2, 1), (1 / 2, 0, 1 / 2, 1)),
    ((0, 0, 2 / 3, 1), (2 / 3, 0, 1 / 3, 1)),
    ((0, 0, 1 / 3, 1), (1 / 3, 0, 1 / 3, 1), (2 / 3, 0, 1 / 3, 1)),
    ((0, 0, 1 / 2, 1), (1 / 2, 0, 1 / 2, 1 / 2), (1 / 2, 1 / 2, 1 / 2, 1 / 2)),
    ((0, 0, 1 / 2, 1 / 2), (1 / 2, 0, 1 / 2, 1 / 2),
     (0, 1 / 2, 1 / 2, 1 / 2), (1 / 2, 1 / 2, 1 / 2, 1 / 2)),
    ((0, 0, 1 / 4, 1), (1 / 4, 0, 1 / 2, 1), (3 / 4, 0, 1 / 4, 1)),
)

# Wayfire's tiled edges: a window snapped to the left or right half.
EDGE_TOP, EDGE_BOTTOM, EDGE_LEFT, EDGE_RIGHT = 1, 2, 4, 8
LEFT_HALF = EDGE_TOP | EDGE_BOTTOM | EDGE_LEFT
RIGHT_HALF = EDGE_TOP | EDGE_BOTTOM | EDGE_RIGHT


def zone_geometry(zone, area):
    """Pixels (dict x, y, width, height) of a zone in a work area. Neighbouring
    zones share their edges exactly: no gaps, no overlaps from rounding."""
    fx, fy, fw, fh = zone
    left = area["x"] + round(area["width"] * fx)
    right = area["x"] + round(area["width"] * (fx + fw))
    top = area["y"] + round(area["height"] * fy)
    bottom = area["y"] + round(area["height"] * (fy + fh))
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def other_half(edges):
    """The zone left free by a window snapped to a half, or None."""
    if edges == LEFT_HALF:
        return LAYOUTS[0][1]
    if edges == RIGHT_HALF:
        return LAYOUTS[0][0]
    return None


def candidates(views, output, exclude=()):
    """Windows Snap Assist offers: ordinary windows on that output, most
    recently used first, without those already placed."""
    out = [v for v in views
           if v.get("role") == "toplevel" and v.get("mapped", True)
           and v.get("output-name") == output and v.get("id") not in exclude
           and v.get("layer", "workspace") == "workspace" and not v.get("fullscreen")
           and v.get("app-id") not in ("org.aurora.Assistant",)]
    out.sort(key=lambda v: v.get("last-focus-timestamp", 0), reverse=True)
    return out
