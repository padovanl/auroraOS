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
        curl \
        xz-utils \
        gettext \
        python3 \
        python3-cairo \
        python3-pil \
        python3-numpy \
        fonts-inter \
        python3-pywayland \
        python3-cffi-backend \
        libwayland-dev \
        pkgconf \
        g++ \
        qt6-base-dev \
        qt6-declarative-dev \
        apt-utils \
        make \
        rsync \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
