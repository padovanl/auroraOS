"""Custom shortcut commands reach Wayfire whole (wf-config: # starts a comment)."""

from aurora.wayfireconf import wf_value


def test_hash_is_escaped_for_wayfire():
    assert wf_value("xdg-open https://site/#part") == "xdg-open https://site/\\#part"
    assert wf_value("notify-send hi") == "notify-send hi"
    assert wf_value("a\nb") == "a b"
