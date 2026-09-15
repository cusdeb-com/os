FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /tmp/cdex-buildenv

# Install the toolchain declared by CDEX. Only debian/control is copied so
# source changes do not become part of the build environment image.
COPY debian/control debian/control

RUN apt-get update && apt-get build-dep -y . \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

CMD ["sleep", "infinity"]
