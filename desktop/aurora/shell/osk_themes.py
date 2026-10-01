"""The on-screen keyboard's themes (kept apart: Settings reads them too)."""

from aurora.i18n import N_

# Looks (Settings → Accessibility → Keyboard theme); the last four change the
# keys' shape and lettering too.
THEMES = (("classic", N_("Aurora")), ("light", N_("Light")), ("accent", N_("Accent Color")),
          ("glass", N_("Glass")), ("mechanical", N_("Mechanical")),
          ("comic", N_("Comic")), ("typewriter", N_("Typewriter")),
          ("neon", N_("Synthwave")), ("pixel", N_("Pixel")), ("candy", N_("Candy")))
