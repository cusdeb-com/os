FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        debootstrap \
        parted \
        e2fsprogs \
        dosfstools \
        util-linux \
        mount \
        grub-pc-bin \
        grub2-common \
        ca-certificates \
        curl \
        git \
        gdisk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install the builder entrypoint plus the full shell module tree and runtime
# payload under /usr/local/share/cusdeb-os so build-image.sh can use its fallback
# path resolution when it runs inside the container.
COPY build-image.sh /usr/local/bin/build-image.sh

COPY scripts /usr/local/share/cusdeb-os/scripts

COPY userland /usr/local/share/cusdeb-os/userland

RUN chmod +x /usr/local/bin/build-image.sh

ENTRYPOINT ["/usr/local/bin/build-image.sh"]
