FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive

# i386 architecture is required for the 32-bit Wine build.
RUN dpkg --add-architecture i386

WORKDIR /tmp/wine-buildenv

# Only packaging metadata is needed to install the build dependencies. The
# source tree is mounted when a build is run, so source changes do not rebuild
# this image.
COPY debian/control debian/control

RUN apt-get update \
    && apt-get build-dep -y . \
    && rm -rf /var/lib/apt/lists/*

# ccache does not provide wrappers for the MinGW compiler names in the base
# image. These names must resolve to ccache before the real compiler is found.
RUN mkdir -p /opt/ccache/bin \
    && ln -s /usr/bin/ccache /opt/ccache/bin/x86_64-w64-mingw32-gcc \
    && ln -s /usr/bin/ccache /opt/ccache/bin/x86_64-w64-mingw32-g++ \
    && ln -s /usr/bin/ccache /opt/ccache/bin/i686-w64-mingw32-gcc \
    && ln -s /usr/bin/ccache /opt/ccache/bin/i686-w64-mingw32-g++

ENV PATH="/opt/ccache/bin:${PATH}"
WORKDIR /workspace

CMD ["sleep", "infinity"]
