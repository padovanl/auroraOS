# Aurora OS build entry point (runs on the host, needs docker + kvm for `run`).

BUILDER   := aurora-os-builder
WORKVOL   := $(CURDIR)/work
OUTDIR    := $(CURDIR)/out
VERSION   := $(shell . config/aurora.conf && echo $$AURORA_VERSION)
ISO       := $(OUTDIR)/aurora-os-$(VERSION)-amd64.iso
DOCKER_RUN = docker run --rm --privileged \
	-v $(CURDIR):/src:ro -v $(WORKVOL):/work -v $(OUTDIR):/out \
	$(BUILDER)

.PHONY: all builder iso stage shell run run-uefi desktop-dev clean distclean

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

clean:
	$(DOCKER_RUN) rm -rf /work/rootfs /work/iso

distclean: clean
	$(DOCKER_RUN) rm -rf /work/cache
	rm -rf $(OUTDIR)
