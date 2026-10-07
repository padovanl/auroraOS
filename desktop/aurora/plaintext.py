"""Rows and toasts show text as it is.

Adw's rows (ActionRow, ComboRow, SwitchRow, EntryRow…) and toasts read their
titles as Pango markup by default: a Wi-Fi network, file or person called
"Tom & Jerry" or "<draft>" came out blank or broken. Every Aurora app imports
this first; a row that really wants markup passes use_markup=True.
"""

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw  # noqa: E402


def _plain_init(original):
    def __init__(self, *args, **kwargs):
        # The texts after use-markup, so they're never parsed as markup (GTK
        # warns each time that fails); GObject sets properties in its own order.
        texts = {k: kwargs.pop(k) for k in ("title", "subtitle") if k in kwargs}
        kwargs.setdefault("use_markup", False)
        original(self, *args, **kwargs)
        for key, value in texts.items():
            self.set_property(key, value)
    __init__._aurora_plain = True
    return __init__


for _cls in (Adw.PreferencesRow, Adw.Toast):
    if not getattr(_cls.__init__, "_aurora_plain", False):
        _cls.__init__ = _plain_init(_cls.__init__)


# Every Aurora app imports this module first: its surface colors come with it.
from aurora import surfaces  # noqa: E402

surfaces.install()
