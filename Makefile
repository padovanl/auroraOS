# Aurora OS build entry point (runs on the host, needs docker + kvm for `run`).

BUILDER   := aurora-os-builder
WORKVOL   := $(CURDIR)/work
OUTDIR    := $(CURDIR)/out
VERSION   := $(shell . config/aurora.conf && echo $$AURORA_VERSION)
ISO       := $(OUTDIR)/aurora-os-$(VERSION)-amd64.iso
# Package version: release.commit-count, e.g. 0.1.47 (newer builds upgrade older ones).
PKG_VERSION := $(VERSION).$(shell git rev-list --count HEAD 2>/dev/null || echo 0)
DOCKER_RUN = docker run --rm --privileged -e AURORA_PKG_VERSION=$(PKG_VERSION) \
	-v $(CURDIR):/src:ro -v $(WORKVOL):/work -v $(OUTDIR):/out \
	$(BUILDER)

.PHONY: all builder iso stage shell run run-uefi desktop-dev clean distclean \
	test test-static test-unit test-smoke test-image test-boot test-interact test-shortcuts \
	test-newfeatures \
	test-shortcut-edges test-files-shortcuts \
	test-install dev-image screenshots site manual vm-screenshots debs repo

all: iso

builder:
	docker build -q -t $(BUILDER) build/

# Full build (bootstrap is skipped if the rootfs already exists).
iso: builder
	@mkdir -p $(WORKVOL) $(OUTDIR)
	$(DOCKER_RUN) bash /src/build/build-inner.sh

# Re-run selected stages, e.g. `make stage S="30 40 80 90"`.
stage: builder
	$(DOCKER_RUN) bash /src/build/build-inner.sh $(S)

shell: builder
	docker run --rm -it --privileged -v $(CURDIR):/src:ro -v $(WORKVOL):/work \
		-v $(OUTDIR):/out $(BUILDER) bash

run:
	build/run-qemu.sh $(ISO)

run-uefi:
	build/run-qemu.sh --uefi $(ISO)

# Run the shell on the current host session (for development).
desktop-dev:
	cd desktop && ./dev-run.sh

# --- tests ---------------------------------------------------------------
# test: everything that needs no ISO (sources, unit tests, headless desktop).
# test-image / test-boot: checks on a built ISO; run before every release.

DEV_RUN = docker run --rm -e PYTHONPYCACHEPREFIX=/tmp/pyc -v $(CURDIR):/src:ro -w /src aurora-os-dev

dev-image:
	docker build -q -t aurora-os-dev desktop/dev >/dev/null

test: test-static test-unit test-smoke

test-static: dev-image
	$(DEV_RUN) bash tests/static.sh

test-unit: dev-image
	$(DEV_RUN) python3 -m pytest -q -p no:cacheprovider tests/unit

test-smoke: dev-image
	desktop/dev/run-headless.sh tests/smoke.sh $(CURDIR)/work/smoke-out
	@test "$$(cat work/smoke-out/smoke/result)" = 0 && echo "SMOKE TEST PASSED"

# Screenshots for the website/README from the real ISO in QEMU.
vm-screenshots:
	python3 tools/vm-screenshots.py $(ISO) --out docs/screenshots

# Only Aurora's packages (out/debs/), without building an ISO.
debs: builder
	@mkdir -p $(WORKVOL) $(OUTDIR)
	$(DOCKER_RUN) bash -c 'mkdir -p /work/src && rsync -a --delete --exclude /desktop/build /src/desktop /src/branding /work/src/ && cp /src/LICENSE /work/src/ && bash /src/build/package-desktop.sh /work/src /out/debs $(PKG_VERSION)'

# Publish out/debs/ into the signed apt repository in docs/apt/ (GitHub Pages).
repo:
	tools/publish-apt.sh out/debs docs/apt

# Regenerate the website's technical page from README.md.
site:
	python3 tools/build-site.py

# Rebuild the official documentation (docs/manual) from docs/_manual and the code.
manual:
	python3 tools/build-manual.py

# Regenerate docs/screenshots from a scripted headless session.
screenshots: dev-image
	desktop/dev/run-headless.sh tests/showcase.sh $(CURDIR)/work/showcase-out
	mkdir -p docs/screenshots
	cp work/showcase-out/showcase/*.png docs/screenshots/

test-image: builder
	$(DOCKER_RUN) bash /src/tests/image/check-rootfs.sh

test-boot:
	python3 tests/boot/boot-test.py $(ISO) --firmware bios --out work/boot-test
	python3 tests/boot/boot-test.py $(ISO) --firmware uefi --out work/boot-test

# Uses the live desktop like a person (clicks, double-clicks, keys) and checks
# the result: desktop icons, installer, windows, menus, Settings (~5 min).
test-interact:
	python3 tests/interact/scenarios.py $(ISO) --out work/interact-test

# This release's new work, on the real system: the icon styles, Launchpad's
# pages and folders, the moving background, window previews, the new apps.
test-newfeatures:
	python3 tests/interact/newfeatures.py $(ISO) --out work/newfeatures

# Drives the system-wide combinations listed in the keyboard-shortcuts manual.
test-shortcuts:
	python3 tests/interact/shortcuts.py $(ISO) --out work/shortcut-test

# Repeats and overlaps shortcuts, cancels modal selectors, and mixes window states.
test-shortcut-edges:
	python3 tests/interact/shortcut_edges.py $(ISO) --out work/shortcut-edge-test

# Drives Files' documented shortcuts, then stresses focus and asynchronous edges.
test-files-shortcuts:
	python3 tests/interact/files_shortcuts.py $(ISO) --out work/files-shortcut-test
	python3 tests/interact/files_shortcut_edges.py $(ISO) --out work/files-shortcut-edge-test

# Installs the ISO onto an empty virtual disk with the real installer (driven by
# key presses), then boots the installed system and checks it (~20 min each).
test-install:
	python3 tests/install/install-test.py $(ISO) --firmware bios --out work/install-test
	python3 tests/install/install-test.py $(ISO) --firmware uefi --out work/install-test

clean:
	$(DOCKER_RUN) rm -rf /work/rootfs /work/iso

distclean: clean
	$(DOCKER_RUN) rm -rf /work/cache
	rm -rf $(OUTDIR)
