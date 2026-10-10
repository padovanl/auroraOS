"""Shared interpretation of a negotiated GTK file drop."""

from gi.repository import Gdk, Gio, GLib


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


def file_paths(value):
    """The local paths carried by a dropped GdkFileList: in the order they were
    dragged, without repeats, and without the remote files nothing here can
    open by path."""
    paths = []
    for gfile in value.get_files():
        path = gfile.get_path()
        if path and path not in paths:
            paths.append(path)
    return paths


def to_trash(paths):
    """Move these files to the trash, and say how many went. One that refuses
    (a read-only disk, a file already gone) leaves the others alone."""
    moved = 0
    for path in paths:
        try:
            Gio.File.new_for_path(path).trash(None)
            moved += 1
        except GLib.Error as err:
            print(f"aurora: {path} could not be moved to the trash: {err.message}")
    return moved


def preferred_action(target, wanted):
    """The action to answer a drag with: the one we mean, when it is on offer,
    and otherwise the one that is — a source that only moves gets a move back,
    because answering with anything it did not offer calls the drop off."""
    drop = target.get_current_drop() if target is not None else None
    offered = drop.get_actions() if drop is not None else wanted
    if offered & wanted:
        return wanted
    if offered & Gdk.DragAction.MOVE:
        return Gdk.DragAction.MOVE
    if offered & Gdk.DragAction.COPY:
        return Gdk.DragAction.COPY
    return wanted
