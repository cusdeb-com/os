# CDEX-over-SPICE runtime image.

ARG X11SPICE_IMAGE=cusdeb-os:x11spice
FROM ${X11SPICE_IMAGE}
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
 && ldconfig \
 && rm -rf /var/lib/apt/lists/*

# Wine won't run its session as root.
RUN useradd -m -s /bin/bash cusdeb \
 && usermod -aG sudo,users cusdeb \
 && printf 'cusdeb ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/cusdeb \
 && chmod 440 /etc/sudoers.d/cusdeb

COPY start-cdex.sh /usr/local/bin/start-cdex.sh
RUN chmod +x /usr/local/bin/start-cdex.sh

EXPOSE 5900
CMD ["/usr/local/bin/start-cdex.sh"]
