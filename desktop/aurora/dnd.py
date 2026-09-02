"""Shared interpretation of a negotiated GTK file drop."""

from gi.repository import Gdk


def is_move(target):
    drop = target.get_current_drop() if target is not None else None
    if drop is None:
        return False
    drag = drop.get_drag()
    if drag is not None:
        selected = drag.get_selected_action()
        if selected:
            return selected == Gdk.DragAction.MOVE
    return bool(drop.get_actions() & Gdk.DragAction.MOVE)
