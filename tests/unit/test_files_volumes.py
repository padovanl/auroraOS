"""Opening Windows' partition from Files: UDisks object paths, cancelled prompts."""

from gi.repository import Gio, GLib

from aurora.files import volumes


def test_block_object_path_escapes_like_udisks():
    assert volumes.block_object_path("/dev/vda3") == "/org/freedesktop/UDisks2/block_devices/vda3"
    assert volumes.block_object_path("/dev/nvme0n1p3").endswith("/nvme0n1p3")
    assert volumes.block_object_path("/dev/dm-0").endswith("/dm_2d0")
    assert volumes.block_object_path("/dev/md_1").endswith("/md_5f1")


def test_closing_the_password_prompt_is_not_an_error():
    handled = GLib.Error.new_literal(Gio.io_error_quark(), "handled",
                                     Gio.IOErrorEnum.FAILED_HANDLED)
    other = GLib.Error.new_literal(Gio.io_error_quark(), "wrong fs type", Gio.IOErrorEnum.FAILED)
    assert volumes.is_cancelled(handled)
    assert not volumes.is_cancelled(other)


def test_pipes_and_devices_are_special(tmp_path):
    import os
    from aurora import apps
    pipe = tmp_path / "pipe.txt"
    os.mkfifo(pipe)
    regular = tmp_path / "notes.txt"
    regular.write_text("hi")
    assert apps.special_file(str(pipe))
    assert apps.special_file("/dev/null")
    assert not apps.special_file(str(regular))
    assert not apps.special_file(str(tmp_path))
    assert not apps.special_file(str(tmp_path / "missing"))
    assert not apps.special_file(None)
    from aurora.ai import index
    assert index.extract(str(pipe)) == ""         # returns at once, no blocking read


def test_files_sort_naturally():
    from aurora.files.window import sort_key
    names = ["f10.txt", "f2.txt", "f1.txt", "F3.txt", "f100.txt"]
    assert sorted(names, key=sort_key) == ["f1.txt", "f2.txt", "F3.txt", "f10.txt", "f100.txt"]


def test_shell_helpers_end_with_the_shell(monkeypatch):
    import shutil
    from aurora import apps
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
    assert apps.tied(["wl-paste", "--watch", "x"]) == [
        "setpriv", "--pdeathsig", "TERM", "--", "wl-paste", "--watch", "x"]
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert apps.tied(["wlsunset"]) == ["wlsunset"]
