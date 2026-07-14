FROM debian:trixie AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        live-build \
        xorriso \
        grub-pc-bin \
        grub-efi-amd64-bin \
        mtools \
        dosfstools \
        cpio \
        gzip \
        squashfs-tools \
        debootstrap \
        wget \
        ca-certificates \
        calamares \
        qt6-base-dev \
        qt6-tools-dev \
        qt6-svg-dev \
        libxkbcommon-dev \
        cmake \
        make \
        g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy the installer source tree into the build stage so the ISO is produced
# entirely inside the Dockerfile, matching the package build pattern.
COPY installer/auto ./auto
COPY installer/config ./config
COPY installer/modules ./modules
COPY installer/build-iso.sh ./build-iso.sh

# Build configuration knobs, passed as build-args from the host wrapper.
ARG MIRROR=http://deb.debian.org/debian
ARG ISO_NAME=cusdeb-os.iso
ARG FORCE_CLEAN=0

ENV BUILD_DIR=/tmp/live-build
ENV OUT_DIR=/build/out
ENV ISO_NAME=${ISO_NAME}
ENV MIRROR=${MIRROR}
ENV FORCE_CLEAN=${FORCE_CLEAN}

# Run the build with elevated privileges so live-build can debootstrap and mount
# pseudo-filesystems inside its chroot.
RUN --security=insecure chmod +x ./build-iso.sh && ./build-iso.sh

FROM scratch AS exporter

COPY --from=builder /build/out/*.iso /
