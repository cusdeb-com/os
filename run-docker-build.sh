#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/out"
IMAGE_TAG="${IMAGE_TAG:-cusdeb-os-builder:trixie}"

# Keep the host-side wrapper deliberately small: it only builds the container
# image and runs the in-container builder with the project checkout mounted at
# /workspace and the output directory mounted at /workspace/out.
mkdir -p "$OUT_DIR"

docker build -t "$IMAGE_TAG" "$SCRIPT_DIR"

docker run --rm \
  --privileged \
  -v "$SCRIPT_DIR:/workspace" \
  -v "$OUT_DIR:/workspace/out" \
  -e IMAGE_NAME="${IMAGE_NAME-cusdeb-os.img}" \
  -e IMAGE_SIZE="${IMAGE_SIZE-12G}" \
  -e RELEASE="${RELEASE-trixie}" \
  -e ARCH="${ARCH-amd64}" \
  -e MIRROR="${MIRROR-https://deb.debian.org/debian}" \
  -e VM_HOSTNAME="${VM_HOSTNAME-cusdeb-os}" \
  -e ROOT_PASSWORD="${ROOT_PASSWORD-}" \
  -e HOST_UID="$(id -u)" \
  -e HOST_GID="$(id -g)" \
  "$IMAGE_TAG"
