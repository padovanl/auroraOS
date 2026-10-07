"""Rows and toasts show names as they are ("Tom & Jerry <draft>")."""

import pytest

from aurora import plaintext  # noqa: F401
from gi.repository import Adw, Gdk, Gtk


def test_rows_and_toasts_are_plain_text():
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        pytest.skip("GTK display unavailable")
    Adw.init()
    row = Adw.ActionRow(title="Tom & Jerry <draft>", subtitle="< 1 min")
    assert not row.get_use_markup()
    assert row.get_title() == "Tom & Jerry <draft>" and row.get_subtitle() == "< 1 min"
    assert not Adw.SwitchRow(title="a & b").get_use_markup()
    assert not Adw.Toast(title="a & <b>").get_use_markup()
    assert Adw.ActionRow(title="<b>bold</b>", use_markup=True).get_use_markup()
