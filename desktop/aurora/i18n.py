"""Translation helpers. Import `_` and `N_` from here."""

import gettext
import locale

from aurora import LOCALEDIR

DOMAIN = "aurora"

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass

try:
    locale.bindtextdomain(DOMAIN, LOCALEDIR)
    locale.textdomain(DOMAIN)
except AttributeError:
    pass

gettext.bindtextdomain(DOMAIN, LOCALEDIR)
gettext.textdomain(DOMAIN)

_ = gettext.gettext
ngettext = gettext.ngettext


def N_(message):
    """Mark a string for translation without translating it yet."""
    return message
