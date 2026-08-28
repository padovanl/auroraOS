"""The shareable health report uses only the visible diagnostic summaries."""

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from aurora.settingsapp.health import format_report  # noqa: E402


def test_format_report_is_compact_and_omits_actions():
    results = [
        ("Disk space", "drive-harddisk-symbolic", ("ok", "42 GB free", None)),
        ("Software updates", "software-update-available-symbolic",
         ("warn", "3 updates available", ("Update", lambda: None))),
    ]
    report = format_report(results)
    assert report == ("Aurora Doctor\n✓ Disk space: 42 GB free\n"
                      "⚠ Software updates: 3 updates available")
    assert "Update\n" not in report
