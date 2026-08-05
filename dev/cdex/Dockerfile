# CDEX-over-SPICE runtime image.

# Stage 1: build x11spice.
FROM debian:trixie AS x11spice_build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    gcc \
    make \
    libtool \
    autoconf \
    automake \
    pkg-config \
    xutils-dev \
    libspice-server-dev \
    libgtk-3-dev \
    libxcb1-dev \
    libxcb-damage0-dev \
    libxcb-xfixes0-dev \
    libxcb-shm0-dev \
    libxcb-xtest0-dev \
    libxcb-util-dev \
    libxcb-xkb-dev \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://gitlab.freedesktop.org/spice/x11spice.git /tmp/x11spice \
 && cd /tmp/x11spice \
 && ./autogen.sh --prefix=/usr/local \
 && make -j"$(nproc)" \
 && make install DESTDIR=/staging

# Stage 2: runtime image.
FROM debian:trixie
ENV DEBIAN_FRONTEND=noninteractive

# Keep package postinst scripts from starting services during the build --
# there is no init in a build layer.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
 && chmod +x /usr/sbin/policy-rc.d

# Wine needs 32-bit (i386) libraries to run 32-bit Windows apps.
RUN dpkg --add-architecture i386

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && mkdir -p /etc/apt/keyrings \
 && curl -fsSL -o /etc/apt/keyrings/cusdeb.gpg https://cusdeb-com.github.io/os/KEY.gpg \
 && chmod 644 /etc/apt/keyrings/cusdeb.gpg \
 && printf 'deb [signed-by=/etc/apt/keyrings/cusdeb.gpg] https://cusdeb-com.github.io/os stable main\n' \
    > /etc/apt/sources.list.d/cusdeb.list \
 && printf 'Package: *\nPin: release o=os-packages\nPin-Priority: 900\n' \
    > /etc/apt/preferences.d/99cusdeb \
 && apt-get update \
 && apt-get install -y \
    cdex-full \
    xvfb \
    x11-utils \
    x11-xserver-utils \
    libspice-server1 \
    libgtk-3-0t64 \
    libxcb-damage0 \
    libxcb-xfixes0 \
    libxcb-shm0 \
    libxcb-xtest0 \
    libxcb-xkb1 \
    sudo \
 && rm -rf /var/lib/apt/lists/*

# x11spice, from stage 1.
COPY --from=x11spice_build /staging/usr/local /usr/local
RUN ldconfig

# Wine won't run its session as root.
RUN useradd -m -s /bin/bash cusdeb \
 && usermod -aG sudo,users cusdeb \
 && printf 'cusdeb ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/cusdeb \
 && chmod 440 /etc/sudoers.d/cusdeb

COPY start-cdex.sh /usr/local/bin/start-cdex.sh
RUN chmod +x /usr/local/bin/start-cdex.sh

EXPOSE 5900
CMD ["/usr/local/bin/start-cdex.sh"]
