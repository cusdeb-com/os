#!/usr/bin/env bash
#
# Build and run the CDEX-over-SPICE container.
#
#   ./up.sh              build the image (if needed) and start the container
#   ./up.sh --rebuild    force a rebuild of the image
#
# After it finishes, connect from the host with a SPICE client:
#   remote-viewer spice://localhost:5900
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

IMAGE="${IMAGE:-cusdeb-os:cdex}"
CONTAINER="${CONTAINER:-cdex}"
SPICE_PORT="${SPICE_PORT:-5900}"
SPICE_BIND="${SPICE_BIND:-127.0.0.1}"
SPICE_PASSWORD="${SPICE_PASSWORD:-secret}"
RESOLUTION="${RESOLUTION:-1280x720x24}"

REBUILD=false
[ "${1:-}" = "--rebuild" ] && REBUILD=true

export DOCKER_BUILDKIT=1

# Build the image (context = dev/cdex/). CDEX is installed from the CusDeb
# Archive and x11spice is compiled from source in a builder stage; that first
# build takes a few minutes and is cached afterwards.
# --network=host lets RUN steps use the host resolver (needed behind a VPN,
# where the build sandbox's default DNS is unreachable).
if $REBUILD || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "==> Building $IMAGE ..."
    docker build --network=host -t "$IMAGE" "$HERE"
fi

# (Re)start the container.
echo "==> Starting container $CONTAINER ..."
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER" \
    -p "${SPICE_BIND}:${SPICE_PORT}:5900" \
    -e SPICE_PASSWORD="$SPICE_PASSWORD" \
    -e RESOLUTION="$RESOLUTION" \
    "$IMAGE" >/dev/null

echo
echo "==> Up. CDEX takes ~20-40s to finish loading."
echo "    Connect from the host with a SPICE client. For example:"
echo
echo "        remote-viewer spice://localhost:${SPICE_PORT}"
echo
echo "    Stop: docker rm -f ${CONTAINER}"
