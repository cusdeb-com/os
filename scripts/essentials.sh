#!/usr/bin/env bash

cleanup() {
  # Always try to tear down mounts, loop devices, and leftover Wine processes.
  # Build failures often happen mid-flight, so cleanup must be best-effort.
  set +e

  sync

  chroot "$MNT" /usr/bin/pkill -u cusdeb -f wine >/dev/null 2>&1 || true
  chroot "$MNT" /usr/bin/pkill -u cusdeb wineserver >/dev/null 2>&1 || true

  if mountpoint -q "$MNT/dev/pts"; then umount "$MNT/dev/pts" || true; fi
  if mountpoint -q "$MNT/dev"; then umount -R "$MNT/dev" || umount -l "$MNT/dev" || true; fi
  if mountpoint -q "$MNT/proc"; then umount "$MNT/proc" || umount -l "$MNT/proc" || true; fi
  if mountpoint -q "$MNT/sys"; then umount -R "$MNT/sys" || umount -l "$MNT/sys" || true; fi
  if mountpoint -q "$MNT"; then umount "$MNT" || umount -l "$MNT" || true; fi

  if [ -n "$PART_LOOPDEV" ]; then
    losetup -d "$PART_LOOPDEV" || true
  fi

  if [ -n "$LOOPDEV" ]; then
    losetup -d "$LOOPDEV" || true
  fi

  rm -rf "$WORKDIR"
}

require_cmd() {
  # Validate host-side prerequisites before the script starts mutating files,
  # creating loop devices, or mounting filesystems.
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

validate_inputs() {
  # Reject unsupported values early so the build fails with a clear message
  # instead of producing an image that only breaks much later at boot time.
  if [ "$ARCH" != "amd64" ]; then
    printf 'Unsupported ARCH: %s (only amd64 is currently supported)\n' "$ARCH" >&2
    exit 1
  fi

  if [[ ! "$RELEASE" =~ ^[a-z0-9][a-z0-9.-]*$ ]]; then
    printf 'Invalid RELEASE: %s\n' "$RELEASE" >&2
    exit 1
  fi

  if [[ ! "$VM_HOSTNAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
    printf 'Invalid VM_HOSTNAME: %s\n' "$VM_HOSTNAME" >&2
    exit 1
  fi

  if [[ "$IMAGE_NAME" != *.img || "$IMAGE_NAME" == */* ]]; then
    printf 'Invalid IMAGE_NAME: %s (must be a basename ending in .img)\n' "$IMAGE_NAME" >&2
    exit 1
  fi

  if [[ ! "$IMAGE_SIZE" =~ ^[1-9][0-9]*[KMGTP]$ ]]; then
    printf 'Invalid IMAGE_SIZE: %s (expected formats like 12G)\n' "$IMAGE_SIZE" >&2
    exit 1
  fi

  if [[ ! "$MIRROR" =~ ^https?://[^[:space:]]+$ ]]; then
    printf 'Invalid MIRROR: %s\n' "$MIRROR" >&2
    exit 1
  fi
}

resolve_asset_cache_dir() {
  local candidate=""

  for candidate in \
    "/workspace/assets-cache" \
    "${SCRIPT_DIR}/assets-cache"
  do
    case "$candidate" in
      /workspace/*)
        if [ -d "/workspace" ]; then
          ASSET_CACHE_DIR="$candidate"
          break
        fi
        ;;
      *)
        ASSET_CACHE_DIR="$candidate"
        break
        ;;
    esac
  done

  if [ -z "$ASSET_CACHE_DIR" ]; then
    printf 'Failed to resolve asset cache directory\n' >&2
    exit 1
  fi

  CHICAGO95_CACHE="$ASSET_CACHE_DIR/Chicago95"
  WIN98SE_CACHE="$ASSET_CACHE_DIR/Win98SE"
}

ensure_cached_repo() {
  local repo_url="$1"
  local repo_dir="$2"

  if [ -d "$repo_dir/.git" ]; then
    printf '[theme] Using cached assets: %s\n' "$repo_dir"
    return
  fi

  require_cmd git
  rm -rf "$repo_dir"
  printf '[theme] Downloading assets: %s\n' "$repo_url"
  git clone --depth 1 "$repo_url" "$repo_dir"
}

ensure_theme_assets() {
  resolve_asset_cache_dir
  mkdir -p "$ASSET_CACHE_DIR"
  ensure_cached_repo "https://github.com/grassmunk/Chicago95.git" "$CHICAGO95_CACHE"
  ensure_cached_repo "https://github.com/nestoris/Win98SE.git" "$WIN98SE_CACHE"

  if [ ! -d "$CHICAGO95_CACHE/Theme/Chicago95" ] || [ ! -d "$CHICAGO95_CACHE/Icons/Chicago95" ] || [ ! -d "$CHICAGO95_CACHE/Cursors" ]; then
    printf 'Chicago95 cache is missing expected theme directories\n' >&2
    exit 1
  fi

  if [ ! -d "$CHICAGO95_CACHE/Cursors/$CURSOR_THEME_NAME" ]; then
    printf 'Chicago95 cache is missing cursor theme: %s\n' "$CURSOR_THEME_NAME" >&2
    exit 1
  fi

  if [ ! -d "$WIN98SE_CACHE/SE98" ]; then
    printf 'Win98SE cache is missing the SE98 icon directory\n' >&2
    exit 1
  fi

  if [ ! -f "$CHICAGO95_CACHE/$WALLPAPER_RELATIVE_PATH" ]; then
    printf 'Chicago95 cache is missing wallpaper asset: %s\n' "$WALLPAPER_RELATIVE_PATH" >&2
    exit 1
  fi
}

install_theme_assets_into_rootfs() {
  install -d "$MNT/usr/share/themes" "$MNT/usr/share/icons" "$MNT/usr/share/backgrounds/chicago95"
  cp -R "$CHICAGO95_CACHE/Theme/Chicago95" "$MNT/usr/share/themes/"
  cp -R "$CHICAGO95_CACHE/Icons/Chicago95" "$MNT/usr/share/icons/"
  cp -R "$CHICAGO95_CACHE/Cursors/." "$MNT/usr/share/icons/"
  cp -R "$WIN98SE_CACHE/SE98" "$MNT/usr/share/icons/"
  cp "$CHICAGO95_CACHE/$WALLPAPER_RELATIVE_PATH" "$MNT/usr/share/backgrounds/chicago95/Setup.png"
}

resolve_required_file() {
  local __outvar="$1"
  local __label="$2"
  shift 2
  local candidate=""

  for candidate in "$@"; do
    if [ -f "$candidate" ]; then
      printf -v "$__outvar" '%s' "$candidate"
      return
    fi
  done

  printf 'Missing %s\n' "$__label" >&2
  exit 1
}

resolve_required_dir() {
  local __outvar="$1"
  local __label="$2"
  shift 2
  local candidate=""

  for candidate in "$@"; do
    if [ -d "$candidate" ]; then
      printf -v "$__outvar" '%s' "$candidate"
      return
    fi
  done

  printf 'Missing %s\n' "$__label" >&2
  exit 1
}
