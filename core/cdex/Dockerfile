FROM debian:bookworm AS builder

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /build/pkg

COPY . .

# Install build dependencies declared in debian/control.
RUN apt-get update && apt-get build-dep -y . \
 && rm -rf /var/lib/apt/lists/*


# Build the binary package.
RUN dpkg-buildpackage -us -uc -b

FROM scratch AS exporter

COPY --from=builder /build/*.deb /
