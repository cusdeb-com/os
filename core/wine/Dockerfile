FROM debian:trixie AS builder

ENV DEBIAN_FRONTEND=noninteractive

# ` architecture is required for the 32-bit Wine build.
RUN dpkg --add-architecture i386

WORKDIR /build/pkg

COPY . .

# Install build dependencies declared in debian/control, exactly like hello-world.
# apt-get update lives in the same layer so the package index is refreshed
# whenever the source tree changes (COPY above invalidates the cache).
RUN apt-get update \
    && apt-get build-dep -y . \
    && rm -rf /var/lib/apt/lists/*

# Build the package. ccache is persisted via BuildKit cache mount.
RUN --mount=type=cache,target=/root/.ccache \
    dpkg-buildpackage -us -uc -b

FROM scratch AS exporter

COPY --from=builder /build/*.deb /
