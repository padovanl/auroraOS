import pytest

from aurora.shell.notifications import sanitize_markup


@pytest.mark.parametrize("body, expected", [
    ("plain text", "plain text"),
    ("<b>bold</b> and <i>it</i>", "<b>bold</b> and <i>it</i>"),
    ("<B>caps</B>", "<b>caps</b>"),
    ("a < b & c", "a &lt; b &amp; c"),
    ("<script>x</script>", "&lt;script&gt;x&lt;/script&gt;"),
    ("<a href='x'>link</a>", "&lt;a href='x'&gt;link&lt;/a&gt;"),
])
def test_only_basic_markup_survives(body, expected):
    assert sanitize_markup(body) == expected


def test_unbalanced_tags_fall_back_to_plain_text():
    out = sanitize_markup("<b>never closed")
    assert "<b>" not in out
    assert "never closed" in out
