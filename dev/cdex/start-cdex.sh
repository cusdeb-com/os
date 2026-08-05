#!/bin/bash
# Bring up the CDEX Win32 desktop on a virtual X display and expose it over
# SPICE. Connect from the host with:
#     remote-viewer spice://localhost:5900        (password: see SPICE_PASSWORD)
#
# The spiceqxl / xserver-xspice driver is broken on Debian trixie, so instead we
# run the session on Xvfb and attach x11spice (a SPICE server for a live X
# display) to it.
set -euo pipefail

SPICE_PORT="${SPICE_PORT:-5900}"
SPICE_PASSWORD="${SPICE_PASSWORD:-secret}"
RESOLUTION="${RESOLUTION:-1280x720x24}"
DISPLAY_NUM="${DISPLAY_NUM:-0}"
export DISPLAY=":${DISPLAY_NUM}"

uid="$(id -u cusdeb)"

# Disable the GTK accessibility bridge; otherwise yad's a11y activation can stall
# the session for ~120s.
export NO_AT_BRIDGE=1

cleanup() { pkill -P $$ 2>/dev/null || true; }
trap cleanup EXIT

# Clear any stale X lock/socket from a previous run so `docker restart`
# reliably brings the display back up.
rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}" 2>/dev/null || true

# 1. Virtual X server.
Xvfb ":${DISPLAY_NUM}" -screen 0 "${RESOLUTION}" -ac +extension MIT-SHM +extension XTEST \
    >/var/log/xvfb.log 2>&1 &

for _ in $(seq 1 60); do
    xdpyinfo -display ":${DISPLAY_NUM}" >/dev/null 2>&1 && break
    sleep 0.5
done

# 2. SPICE server attached to the X display.
x11spice \
    --display=":${DISPLAY_NUM}" \
    --allow-control \
    --hide \
    --password="${SPICE_PASSWORD}" \
    "0.0.0.0:${SPICE_PORT}" \
    >/var/log/x11spice.log 2>&1 &

# 3. The CDEX Win32 shell session, as the non-root cusdeb user.
install -d -o cusdeb -g cusdeb "/run/user/${uid}"
runuser -u cusdeb -- env \
    DISPLAY=":${DISPLAY_NUM}" \
    XDG_RUNTIME_DIR="/run/user/${uid}" \
    HOME="/home/cusdeb" \
    WINEDEBUG="${WINEDEBUG:--all}" \
    NO_AT_BRIDGE=1 \
    /usr/bin/cdex-win32-session &
session_pid=$!

wait "${session_pid}"
