"""File clipboard compatible with GTK and GNOME file managers."""
from gi.repository import Gdk, Gio, GLib

MIME = "x-special/gnome-copied-files"
MAX_BYTES = 1024 * 1024
STATE = {"provider": None, "mode": None, "files": [], "pending": False}


def decode(data):
    """A GNOME clipboard carries its action followed by escaped file URIs."""
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    if not lines or lines[0] not in ("copy", "cut"):
        return None
    files = []
    for uri in lines[1:]:
        if not uri or ":" not in uri or any(c.isspace() for c in uri) or "\0" in uri:
            return None
        location = Gio.File.new_for_uri(uri)
        if not any(location.equal(old) for old in files):
            files.append(location)
    return ("move" if lines[0] == "cut" else "copy", files) if files else None


def owned(clipboard):
    provider = STATE["provider"]
    return provider is not None and clipboard.get_content() == provider


def publish(clipboard, mode, files):
    filelist = Gdk.FileList.new_from_list(files)
    payload = ("cut" if mode == "move" else "copy") + "\n"
    payload += "\n".join(file.get_uri() for file in files) + "\n"
    provider = Gdk.ContentProvider.new_union([
        Gdk.ContentProvider.new_for_value(filelist),
        Gdk.ContentProvider.new_for_bytes(MIME, GLib.Bytes.new(payload.encode("utf-8")))])
    if clipboard.set_content(provider):
        STATE.update(provider=provider, mode=mode, files=list(files), pending=False)
        return provider
    return None


def complete_move(clipboard, provider, completed):
    """Retain failed/cancelled cut items without replacing a newer clipboard."""
    if not owned(clipboard) or STATE["provider"] != provider:
        return
    remaining = [file for file in STATE["files"] if file.get_path() not in completed]
    if remaining:
        return publish(clipboard, "move", remaining)
    else:
        clipboard.set_content(None)
        STATE.update(provider=None, mode=None, files=[], pending=False)


def read(clipboard, callback):
    if owned(clipboard):
        if not STATE["pending"]:
            callback(STATE["mode"], list(STATE["files"]), STATE["provider"])
        return

    def fallback():
        def got(clip, result):
            try:
                value = clip.read_value_finish(result)
            except GLib.Error:
                return
            if value is not None:
                callback("copy", value.get_files(), None)
        clipboard.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, got)

    if not clipboard.get_formats().contain_mime_type(MIME):
        fallback()
        return

    def opened(clip, result):
        try:
            stream, _mime = clip.read_finish(result)
        except GLib.Error:
            fallback()
            return
        content = bytearray()

        def close():
            stream.close_async(GLib.PRIORITY_DEFAULT, None, None)

        def chunk_done(source, res):
            try:
                data = source.read_bytes_finish(res).get_data()
            except GLib.Error:
                close()
                fallback()
                return
            content.extend(data)
            if len(content) > MAX_BYTES:
                close()
                return
            if data:
                stream.read_bytes_async(65536, GLib.PRIORITY_DEFAULT, None, chunk_done)
                return
            close()
            value = decode(bytes(content))
            if value:
                callback(*value, None)
            else:
                fallback()
        stream.read_bytes_async(65536, GLib.PRIORITY_DEFAULT, None, chunk_done)
    clipboard.read_async([MIME], GLib.PRIORITY_DEFAULT, None, opened)
