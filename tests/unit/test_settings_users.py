"""Settings → Users: usernames suggested from any full name, and full names
that can't break the account entry."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from aurora.settingsapp.system import clean_full_name, suggest_username, username_problem  # noqa: E402


def test_usernames_from_full_names():
    assert suggest_username("Lùca Pàdovan") == "luca"
    assert suggest_username("Ægir Øster") == "gir"      # no ASCII form: the person edits it
    assert suggest_username("田中 太郎") == ""
    assert suggest_username("2pac Shakur") == "u2pac"
    assert suggest_username("") == ""


def test_username_rules():
    assert username_problem("mario") is None
    assert username_problem("root") is not None         # exists
    assert username_problem("Mario") is not None
    assert username_problem("1abc") is not None
    assert username_problem("") is not None


def test_full_name_separators():
    assert clean_full_name("Rossi, Mario") == "Rossi Mario"
    assert clean_full_name("a:b") == "a b"
