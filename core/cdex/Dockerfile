FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /tmp/cdex-buildenv

# Needed only to build this image: apt-get build-dep reads the build
# dependencies from debian/control. The source tree is not copied; it is
# mounted when a package is built.
COPY debian/control debian/control

RUN apt-get update && apt-get build-dep -y . \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

CMD ["sleep", "infinity"]
