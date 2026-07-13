# Build environment for Aurora OS. Everything that needs root (debootstrap,
# chroot, squashfs, ISO mastering) happens inside this container.
FROM debian:trixie

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        debootstrap \
        squashfs-tools \
        xorriso \
        grub-pc-bin \
        grub-efi-amd64-bin \
        grub-common \
        mtools \
        dosfstools \
        ca-certificates \
        gettext \
        python3 \
        make \
        rsync \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
