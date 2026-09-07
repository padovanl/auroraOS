"""Small, optional Wayfire IPC client for project window layouts."""

import json
import os
import socket
import struct
import time


def request(method, data=None):
    address = os.environ.get("WAYFIRE_SOCKET")
    if not address:
        raise OSError("Wayfire IPC unavailable")
    payload = json.dumps({"method": method, "data": data or {}}).encode()
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(1.5)
        connection.connect(address)
        connection.sendall(struct.pack("<I", len(payload)) + payload)
        size = struct.unpack("<I", _read(connection, 4))[0]
        if size > 1024 * 1024:
            raise ValueError("Wayfire response too large")
        result = json.loads(_read(connection, size))
    if isinstance(result, dict) and "error" in result:
        raise OSError(str(result["error"]))
    return result


def _read(connection, size):
    chunks = []
    while size:
        chunk = connection.recv(size)
        if not chunk:
            raise ConnectionError("Wayfire IPC closed")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


def views():
    result = request("window-rules/list-views")
    return result if isinstance(result, list) else []


def save_layout():
    saved = []
    for view in views():
        geometry = view.get("geometry", {})
        app_id = view.get("app-id", "")
        if not app_id or not all(isinstance(geometry.get(k), int)
                                 for k in ("x", "y", "width", "height")):
            continue
        if geometry["width"] <= 0 or geometry["height"] <= 0:
            continue
        saved.append({"app_id": app_id, "geometry": {
            key: geometry[key] for key in ("x", "y", "width", "height")}})
    return saved


def restore_layout(layout, before):
    """Only position newly launched views; never move unrelated open windows."""
    if not layout:
        return
    known = {item.get("id") for item in before}
    pending = list(layout)
    deadline = time.monotonic() + 12
    while pending and time.monotonic() < deadline:
        time.sleep(0.5)
        try:
            current = views()
        except (OSError, ValueError, ConnectionError):
            return
        for view in current:
            if view.get("id") in known:
                continue
            match = next((item for item in pending
                          if item.get("app_id") == view.get("app-id")), None)
            if match is None:
                continue
            try:
                request("window-rules/configure-view", {
                    "id": view["id"], "geometry": match["geometry"]})
            except (OSError, ValueError, KeyError):
                pass
            pending.remove(match)
            known.add(view.get("id"))
