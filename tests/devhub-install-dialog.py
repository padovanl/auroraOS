#!/usr/bin/env python3
"""Exercise Dev Hub's embedded installer in a real GTK session."""

import os
import shlex
import sys
import tempfile
import time

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

from aurora.devhub import app as devhub


class Card:
    def __init__(self, marker):
        self.recipe = {
            "id": "dialog-smoke",
            "name": "Dialog smoke test",
            "check": f"test -f {shlex.quote(marker)}",
        }
        self.refreshed = False
        self.install_failed = False

    def refresh(self):
        self.refreshed = True


class TestApp(Adw.Application):
    def __init__(self, recipe_path, marker, expect_success):
        super().__init__(application_id="org.aurora.DevHub.InstallDialogTest")
        self.recipe_path = recipe_path
        self.marker = marker
        self.expect_success = expect_success
        self.ok = False

    def do_activate(self):
        GLib.timeout_add_seconds(10, self._timeout)
        parent = Adw.ApplicationWindow(application=self)
        parent.toasts = Adw.ToastOverlay()
        parent.set_content(parent.toasts)
        parent.present()
        card = Card(self.marker)
        # The smoke test needs no shell activity service; it only checks the
        # VTE process lifecycle and the resulting UI state.
        devhub.activities.update = lambda *_args, **_kwargs: None
        dialog = devhub.InstallWindow(parent, card, self.recipe_path, "smoke")
        dialog.present()
        deadline = time.monotonic() + 8

        def check():
            if dialog.running and time.monotonic() < deadline:
                return GLib.SOURCE_CONTINUE
            expected_status = "installed" if self.expect_success else "failed"
            self.ok = (not dialog.running and os.path.exists(self.marker) and
                       card.refreshed and card.install_failed is not self.expect_success and
                       expected_status in dialog.status.get_label().lower())
            dialog.close()
            parent.close()
            self.quit()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(100, check)

    def _timeout(self):
        self.quit()
        return GLib.SOURCE_REMOVE


def main():
    expect_success = "--fail-after-install" not in sys.argv[1:]
    marker_fd, marker = tempfile.mkstemp(prefix="devhub-dialog-result-")
    os.close(marker_fd)
    os.remove(marker)
    fd, recipe = tempfile.mkstemp(prefix="devhub-dialog-recipe-", suffix=".sh")
    with os.fdopen(fd, "w") as stream:
        stream.write(f"#!/bin/bash\nprintf done > {shlex.quote(marker)}\n")
        if not expect_success:
            stream.write("exit 17\n")
    app = TestApp(recipe, marker, expect_success)
    app.run([])
    if os.path.exists(marker):
        os.remove(marker)
    return 0 if app.ok and not os.path.exists(recipe) else 1


if __name__ == "__main__":
    raise SystemExit(main())
