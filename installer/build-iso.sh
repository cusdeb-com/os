#!/usr/bin/env bash
set -euo pipefail

# Build minimal Debian live ISO with Calamares installer.
# Designed to run inside the Dockerfile builder stage; it assumes the
# installer source tree has been copied to /build and that live-build tooling
# is available.
#
# NOTE: incremental builds are disabled for now because live-build's caching
# proved unreliable across config/package-list changes. Every invocation does
# a full clean rebuild. This is slower but predictable. Incremental builds may
# be reintroduced later.

SCRIPT_DIR="/build"
BUILD_DIR="${BUILD_DIR:-/tmp/live-build}"
OUT_DIR="${OUT_DIR:-/build/out}"
ISO_NAME="${ISO_NAME:-cusdeb-os.iso}"
MIRROR="${MIRROR:-http://deb.debian.org/debian}"

# FORCE_CLEAN is kept for backward compatibility but currently has no effect:
# every build starts from a clean state.
FORCE_CLEAN="${FORCE_CLEAN:-0}"

echo "=== Calamares Live ISO Builder ==="
echo "Build dir: ${BUILD_DIR}"
echo "Output dir: ${OUT_DIR}"
echo "ISO name:  ${ISO_NAME}"

# live-build bind-mounts /proc, /sys, /dev and /dev/pts into the chroot.
# Unmount them first, otherwise rm -rf fails on busy or leftover mounts.
for m in "${BUILD_DIR}/chroot/dev/pts" "${BUILD_DIR}/chroot/dev" "${BUILD_DIR}/chroot/proc" "${BUILD_DIR}/chroot/sys"; do
    if mountpoint -q "${m}" 2>/dev/null; then
        echo "    Unmounting ${m}..."
        umount "${m}" 2>/dev/null || umount -l "${m}" 2>/dev/null || true
    fi
done

# BUILD_DIR may be reused as a Docker build cache layer, so remove its contents
# rather than the directory itself.
if [ -d "${BUILD_DIR}" ]; then
    echo "[0/4] Cleaning build directory..."
    find "${BUILD_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi

mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"
cp -r "${SCRIPT_DIR}/auto" .
cp -r "${SCRIPT_DIR}/config" .
./auto/config

echo "[1/4] Building custom Calamares viewmodule..."
MODULE_BUILD_DIR="/tmp/optional-packages-build"
MODULE_SRC_DIR="${SCRIPT_DIR}/modules/optional-packages"
MODULE_INSTALL_DIR="${BUILD_DIR}/config/includes.chroot/usr/lib/x86_64-linux-gnu/calamares/modules/optional-packages"

rm -rf "${MODULE_BUILD_DIR}"
mkdir -p "${MODULE_BUILD_DIR}"
cd "${MODULE_BUILD_DIR}"
cmake "${MODULE_SRC_DIR}"
make -j"$(nproc)"

mkdir -p "${MODULE_INSTALL_DIR}"
cp "${MODULE_BUILD_DIR}/libcalamares_viewmodule_optional-packages.so" "${MODULE_INSTALL_DIR}/"
cp "${MODULE_SRC_DIR}/module.desc" "${MODULE_INSTALL_DIR}/"
echo "Custom viewmodule installed to: ${MODULE_INSTALL_DIR}"

cd "${BUILD_DIR}"

echo "[2/4] Building live image (full clean build, ~10-20 minutes)..."
lb build

echo "[3/4] Collecting output..."
mkdir -p "${OUT_DIR}"

# iso-hybrid produces live-image-amd64.hybrid.iso
ISO_SRC=""
for f in live-image-amd64.hybrid.iso live-image-amd64.iso; do
    if [ -f "$f" ]; then
        ISO_SRC="$f"
        break
    fi
done

if [ -n "${ISO_SRC}" ]; then
    cp "${ISO_SRC}" "${OUT_DIR}/${ISO_NAME}"
    echo "SUCCESS: ${OUT_DIR}/${ISO_NAME}"
    ls -lh "${OUT_DIR}/${ISO_NAME}"
else
    echo "ERROR: ISO not found in ${BUILD_DIR}"
    ls -la "${BUILD_DIR}"
    exit 1
fi

echo "[4/4] Done."
