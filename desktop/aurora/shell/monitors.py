"""Keep one widget per monitor in sync with the connected outputs."""

from gi.repository import Gdk


class PerMonitor:
    """Calls factory(monitor) for each monitor and destroys windows on unplug."""

    def __init__(self, factory):
        self._factory = factory
        self._windows = {}
        self._model = Gdk.Display.get_default().get_monitors()
        self._model.connect("items-changed", lambda *a: self._sync())
        self._sync()

    def _sync(self):
        current = [self._model.get_item(i) for i in range(self._model.get_n_items())]
        for mon in list(self._windows):
            if mon not in current:
                self._windows.pop(mon).destroy()
        for mon in current:
            if mon not in self._windows:
                win = self._factory(mon)
                self._windows[mon] = win
                win.present()

    def windows(self):
        return list(self._windows.values())


def primary_monitor():
    model = Gdk.Display.get_default().get_monitors()
    return model.get_item(0) if model.get_n_items() else None
