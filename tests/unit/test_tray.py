from aurora.shell.tray import _pixmap_texture


def test_argb_pixmap_becomes_texture():
    # One opaque red pixel and one transparent pixel, ARGB in network byte order.
    data = bytes([255, 255, 0, 0, 0, 0, 0, 0])
    tex = _pixmap_texture([(2, 1, data)])
    assert tex.get_width() == 2 and tex.get_height() == 1


def test_picks_closest_size():
    small = (16, 16, bytes(16 * 16 * 4))
    big = (64, 64, bytes(64 * 64 * 4))
    assert _pixmap_texture([big, small], size=22).get_width() == 16
    assert _pixmap_texture([], size=22) is None
