#!/usr/bin/env bash
set -euo pipefail

# Build configuration knobs. These defaults are meant to be overridden by the
# outer wrapper or CI environment without editing the script itself.
IMAGE_NAME="${IMAGE_NAME-cusdeb-os.img}"
IMAGE_SIZE="${IMAGE_SIZE-12G}"
RELEASE="${RELEASE-trixie}"
ARCH="${ARCH-amd64}"
MIRROR="${MIRROR-https://deb.debian.org/debian}"
VM_HOSTNAME="${VM_HOSTNAME-cusdeb-os}"
ROOT_PASSWORD="${ROOT_PASSWORD-}"
OUT_DIR="${OUT_DIR-/workspace/out}"
HOST_UID="${HOST_UID-}"
HOST_GID="${HOST_GID-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_ROOT=""

# Resolve the canonical project root for sourced shell modules. The builder may
# run directly from the repo checkout, from a Docker-mounted /workspace, or from
# the packaged share directory inside the builder image.
for candidate in \
  "$SCRIPT_DIR" \
  "/workspace" \
  "/usr/local/share/cusdeb-os"
do
  if [ -f "$candidate/scripts/essentials.sh" ]; then
    SCRIPT_ROOT="$candidate"
    break
  fi
done

if [ -z "$SCRIPT_ROOT" ]; then
  printf 'Missing scripts root with essentials.sh\n' >&2
  exit 1
fi

SCRIPT_DIR="$SCRIPT_ROOT"

# Load shared helpers first, then the numbered bootstrap stages in execution
# order so the main body below stays as a small orchestration layer.
source "$SCRIPT_ROOT/scripts/essentials.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/01-create-image.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/02-partition-image.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/03-attach-loop-devices.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/04-format-and-mount-rootfs.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/05-debootstrap-rootfs.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/06-write-base-config.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/07-provision-chroot.sh"
source "$SCRIPT_ROOT/scripts/bootstrap/08-finalize-image.sh"

CHROOT_SCRIPT_SOURCE=""
CUSDEB_SESSION_SOURCE=""
APP_BIN_SOURCE_DIR=""
PAINT_ICON_16_SOURCE=""
PAINT_ICON_48_SOURCE=""
ASSET_CACHE_DIR=""
CHICAGO95_CACHE=""
WIN98SE_CACHE=""
CURSOR_THEME_NAME="Chicago95_Standard_Cursors"
WALLPAPER_RELATIVE_PATH="Extras/Backgrounds/Wallpaper/Setup.png"

# Temporary paths and state used while assembling the disk image.
WORKDIR="$(mktemp -d)"
MNT="${WORKDIR}/mnt"
IMAGE_PATH="${OUT_DIR}/${IMAGE_NAME}"
LOOPDEV=""
PART_LOOPDEV=""
ROOT_UUID=""
PART_START_BYTES=""

mkdir -p "$MNT" "$OUT_DIR"
trap cleanup EXIT

require_cmd debootstrap
require_cmd parted
require_cmd losetup
require_cmd mkfs.ext4
require_cmd mount
require_cmd umount
require_cmd blkid
require_cmd chroot
require_cmd sync

validate_inputs
ensure_theme_assets

# Resolve the guest provisioning script and runtime payload from the repo-side
# layout. The guest still receives these assets under /root and /usr/local/bin;
# only the source-side project structure changed.
resolve_required_file \
  CHROOT_SCRIPT_SOURCE \
  "chroot script" \
  "${SCRIPT_DIR}/scripts/inside-chroot.sh" \
  "/workspace/scripts/inside-chroot.sh" \
  "/usr/local/share/cusdeb-os/scripts/inside-chroot.sh"

resolve_required_file \
  CUSDEB_SESSION_SOURCE \
  "cusdeb-session file" \
  "${SCRIPT_DIR}/userland/cusdeb-session" \
  "/workspace/userland/cusdeb-session" \
  "/usr/local/share/cusdeb-os/userland/cusdeb-session"

resolve_required_dir \
  APP_BIN_SOURCE_DIR \
  "application source directory: userland" \
  "${SCRIPT_DIR}/userland" \
  "/workspace/userland" \
  "/usr/local/share/cusdeb-os/userland"

if ! compgen -G "$APP_BIN_SOURCE_DIR/*.exe" >/dev/null; then
  printf 'Missing .exe application files in %s\n' "$APP_BIN_SOURCE_DIR" >&2
  exit 1
fi

 # Paint keeps custom icons alongside the userland payload so the Docker image,
 # local checkout, and packaged share directory all use the same asset layout.
resolve_required_file \
  PAINT_ICON_16_SOURCE \
  "paint_16.png file" \
  "${SCRIPT_DIR}/userland/icons/paint_16.png" \
  "/workspace/userland/icons/paint_16.png" \
  "/usr/local/share/cusdeb-os/userland/icons/paint_16.png"

resolve_required_file \
  PAINT_ICON_48_SOURCE \
  "paint_48.png file" \
  "${SCRIPT_DIR}/userland/icons/paint_48.png" \
  "/workspace/userland/icons/paint_48.png" \
  "/usr/local/share/cusdeb-os/userland/icons/paint_48.png"

stage_01_create_image
stage_02_partition_image
stage_03_attach_loop_devices
stage_04_format_and_mount_rootfs
stage_05_debootstrap_rootfs
stage_06_write_base_config
stage_07_provision_chroot
stage_08_finalize_image
