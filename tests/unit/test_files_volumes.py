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
