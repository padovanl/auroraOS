# Aurora OS build entry point (runs on the host, needs docker + kvm for `run`).

BUILDER   := aurora-os-builder
WORKVOL   := $(CURDIR)/work
OUTDIR    := $(CURDIR)/out
VERSION   := $(shell . config/aurora.conf && echo $$AURORA_VERSION)
ISO       := $(OUTDIR)/aurora-os-$(VERSION)-amd64.iso
DOCKER_RUN = docker run --rm --privileged \
	-v $(CURDIR):/src:ro -v $(WORKVOL):/work -v $(OUTDIR):/out \
	$(BUILDER)

.PHONY: all builder iso stage shell run run-uefi desktop-dev clean distclean \
	test test-static test-unit test-smoke test-image test-boot dev-image

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

test-image: builder
	$(DOCKER_RUN) bash /src/tests/image/check-rootfs.sh

test-boot:
	python3 tests/boot/boot-test.py $(ISO) --firmware bios --out work/boot-test
	python3 tests/boot/boot-test.py $(ISO) --firmware uefi --out work/boot-test

clean:
	$(DOCKER_RUN) rm -rf /work/rootfs /work/iso

distclean: clean
	$(DOCKER_RUN) rm -rf /work/cache
	rm -rf $(OUTDIR)
