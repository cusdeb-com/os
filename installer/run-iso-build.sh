#!/usr/bin/env bash
set -euo pipefail

# Host wrapper for building the Calamares live ISO.
# Uses docker buildx with the "security.insecure" entitlement so live-build can
# debootstrap, mount pseudo-filesystems, and produce the hybrid ISO inside the
# Dockerfile build stage. The final ISO is exported via the scratch exporter
# stage, matching the package build pattern used by core/cdex/Dockerfile.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
IMAGE_TAG="${IMAGE_TAG:-cusdeb-os-calamares-builder:trixie}"
OUT_DIR="${OUT_DIR:-${PROJECT_ROOT}/out}"
ISO_NAME="${ISO_NAME:-cusdeb-os.iso}"
MIRROR="${MIRROR:-http://deb.debian.org/debian}"
FORCE_CLEAN="${FORCE_CLEAN:-0}"

mkdir -p "${OUT_DIR}"

# Ensure a buildx builder with the insecure entitlement exists. Reusing the
# default builder is fine if it already allows security.insecure; otherwise we
# create and use a dedicated one.
BUILDER_NAME="cusdeb-os-calamares-builder"
if ! docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
    echo "Creating buildx builder ${BUILDER_NAME} with insecure entitlement..."
    docker buildx create \
        --name "${BUILDER_NAME}" \
        --buildkitd-flags '--allow-insecure-entitlement security.insecure' \
        --use
else
    docker buildx use "${BUILDER_NAME}"
fi

echo "Building Calamares live ISO via docker buildx..."
docker buildx build \
    --file "${SCRIPT_DIR}/Dockerfile" \
    --tag "${IMAGE_TAG}" \
    --target exporter \
    --output "type=local,dest=${OUT_DIR}" \
    --allow security.insecure \
    --build-arg "ISO_NAME=${ISO_NAME}" \
    --build-arg "MIRROR=${MIRROR}" \
    --build-arg "FORCE_CLEAN=${FORCE_CLEAN}" \
    "${PROJECT_ROOT}"

# The exporter stage writes the ISO to the root of the output directory, but the
# filename inside the ISO comes from ISO_NAME. Rename it locally if needed.
EXPORTED_ISO="${OUT_DIR}/${ISO_NAME}"
if [ -f "${EXPORTED_ISO}" ]; then
    echo "SUCCESS: ${EXPORTED_ISO}"
    ls -lh "${EXPORTED_ISO}"
else
    echo "ERROR: ISO not found at ${EXPORTED_ISO}"
    ls -la "${OUT_DIR}"
    exit 1
fi
