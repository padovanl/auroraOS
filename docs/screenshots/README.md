# Documentation screenshots

## Window and guide refresh — 12 October 2026

Eighteen captures show the current shared window styling, Settings pages, static
and animated wallpaper galleries, Files, Task Manager and the activity center. Extra workflow captures show the account-creation controls
and the Files context menu.
Settings → Users, Files and Task Manager include both light and dark views.
They were captured from an actual 1920×1080 Aurora session in disposable QEMU,
with current desktop sources staged into the existing live image. This documents
the current desktop; it does not validate a newly rebuilt release ISO. The guest
clock uses UTC. Activity rows and the Welcome.txt file are demonstration data.

PNG files retain the complete Full HD desktop. Lossless WebP versions focus on
the window or activity menu so guide controls stay readable on smaller screens.
The illustrated manual uses native, initially closed `details` sections with
lazy-loaded images, reserved image dimensions and a 200 ms disclosure animation.
Keyboard activation, reduced motion and operation without JavaScript are retained.
Click an image to open its original PNG. Older captures of other interfaces,
including the installer, remain separate from this window refresh.

To reproduce in a disposable VM (requires QEMU/KVM and Pillow):

```bash
python3 tools/window-screenshots.py path/to/new.iso
# For development captures from an older ISO:
python3 tools/window-screenshots.py path/to/old.iso --push
# Only wallpaper galleries and activity menu:
python3 tools/window-screenshots.py path/to/old.iso --push --guides-only
```

Regenerate the guide after changing `docs/_manual/`:

```bash
python3 tools/build-manual.py
python3 tools/check-site-links.py
```

The documentation generator requires the project's Python version (3.13 in the
development container). `tests/docs-disclosures.py` runs Chromium checks against
the generated Appearance guide: image deferral/loading, opening and closing,
rapid clicks, real Enter-key activation, mobile/desktop widths and reduced motion. It also verifies native disclosure with
JavaScript disabled. Run it
in the existing `aurora-web` container with this repository mounted at `/src`.
The guide sections use native `details`/`summary`, so screenshots remain
accessible when scripts are disabled.
