#!/usr/bin/env bash

stage_05_debootstrap_rootfs() {
  # Stage 5: bootstrap a minimal Debian system directly into the mounted rootfs.
  printf '[5/8] Bootstrapping Debian %s\n' "$RELEASE"
  debootstrap --arch="$ARCH" "$RELEASE" "$MNT" "$MIRROR"
}
